# BUILD: Autopilot V2 — Calendar Sync + Push Loop + KR Auto-Progress

## Git config (ALWAYS use this)
git config user.name lukasjstr && git config user.email lukasjstr@gmail.com

## Context
- Bot uses GPT-4o exclusively (OpenAI). Never use Anthropic models.
- Server: root@95.111.252.176, venv at /opt/personal-os/venv/bin/python3
- DB: PostgreSQL, user=pos_user, db=personal_os, password=personalos2026, host=localhost
- Deploy: scp files → systemctl restart personal-os → build dashboard → systemctl restart personal-os-dashboard

---

## PART 1 — Google Calendar Sync (iCal, no OAuth needed)

The user provides their Google Calendar secret ICS URL (from calendar.google.com → Settings → export).
We fetch it periodically and sync events into the existing calendar_events table.

### 1a. Migration — add ical_url to users + google_event_id to calendar_events

File: `bot/database/migrations/versions/018_ical_sync.py`
```python
"""Add iCal sync fields

Revision ID: 018
Revises: 017
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('ical_url', sa.Text(), nullable=True))
    op.add_column('calendar_events', sa.Column('external_id', sa.String(512), nullable=True))
    op.add_column('calendar_events', sa.Column('external_source', sa.String(64), nullable=True))
    op.create_index('ix_calendar_events_external_id', 'calendar_events', ['external_id'])

def downgrade():
    op.drop_index('ix_calendar_events_external_id', 'calendar_events')
    op.drop_column('calendar_events', 'external_source')
    op.drop_column('calendar_events', 'external_id')
    op.drop_column('users', 'ical_url')
```

Also update models.py:
- Add to User class: `ical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`
- Add to CalendarEvent class: `external_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)` and `external_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)`

### 1b. iCal sync job

File: `bot/jobs/ical_sync.py` (NEW FILE)
```python
"""iCal sync — fetch Google Calendar ICS and upsert into calendar_events."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from icalendar import Calendar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_session
from bot.database.models import CalendarEvent, User

logger = logging.getLogger(__name__)


def _parse_dt(dt_val) -> Optional[datetime]:
    """Convert icalendar date/datetime to UTC datetime."""
    if dt_val is None:
        return None
    if hasattr(dt_val, 'dt'):
        dt_val = dt_val.dt
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val
        return dt_val.astimezone(timezone.utc).replace(tzinfo=None)
    # date only → midnight
    return datetime(dt_val.year, dt_val.month, dt_val.day, 0, 0, 0)


async def sync_ical_for_user(session: AsyncSession, user: User) -> int:
    """Fetch and sync iCal events for a user. Returns count of upserted events."""
    if not user.ical_url:
        return 0
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(user.ical_url)
            resp.raise_for_status()
            cal = Calendar.from_ical(resp.content)
    except Exception as e:
        logger.warning("iCal fetch failed for user %d: %s", user.id, e)
        return 0

    count = 0
    now = datetime.utcnow()
    cutoff_past = datetime(now.year, now.month, 1)  # only events from current month onwards
    cutoff_future = datetime(now.year + 1, now.month, now.day)  # max 1 year ahead

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", "Kein Titel"))
        dtstart = _parse_dt(component.get("DTSTART"))
        dtend = _parse_dt(component.get("DTEND"))
        description = str(component.get("DESCRIPTION", "") or "").strip() or None

        if not dtstart or not uid:
            continue
        if dtstart < cutoff_past or dtstart > cutoff_future:
            continue

        # Check if event already exists
        existing_result = await session.execute(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user.id,
                CalendarEvent.external_id == uid,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update if changed
            existing.title = summary
            existing.start_time = dtstart
            existing.end_time = dtend
            existing.description = description
        else:
            event = CalendarEvent(
                user_id=user.id,
                title=summary,
                start_time=dtstart,
                end_time=dtend,
                description=description,
                event_type="meeting",
                external_id=uid,
                external_source="ical",
            )
            session.add(event)
            count += 1

    await session.flush()
    logger.info("iCal sync: %d new events for user %d", count, user.id)
    return count


async def sync_all_users() -> None:
    """Sync iCal for all users who have an ical_url configured."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.ical_url.isnot(None), User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()
        for user in users:
            try:
                await sync_ical_for_user(session, user)
            except Exception as e:
                logger.error("iCal sync error for user %d: %s", user.id, e)
```

Install icalendar library: `pip install icalendar` (also add to requirements.txt)

### 1c. Add ical_sync to scheduler

File: `bot/jobs/scheduler.py`
Find where jobs are registered (look for `scheduler.add_job` calls) and add:
```python
from bot.jobs.ical_sync import sync_all_users as ical_sync_all

scheduler.add_job(
    ical_sync_all,
    "interval",
    minutes=15,
    id="ical_sync",
    replace_existing=True,
)
```

### 1d. API endpoint to save iCal URL

File: `bot/api/routes.py`
Add this endpoint near the settings endpoints:
```python
class SetIcalBody(BaseModel):
    ical_url: Optional[str] = None

@router.put("/settings/ical")
async def set_ical_url(
    body: SetIcalBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Save user's Google Calendar iCal URL and trigger immediate sync."""
    user.ical_url = body.ical_url or None
    await session.flush()
    if user.ical_url:
        from bot.jobs.ical_sync import sync_ical_for_user
        count = await sync_ical_for_user(session, user)
        return {"ok": True, "synced": count, "message": f"{count} Events importiert"}
    return {"ok": True, "synced": 0, "message": "iCal URL entfernt"}

@router.get("/settings/ical")
async def get_ical_status(
    user: User = Depends(get_current_user),
) -> dict:
    return {"ical_url": user.ical_url, "configured": bool(user.ical_url)}
```

### 1e. Dashboard Settings — iCal input

File: `dashboard/src/app/settings/page.tsx`
Find the settings form (look for existing input fields for profile settings).
Add a new section for Google Calendar sync. Find the place where settings sections are rendered and add:

```tsx
{/* Google Calendar Sync */}
<div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
  <h3 className="text-white font-semibold mb-1">📅 Google Calendar Sync</h3>
  <p className="text-zinc-500 text-sm mb-4">
    Verbinde deinen Google Kalender. Öffne calendar.google.com → Einstellungen → Deinen Kalender → "Geheime Adresse im iCal-Format".
  </p>
  <div className="flex gap-3">
    <input
      type="url"
      value={icalUrl}
      onChange={(e) => setIcalUrl(e.target.value)}
      placeholder="https://calendar.google.com/calendar/ical/..."
      className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
    />
    <button
      onClick={handleSaveIcal}
      disabled={savingIcal}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors disabled:opacity-40"
    >
      {savingIcal ? "Speichern..." : "Verbinden"}
    </button>
  </div>
  {icalStatus && (
    <p className="text-green-400 text-xs mt-2">✓ {icalStatus}</p>
  )}
</div>
```

Add the required state and handler to the settings page component (look at existing pattern for other settings):
```tsx
const [icalUrl, setIcalUrl] = useState("");
const [icalStatus, setIcalStatus] = useState("");
const [savingIcal, setSavingIcal] = useState(false);

// In useEffect that loads settings:
const icalRes = await api.get("/settings/ical");
setIcalUrl(icalRes.ical_url || "");

const handleSaveIcal = async () => {
  setSavingIcal(true);
  try {
    const res = await apiFetch("/api/settings/ical", { method: "PUT", body: JSON.stringify({ ical_url: icalUrl }) });
    setIcalStatus(res.message || "Verbunden!");
    addToast("Kalender verbunden", "success");
  } catch {
    addToast("Fehler beim Verbinden", "error");
  } finally {
    setSavingIcal(false);
  }
};
```

For the `apiFetch` PUT call, use the existing `apiPut` helper from `api.ts`:
```typescript
// In api.ts, add:
setIcalUrl: (ical_url: string | null) => apiPut<{ ok: boolean; synced: number; message: string }>("/api/settings/ical", { ical_url }),
getIcalStatus: () => apiFetch<{ ical_url: string | null; configured: boolean }>("/api/settings/ical"),
```

---

## PART 2 — Dashboard Task Completion → Telegram Next-Action Push

When a task is completed via the dashboard API, immediately send the next priority task to the user via Telegram.

### 2a. Update POST /api/tasks/{task_id}/complete in routes.py

Find the existing `complete_task` endpoint (search for `@router.post("/tasks/{task_id}/complete")`).
After the task is marked complete, add next-action push logic:

```python
# After marking task complete, find next task and push to Telegram
try:
    from bot.telegram.sender import send_message
    from bot.core.tasks import get_next_task_in_kr, get_open_tasks
    from bot.core.autopilot import get_next_action

    next_msg = None
    # Try KR-linked next task first
    if task.key_result_id:
        next_task = await get_next_task_in_kr(session, task.key_result_id)
        if next_task:
            next_msg = f"✅ *{task.title}* erledigt!\n\n➡️ *Nächste Aktion:*\n{next_task.title}"
    
    # Fallback: get highest priority open task
    if not next_msg:
        open_tasks = await get_open_tasks(session, user.id, limit=3)
        remaining = [t for t in open_tasks if t.id != task.id]
        if remaining:
            top = remaining[0]
            next_msg = f"✅ *{task.title}* erledigt!\n\n➡️ *Als nächstes:*\n[P{top.priority}] {top.title}"
        else:
            next_msg = f"✅ *{task.title}* erledigt!\n\n🎉 Alle Tasks erledigt! Zeit für ein neues Ziel."
    
    await send_message(user.telegram_id, next_msg, parse_mode="Markdown")
except Exception as e:
    logger.warning("Next-action push failed: %s", e)
```

### 2b. KR Auto-Progress on Task Completion

When completing a task that has a `key_result_id`, auto-increment the KR's `current_value` by 1.

In the same `complete_task` endpoint (or in `bot/core/tasks.py` in the `complete_task` function):
```python
# After marking task.status = "done":
if task.key_result_id:
    from bot.database.models import KeyResult
    kr = await session.get(KeyResult, task.key_result_id)
    if kr and kr.metric_type in ("number", "streak", "checklist"):
        kr.current_value = (kr.current_value or 0) + 1
        logger.info("Auto-incremented KR %d to %s", kr.id, kr.current_value)
```

---

## PART 3 — Proactive Gap Nudge Job

Every 30 minutes during working hours (7:00–22:00), check if there's a calendar gap coming up (next 60 min with no event) and push the highest priority task.

File: `bot/jobs/gap_nudge.py` (NEW FILE)
```python
"""Gap nudge — detect free time windows and push next priority task."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_session
from bot.database.models import CalendarEvent, Task, User
from bot.telegram.sender import send_message

logger = logging.getLogger(__name__)


async def send_gap_nudges() -> None:
    """Check all active users for upcoming free time windows and push next task."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = result.scalars().all()
        
        now = datetime.utcnow()
        hour = now.hour
        
        # Only during waking hours (7-22 UTC, adjust if needed)
        if hour < 7 or hour >= 22:
            return
        
        window_start = now + timedelta(minutes=5)
        window_end = now + timedelta(minutes=65)
        
        for user in users:
            try:
                # Check if there's a calendar event in the next 60 min
                conflict = await session.execute(
                    select(CalendarEvent).where(
                        and_(
                            CalendarEvent.user_id == user.id,
                            CalendarEvent.start_time >= window_start,
                            CalendarEvent.start_time <= window_end,
                        )
                    )
                )
                if conflict.scalars().first():
                    continue  # Busy, skip
                
                # Find highest priority open task
                tasks_result = await session.execute(
                    select(Task).where(
                        and_(
                            Task.user_id == user.id,
                            Task.status == "open",
                        )
                    ).order_by(Task.priority, Task.created_at).limit(1)
                )
                top_task = tasks_result.scalar_one_or_none()
                
                if not top_task:
                    continue
                
                # Only nudge once per task per day (check via a simple flag or timing heuristic)
                # For now, just push (can add deduplication later)
                msg = (
                    f"⚡ *Du hast gerade Zeit!*\n\n"
                    f"Deine Top-Priorität:\n"
                    f"☐ *{top_task.title}*"
                )
                if top_task.due_date:
                    msg += f"\n📅 Fällig: {top_task.due_date.strftime('%d.%m.')}"
                msg += "\n\nAntworte 'erledigt' wenn du fertig bist."
                
                await send_message(user.telegram_id, msg, parse_mode="Markdown")
                
            except Exception as e:
                logger.warning("Gap nudge failed for user %d: %s", user.id, e)
```

Add to scheduler:
```python
from bot.jobs.gap_nudge import send_gap_nudges

scheduler.add_job(
    send_gap_nudges,
    "interval",
    minutes=30,
    id="gap_nudge",
    replace_existing=True,
)
```

---

## PART 4 — Deploy

1. `pip install icalendar` in the venv on server
2. Add `icalendar` to `requirements.txt`
3. `python3 -m py_compile bot/database/models.py bot/api/routes.py bot/jobs/ical_sync.py bot/jobs/gap_nudge.py` — all must pass
4. `cd dashboard && npm run build` — must compile cleanly
5. SSH to server and deploy:
   ```bash
   ssh root@95.111.252.176 "
   cd /opt/personal-os
   venv/bin/pip install icalendar
   venv/bin/alembic upgrade 018
   systemctl restart personal-os
   echo BACKEND_DONE
   "
   ```
6. Copy dashboard files to server and rebuild
7. Commit: `git add -A && git commit -m "feat(autopilot): Google Calendar iCal sync + next-action push + KR auto-progress + gap nudges" && git push`

## Completion signal
When done: `openclaw system event --text "Done: Autopilot V2 live — iCal sync, next-action push, KR auto-progress, gap nudges" --mode now`
