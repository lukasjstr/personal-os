"""Seed Lukas's bedrock (V3 P02 — Lukas-Kalibrierung).

Hand-curated identity layer that ALWAYS goes into the AI context.
Idempotent: re-running upserts by user_id and only overwrites the bedrock
when --force is passed.

Run: PYTHONPATH=. python3 scripts/seed_lukas_bedrock.py [--force] [--user-id N]
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from bot.database.connection import get_session
from bot.database.models import LifeProfile, User


LUKAS_BEDROCK: dict = {
    "identity": {
        "name": "Lukas",
        "current_location": "Bangkok",
        "home_country": "Deutschland",
        "company": "Blaue Adler",
        "co_founders": ["Nils", "Philipp"],
        "launch_target": "Juni/Juli 2026",
        "birthdays": {"self": "29.12", "dad": "14.06"},
    },
    "life_areas": [
        {"name": "Mental/Emotional", "vision": "emotional stability, loving, patient, caring, inspiring"},
        {"name": "Physical", "vision": "~85kg, Leonidas/Spartan look"},
        {"name": "Character", "vision": "leader, multilingual, learn Greek & Latin, intellectually spar with dad"},
        {"name": "Family", "vision": "loving family, wolf pack of winners sharing learnings"},
        {"name": "Romance", "vision": "find wife material + live out sexual desires"},
        {"name": "Money/Business", "vision": "10k/mo → 36M → own sports team, Shark Tank investor, Tuscan winery"},
        {"name": "Lifestyle", "vision": "location-independent, yacht, jet, UFC first row, Monaco GP"},
        {"name": "Charity", "vision": "buildings named after him, give back to fostering orgs"},
        {"name": "Spirituality", "vision": "life is reality to experience, make the most of it"},
    ],
    "skill_levers": [
        {"name": "Kapitalallokation", "description": "Equity, Cashflow-Assets, Strukturen", "priority": 2},
        {"name": "Vertrieb & Verhandlung", "description": "Öffnet jede Tür", "priority": 2},
        {"name": "Bauen mit Leverage", "description": "Produkt + Team + AI — Blaue Adler", "priority": 2},
        {"name": "Selbstführung & Organisation", "description": "Größter Hebel, identifizierter Engpass", "priority": 1},
    ],
    "self_leadership_competencies": [
        "Klarheit über das eine Ziel",
        "Entscheidungsqualität unter Unsicherheit",
        "Selbstwahrnehmung in Echtzeit",
        "Emotionsregulation",
        "Energiemanagement statt Zeitmanagement",
        "Versprechensdisziplin",
        "Konsequente Selbstkonfrontation",
        "Erholungs-/Solitude-Fähigkeit",
        "Systemdenken über sich selbst",
        "Bereitschaft Identität zu aktualisieren",
    ],
    "leitspruch": (
        "Ich bin der Beste darin, große Aufgaben zu operationalisieren — Visionen in Projekte, "
        "Projekte in Ergebnisse zu übersetzen. Ich durchdringe neue Komplexität schnell. Ich finde "
        "den Kern. Ich baue die Etappen. Meine Schwäche: Ich expandiere, wenn kein Cut kommt — und "
        "ich brauche Übergänge zwischen Etappen, um auf Hochleistung zu bleiben. Das manage ich aktiv."
    ),
    "strengths": ["Kompetenzen lernen", "Zahlen", "Analysieren", "Reflektieren"],
    "weaknesses": ["Geduld/Warten", "Organisation", "Zu viel parallel"],
    "bottleneck": "Layer 2 (Entscheidungshygiene, Fokus)",
    "language": "de",
    "communication_style": (
        "direkt, ohne Floskeln, max 4 Sätze, du-Form, kein 'Bitte', Coach nicht Assistent"
    ),
}


async def seed_for_user(user_id: int, force: bool) -> tuple[str, dict]:
    """Returns (action, bedrock). action ∈ {created, updated, skipped}."""
    async with get_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            return "user-not-found", {}

        profile = (await session.execute(
            select(LifeProfile).where(LifeProfile.user_id == user_id)
        )).scalar_one_or_none()

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if profile is None:
            profile = LifeProfile(
                user_id=user_id,
                bedrock=LUKAS_BEDROCK,
                bedrock_updated_at=now,
                bedrock_history=[{
                    "snapshot": LUKAS_BEDROCK,
                    "ts": now.isoformat(),
                    "source": "seed_lukas_bedrock",
                }],
            )
            session.add(profile)
            return "created", LUKAS_BEDROCK

        if profile.bedrock and not force:
            return "skipped", profile.bedrock

        # archive current bedrock to history before overwriting
        history = list(profile.bedrock_history or [])
        if profile.bedrock:
            history.append({
                "snapshot": profile.bedrock,
                "ts": (profile.bedrock_updated_at or profile.created_at).isoformat()
                       if profile.bedrock_updated_at or profile.created_at else now.isoformat(),
                "source": "pre-seed-archive",
            })
        history.append({
            "snapshot": LUKAS_BEDROCK,
            "ts": now.isoformat(),
            "source": "seed_lukas_bedrock(--force)" if force else "seed_lukas_bedrock",
        })
        profile.bedrock = LUKAS_BEDROCK
        profile.bedrock_updated_at = now
        profile.bedrock_history = history
        return "updated", LUKAS_BEDROCK


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Lukas's bedrock identity (P02).")
    parser.add_argument("--user-id", type=int, default=None,
                        help="Target user id. Default: seed for ALL users.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing bedrock (archives current to history first).")
    args = parser.parse_args()

    async def run() -> None:
        targets: list[int]
        if args.user_id is not None:
            targets = [args.user_id]
        else:
            async with get_session() as session:
                user_ids = (await session.execute(select(User.id))).scalars().all()
                targets = list(user_ids)
        if not targets:
            print("No users found.")
            return
        print(f"Seeding bedrock for {len(targets)} user(s): {targets}")
        for uid in targets:
            action, _ = await seed_for_user(uid, args.force)
            print(f"  user_id={uid}: {action}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
