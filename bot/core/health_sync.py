"""Universal health data sync — accepts data from any source.

Sources: iOS Shortcuts, Huawei Health export, manual Telegram input.
Stores in existing Log table with appropriate log_types.
Auto-updates linked KRs when daily targets are met.
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import KeyResult, Log, User

logger = logging.getLogger(__name__)


async def sync_health_metrics(
    session: AsyncSession,
    user: User,
    metrics: dict,
    source: str = "api",
) -> dict:
    """
    Accept health metrics dict and store in Log table.
    Auto-update linked KRs if daily targets are met.

    metrics keys (all optional):
        sleep_hours: float
        sleep_quality: int (1-10)
        steps: int
        hrv: int (ms)
        weight_kg: float
        calories: int
        active_minutes: int
        resting_heart_rate: int
        spo2: float (%)
        stress_score: int (0-100)
        metric_date: str (YYYY-MM-DD, default today)
    """
    metric_date_str = metrics.get("metric_date")
    if metric_date_str:
        try:
            metric_date = date.fromisoformat(metric_date_str)
        except ValueError:
            metric_date = date.today()
    else:
        metric_date = date.today()

    metric_dt = datetime.combine(metric_date, datetime.min.time())
    stored = []
    kr_updates = []

    # ── Sleep ───────────────────────────────────────────────────────────────
    sleep_hours = metrics.get("sleep_hours")
    if sleep_hours is not None:
        await _upsert_log(session, user.id, "sleep", {
            "hours": float(sleep_hours),
            "quality": metrics.get("sleep_quality"),
            "source": source,
        }, metric_dt)
        stored.append(f"Schlaf: {sleep_hours:.1f}h")

        # Auto-update sleep KR if ≥ target
        kr_update = await _maybe_update_kr(session, user.id, "schlaf", float(sleep_hours), metric_date)
        if kr_update:
            kr_updates.append(kr_update)

    # ── Steps ────────────────────────────────────────────────────────────────
    steps = metrics.get("steps")
    if steps is not None:
        await _upsert_log(session, user.id, "steps", {
            "count": int(steps),
            "source": source,
        }, metric_dt)
        stored.append(f"Schritte: {int(steps):,}")

        # Auto-update steps KR
        kr_update = await _maybe_update_kr(session, user.id, "schritte", float(steps), metric_date)
        if kr_update:
            kr_updates.append(kr_update)

    # ── HRV ─────────────────────────────────────────────────────────────────
    hrv = metrics.get("hrv")
    if hrv is not None:
        await _upsert_log(session, user.id, "hrv", {
            "score": int(hrv),
            "unit": "ms",
            "source": source,
        }, metric_dt)
        stored.append(f"HRV: {int(hrv)}ms")

    # ── Weight ───────────────────────────────────────────────────────────────
    weight = metrics.get("weight_kg")
    if weight is not None:
        await _upsert_log(session, user.id, "weight", {
            "kg": float(weight),
            "source": source,
        }, metric_dt)
        stored.append(f"Gewicht: {float(weight):.1f}kg")

    # ── Other metrics ────────────────────────────────────────────────────────
    extras = {}
    for key in ("calories", "active_minutes", "resting_heart_rate", "spo2", "stress_score"):
        if metrics.get(key) is not None:
            extras[key] = metrics[key]
    if extras:
        extras["source"] = source
        await _upsert_log(session, user.id, "health_metrics", extras, metric_dt)
        stored.append(f"Weitere: {list(extras.keys())}")

    await session.flush()
    return {
        "stored": stored,
        "kr_updates": kr_updates,
        "date": str(metric_date),
        "source": source,
    }


async def parse_huawei_export(zip_bytes: bytes) -> list[dict]:
    """
    Parse a Huawei Health ZIP export and return list of daily metric dicts.

    Huawei Health exports include CSV files:
    - sleep_*.csv: date, sleep_duration_hours, deep_sleep, light_sleep, rem, awake
    - step_count_*.csv: date, steps
    - health_data_*.csv: date, hrv_avg, resting_heart_rate, spo2, stress
    """
    daily: dict[str, dict] = {}  # date_str → metrics dict

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                name_lower = name.lower()
                with zf.open(name) as f:
                    content = f.read().decode("utf-8", errors="ignore")

                if "sleep" in name_lower and name_lower.endswith(".csv"):
                    _parse_sleep_csv(content, daily)
                elif "step" in name_lower and name_lower.endswith(".csv"):
                    _parse_steps_csv(content, daily)
                elif "health_data" in name_lower and name_lower.endswith(".csv"):
                    _parse_health_csv(content, daily)
                elif "sport" in name_lower and name_lower.endswith(".csv"):
                    # Workout sessions — skip for now, handled separately
                    pass
    except zipfile.BadZipFile:
        logger.error("Invalid ZIP file for Huawei export")
        return []
    except Exception:
        logger.exception("Error parsing Huawei export")
        return []

    return [{"metric_date": d, **v} for d, v in sorted(daily.items())]


def _parse_sleep_csv(content: str, daily: dict) -> None:
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        try:
            # Try common Huawei column names
            date_str = (row.get("Date") or row.get("date") or row.get("Datum") or "").strip()
            if not date_str:
                continue
            # Normalize date
            date_str = _normalize_date(date_str)
            if not date_str:
                continue

            duration = float(
                row.get("Sleep Duration") or row.get("sleep_duration")
                or row.get("Total Sleep Time") or row.get("total_sleep_time")
                or row.get("Schlafdauer") or 0
            )
            # Huawei sometimes stores in minutes, sometimes hours
            if duration > 24:
                duration = duration / 60  # convert minutes to hours

            if duration > 0:
                daily.setdefault(date_str, {})["sleep_hours"] = round(duration, 2)
        except (ValueError, KeyError):
            pass


def _parse_steps_csv(content: str, daily: dict) -> None:
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        try:
            date_str = (row.get("Date") or row.get("date") or row.get("Datum") or "").strip()
            date_str = _normalize_date(date_str)
            if not date_str:
                continue
            steps = int(
                row.get("Steps") or row.get("steps") or row.get("Schritte")
                or row.get("Step Count") or 0
            )
            if steps > 0:
                daily.setdefault(date_str, {})["steps"] = steps
        except (ValueError, KeyError):
            pass


def _parse_health_csv(content: str, daily: dict) -> None:
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        try:
            date_str = (row.get("Date") or row.get("date") or row.get("Datum") or "").strip()
            date_str = _normalize_date(date_str)
            if not date_str:
                continue

            d = daily.setdefault(date_str, {})

            hrv = row.get("HRV") or row.get("hrv") or row.get("HRV Average")
            if hrv and str(hrv).strip():
                try:
                    d["hrv"] = int(float(hrv))
                except ValueError:
                    pass

            rhr = row.get("Resting Heart Rate") or row.get("resting_heart_rate")
            if rhr and str(rhr).strip():
                try:
                    d["resting_heart_rate"] = int(float(rhr))
                except ValueError:
                    pass

            spo2 = row.get("SpO2") or row.get("spo2") or row.get("Blood Oxygen")
            if spo2 and str(spo2).strip():
                try:
                    d["spo2"] = float(spo2)
                except ValueError:
                    pass
        except (ValueError, KeyError):
            pass


def _normalize_date(raw: str) -> str:
    """Try to normalize various date formats to YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


async def _upsert_log(
    session: AsyncSession,
    user_id: int,
    log_type: str,
    data: dict,
    logged_at: datetime,
) -> None:
    """Create or update a log entry for the given date + type (one per day)."""
    day_start = logged_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = logged_at.replace(hour=23, minute=59, second=59)

    existing = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type == log_type,
            Log.logged_at >= day_start,
            Log.logged_at <= day_end,
        ))
    )).scalar_one_or_none()

    if existing:
        existing.data = data
    else:
        session.add(Log(
            user_id=user_id,
            log_type=log_type,
            data=data,
            logged_at=logged_at,
        ))


async def _maybe_update_kr(
    session: AsyncSession,
    user_id: int,
    keyword: str,
    value: float,
    metric_date: date,
) -> Optional[str]:
    """If an active KR title contains keyword and value meets target → increment streak."""
    krs = (await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
        ))
    )).scalars().all()

    for kr in krs:
        if keyword.lower() not in kr.title.lower():
            continue

        # Check if already updated today
        today_progress = (await session.execute(
            select(Log).where(and_(
                Log.user_id == user_id,
                Log.log_type == "progress",
                Log.key_result_id == kr.id,
                extract("year", Log.logged_at) == metric_date.year,
                extract("month", Log.logged_at) == metric_date.month,
                extract("day", Log.logged_at) == metric_date.day,
            ))
        )).scalar_one_or_none()

        if today_progress:
            continue  # Already logged today

        # Check if target is met
        target = kr.target_value or 0
        if keyword == "schritte" and value >= target:
            kr.current_value = min(kr.current_value + 1, kr.target_value or 999)
            session.add(Log(
                user_id=user_id,
                log_type="progress",
                key_result_id=kr.id,
                data={"value": 1, "source": "health_sync", "actual_value": value},
                logged_at=datetime.combine(metric_date, datetime.min.time()),
            ))
            return f"KR#{kr.id} '{kr.title}' automatisch aktualisiert ({value:.0f} Schritte)"

        elif keyword == "schlaf" and value >= 7.0:  # ≥7h sleep target
            kr.current_value = min(kr.current_value + 1, kr.target_value or 999)
            session.add(Log(
                user_id=user_id,
                log_type="progress",
                key_result_id=kr.id,
                data={"value": 1, "source": "health_sync", "actual_hours": value},
                logged_at=datetime.combine(metric_date, datetime.min.time()),
            ))
            return f"KR#{kr.id} '{kr.title}' automatisch aktualisiert ({value:.1f}h Schlaf)"

    return None


async def get_health_context(session: AsyncSession, user_id: int) -> str:
    """Return yesterday's health metrics for AI context."""
    from datetime import timedelta
    yesterday = date.today() - timedelta(days=1)
    y_start = datetime.combine(yesterday, datetime.min.time())
    y_end = datetime.combine(yesterday, datetime.max.time())

    logs = (await session.execute(
        select(Log).where(and_(
            Log.user_id == user_id,
            Log.log_type.in_(["sleep", "steps", "hrv", "weight", "health_metrics"]),
            Log.logged_at >= y_start,
            Log.logged_at <= y_end,
        ))
    )).scalars().all()

    if not logs:
        return ""

    lines = [f"=== GESUNDHEIT GESTERN ({yesterday.strftime('%d.%m')}) ==="]
    for log in logs:
        d = log.data or {}
        if log.log_type == "sleep":
            h = d.get("hours", "?")
            q = f" (Qualität: {d['quality']}/10)" if d.get("quality") else ""
            emoji = "✅" if float(h) >= 7 else "⚠️"
            lines.append(f"  {emoji} Schlaf: {h}h{q}")
        elif log.log_type == "steps":
            s = d.get("count", 0)
            emoji = "✅" if s >= 8000 else "⚠️"
            lines.append(f"  {emoji} Schritte: {int(s):,}")
        elif log.log_type == "hrv":
            lines.append(f"  💓 HRV: {d.get('score', '?')}ms")
        elif log.log_type == "weight":
            lines.append(f"  ⚖️ Gewicht: {d.get('kg', '?')}kg")
        elif log.log_type == "health_metrics":
            if d.get("resting_heart_rate"):
                lines.append(f"  ❤️ Ruhepuls: {d['resting_heart_rate']} bpm")
            if d.get("spo2"):
                lines.append(f"  🫁 SpO2: {d['spo2']}%")
    return "\n".join(lines)
