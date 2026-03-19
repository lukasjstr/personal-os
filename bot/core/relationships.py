"""Feature 8: Relationship Engine — contacts, interactions, commitments."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Commitment, Contact, Interaction

logger = logging.getLogger(__name__)


async def create_contact(
    session: AsyncSession,
    user_id: int,
    name: str,
    relationship_type: str = "friend",
    birthday: Optional[date] = None,
    notes: Optional[str] = None,
) -> tuple[Contact, bool]:
    """Create a contact, or return existing one (dedup by name). Returns (contact, created)."""
    # Dedup: check if contact with same name already exists
    existing = await session.execute(
        select(Contact).where(and_(Contact.user_id == user_id, Contact.name == name))
    )
    contact = existing.scalar_one_or_none()
    if contact:
        # Update notes/birthday if new info provided
        if notes and not contact.notes:
            contact.notes = notes
        if birthday and not contact.birthday:
            contact.birthday = birthday
        await session.flush()
        return contact, False

    contact = Contact(
        user_id=user_id,
        name=name,
        relationship_type=relationship_type,
        birthday=birthday,
        notes=notes,
        is_active=True,
    )
    session.add(contact)
    await session.flush()
    return contact, True


async def log_interaction(
    session: AsyncSession,
    user_id: int,
    contact_id: int,
    interaction_type: str,
    notes: str = "",
    quality_score: Optional[int] = None,
) -> Interaction:
    """Log an interaction with a contact and update last_contacted_at."""
    now = datetime.utcnow()

    interaction = Interaction(
        user_id=user_id,
        contact_id=contact_id,
        interaction_type=interaction_type,
        notes=notes or None,
        quality_score=quality_score,
        interacted_at=now,
    )
    session.add(interaction)

    # Update contact's last_contacted_at
    contact_result = await session.execute(
        select(Contact).where(and_(Contact.id == contact_id, Contact.user_id == user_id))
    )
    contact = contact_result.scalar_one_or_none()
    if contact:
        contact.last_contacted_at = now

    await session.flush()
    return interaction


async def get_overdue_contacts(session: AsyncSession, user_id: int) -> list[dict]:
    """Return contacts where (now - last_contacted_at) > contact_frequency_days."""
    now = datetime.utcnow()

    result = await session.execute(
        select(Contact).where(
            and_(
                Contact.user_id == user_id,
                Contact.is_active == True,  # noqa: E712
            )
        ).order_by(Contact.name)
    )
    contacts = result.scalars().all()

    overdue = []
    for c in contacts:
        if c.last_contacted_at is None:
            days_since = None
            overdue_days = None
            is_overdue = True  # never contacted
        else:
            days_since = (now - c.last_contacted_at).days
            overdue_days = days_since - c.contact_frequency_days
            is_overdue = overdue_days > 0

        if is_overdue:
            overdue.append({
                "id": c.id,
                "name": c.name,
                "nickname": c.nickname,
                "relationship_type": c.relationship_type,
                "contact_frequency_days": c.contact_frequency_days,
                "last_contacted_at": c.last_contacted_at.isoformat() if c.last_contacted_at else None,
                "days_since_contact": days_since,
                "overdue_days": overdue_days,
            })

    return overdue


async def add_commitment(
    session: AsyncSession,
    user_id: int,
    description: str,
    contact_id: Optional[int] = None,
    due_date: Optional[date] = None,
) -> Commitment:
    """Add a new commitment."""
    commitment = Commitment(
        user_id=user_id,
        contact_id=contact_id,
        description=description,
        due_date=due_date,
        status="pending",
    )
    session.add(commitment)
    await session.flush()
    return commitment


async def get_pending_commitments(session: AsyncSession, user_id: int) -> list[Commitment]:
    """Return pending commitments, including overdue ones."""
    today = date.today()

    result = await session.execute(
        select(Commitment)
        .options(selectinload(Commitment.contact))
        .where(
            and_(
                Commitment.user_id == user_id,
                Commitment.status.in_(["pending", "overdue"]),
            )
        )
        .order_by(Commitment.due_date.asc().nulls_last())
    )
    commitments = result.scalars().all()

    # Auto-mark overdue
    for c in commitments:
        if c.due_date and c.due_date < today and c.status == "pending":
            c.status = "overdue"

    await session.flush()
    return commitments


async def get_relationship_context(session: AsyncSession, user_id: int) -> str:
    """Return a context block with overdue contacts and pending commitments for AI."""
    overdue = await get_overdue_contacts(session, user_id)
    commitments = await get_pending_commitments(session, user_id)

    if not overdue and not commitments:
        return ""

    lines = ["=== BEZIEHUNGEN ==="]

    if overdue:
        lines.append(f"Überfällige Kontakte ({len(overdue)}):")
        for c in overdue[:5]:
            days_info = f"seit {c['days_since_contact']} Tagen" if c['days_since_contact'] else "noch nie kontaktiert"
            lines.append(f"  ⚠️ {c['name']} ({c['relationship_type']}) — {days_info}")

    if commitments:
        lines.append(f"Offene Zusagen ({len(commitments)}):")
        for cm in commitments[:5]:
            due_info = f" [fällig: {cm.due_date}]" if cm.due_date else ""
            overdue_marker = " ⚠️ ÜBERFÄLLIG" if cm.status == "overdue" else ""
            contact_name = cm.contact.name if cm.contact else ""
            contact_info = f" ({contact_name})" if contact_name else ""
            lines.append(f"  {'✅' if cm.status == 'done' else '☐'} {cm.description}{contact_info}{due_info}{overdue_marker}")

    lines.append("")
    return "\n".join(lines)
