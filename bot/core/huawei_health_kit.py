"""Huawei Health Kit REST API integration for real-time watch sync.

Supports Honor/Huawei watches via Huawei Health Kit Open Platform.
OAuth2 authorization → periodic data pull → sync to Personal OS.

Required env vars:
    HUAWEI_CLIENT_ID     — from Huawei Developer Console
    HUAWEI_CLIENT_SECRET — from Huawei Developer Console

Setup:
    1. Register at https://developer.huawei.com/consumer/en/
    2. Create a Health Kit app → get client_id + client_secret
    3. User authorizes via OAuth2 → we store refresh_token in user.settings
    4. Scheduler calls sync_huawei_health() periodically
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User

logger = logging.getLogger(__name__)

# ── Huawei Health Kit API endpoints ──────────────────────────────────────────

HUAWEI_AUTH_URL = "https://oauth-login.cloud.huawei.com/oauth2/v3/token"
HUAWEI_HEALTH_BASE = "https://health-api.cloud.huawei.com/healthkit/v1"

# Data type IDs (Huawei Health Kit constants)
DATA_TYPE_STEP = "com.huawei.health.step"
DATA_TYPE_SLEEP = "com.huawei.health.sleep"
DATA_TYPE_HEART_RATE = "com.huawei.health.heartrate"
DATA_TYPE_SPO2 = "com.huawei.health.spo2"
DATA_TYPE_STRESS = "com.huawei.health.stress"
DATA_TYPE_ACTIVITY = "com.huawei.health.activityrecord"

# Polymerize type IDs for daily aggregates
POLY_STEP = 1000
POLY_SLEEP = 1041
POLY_HEART_RATE = 1002
POLY_SPO2 = 1011
POLY_STRESS = 1012
POLY_CALORIES = 1005
POLY_DISTANCE = 1003
POLY_ACTIVE_MINUTES = 1013


def _get_credentials() -> tuple[str, str]:
    client_id = os.getenv("HUAWEI_CLIENT_ID", "")
    client_secret = os.getenv("HUAWEI_CLIENT_SECRET", "")
    return client_id, client_secret


# ── OAuth2 Token Management ─────────────────────────────────────────────────

async def get_authorization_url(user_id: int, redirect_uri: str) -> str:
    """Generate OAuth2 authorization URL for user to grant Health Kit access."""
    client_id, _ = _get_credentials()
    if not client_id:
        raise ValueError("HUAWEI_CLIENT_ID not configured")

    scopes = (
        "https://www.huawei.com/healthkit/step.read "
        "https://www.huawei.com/healthkit/sleep.read "
        "https://www.huawei.com/healthkit/heartrate.read "
        "https://www.huawei.com/healthkit/spo2.read "
        "https://www.huawei.com/healthkit/stress.read "
        "https://www.huawei.com/healthkit/activity.read "
        "https://www.huawei.com/healthkit/calories.read"
    )

    return (
        f"https://oauth-login.cloud.huawei.com/oauth2/v3/authorize?"
        f"response_type=code&access_type=offline"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state={user_id}"
    )


async def exchange_code_for_tokens(
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange OAuth2 authorization code for access + refresh tokens."""
    client_id, client_secret = _get_credentials()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(HUAWEI_AUTH_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        })
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token using the stored refresh token."""
    client_id, client_secret = _get_credentials()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(HUAWEI_AUTH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        resp.raise_for_status()
        return resp.json()


async def store_huawei_tokens(
    session: AsyncSession,
    user: User,
    token_data: dict,
) -> None:
    """Store Huawei OAuth tokens in user settings."""
    settings = dict(user.settings or {})
    settings["huawei_access_token"] = token_data.get("access_token")
    settings["huawei_refresh_token"] = token_data.get("refresh_token")
    settings["huawei_token_expires"] = (
        datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
    ).isoformat()
    user.settings = settings
    await session.flush()


async def get_valid_access_token(
    session: AsyncSession,
    user: User,
) -> Optional[str]:
    """Get a valid access token, refreshing if expired."""
    settings = user.settings or {}
    access_token = settings.get("huawei_access_token")
    refresh_token = settings.get("huawei_refresh_token")
    expires_str = settings.get("huawei_token_expires")

    if not access_token or not refresh_token:
        return None

    # Check expiry
    if expires_str:
        try:
            expires_at = datetime.fromisoformat(expires_str)
            if datetime.utcnow() < expires_at - timedelta(minutes=5):
                return access_token
        except ValueError:
            pass

    # Token expired or about to expire — refresh
    try:
        token_data = await refresh_access_token(refresh_token)
        await store_huawei_tokens(session, user, token_data)
        return token_data.get("access_token")
    except Exception:
        logger.exception(f"Failed to refresh Huawei token for user {user.id}")
        return None


# ── Data Retrieval ───────────────────────────────────────────────────────────

async def _fetch_daily_summary(
    access_token: str,
    data_type: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch polymerized (daily aggregated) health data from Huawei."""
    start_ms = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
    end_ms = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{HUAWEI_HEALTH_BASE}/data/polymerize",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "polymerizeType": data_type,
                "startTime": start_ms,
                "endTime": end_ms,
            },
        )
        if resp.status_code == 401:
            logger.warning("Huawei API returned 401 — token may be expired")
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("group", [])


async def fetch_steps(access_token: str, target_date: date) -> Optional[int]:
    """Fetch total steps for a single day."""
    groups = await _fetch_daily_summary(access_token, POLY_STEP, target_date, target_date)
    for g in groups:
        for sample in g.get("samplePoints", []):
            for field in sample.get("fieldValues", []):
                if field.get("fieldName") == "steps":
                    return int(field.get("intValue", 0))
    return None


async def fetch_sleep(access_token: str, target_date: date) -> Optional[dict]:
    """Fetch sleep data (total hours + phases) for a single night."""
    # Sleep data: query the night before (sleep crosses midnight)
    groups = await _fetch_daily_summary(
        access_token, POLY_SLEEP,
        target_date - timedelta(days=1), target_date,
    )
    if not groups:
        return None

    total_minutes = 0
    deep_minutes = 0
    light_minutes = 0
    rem_minutes = 0

    for g in groups:
        for sample in g.get("samplePoints", []):
            for field in sample.get("fieldValues", []):
                name = field.get("fieldName", "")
                val = field.get("intValue", 0)
                if name == "sleep_duration":
                    total_minutes += val
                elif name == "deep_sleep_duration":
                    deep_minutes += val
                elif name == "light_sleep_duration":
                    light_minutes += val
                elif name == "rem_sleep_duration":
                    rem_minutes += val

    if total_minutes == 0:
        return None

    return {
        "hours": round(total_minutes / 60, 2),
        "deep_hours": round(deep_minutes / 60, 2),
        "light_hours": round(light_minutes / 60, 2),
        "rem_hours": round(rem_minutes / 60, 2),
    }


async def fetch_heart_rate(access_token: str, target_date: date) -> Optional[dict]:
    """Fetch heart rate summary for a day."""
    groups = await _fetch_daily_summary(access_token, POLY_HEART_RATE, target_date, target_date)
    if not groups:
        return None

    values = []
    for g in groups:
        for sample in g.get("samplePoints", []):
            for field in sample.get("fieldValues", []):
                if field.get("fieldName") == "heart_rate":
                    values.append(int(field.get("intValue", 0)))

    if not values:
        return None

    return {
        "resting": min(values),
        "average": round(sum(values) / len(values)),
        "max": max(values),
    }


async def fetch_spo2(access_token: str, target_date: date) -> Optional[float]:
    """Fetch average SpO2 for a day."""
    groups = await _fetch_daily_summary(access_token, POLY_SPO2, target_date, target_date)
    values = []
    for g in groups:
        for sample in g.get("samplePoints", []):
            for field in sample.get("fieldValues", []):
                if field.get("fieldName") == "spo2":
                    values.append(float(field.get("floatValue", 0)))
    return round(sum(values) / len(values), 1) if values else None


async def fetch_stress(access_token: str, target_date: date) -> Optional[int]:
    """Fetch average stress score for a day."""
    groups = await _fetch_daily_summary(access_token, POLY_STRESS, target_date, target_date)
    values = []
    for g in groups:
        for sample in g.get("samplePoints", []):
            for field in sample.get("fieldValues", []):
                if field.get("fieldName") == "stress":
                    values.append(int(field.get("intValue", 0)))
    return round(sum(values) / len(values)) if values else None


# ── Main Sync Function ──────────────────────────────────────────────────────

async def sync_huawei_health(
    session: AsyncSession,
    user: User,
    target_date: Optional[date] = None,
) -> dict:
    """
    Pull all available health data from Huawei Health Kit and sync to Personal OS.

    Called by scheduler (daily) or manually via API.
    Returns dict compatible with sync_health_metrics().
    """
    from bot.core.health_sync import sync_health_metrics

    access_token = await get_valid_access_token(session, user)
    if not access_token:
        return {"error": "no_token", "message": "Huawei Health nicht verbunden. Bitte zuerst autorisieren."}

    if target_date is None:
        target_date = date.today() - timedelta(days=1)  # Default: sync yesterday

    metrics: dict = {"metric_date": target_date.isoformat()}
    errors: list[str] = []

    # Fetch all metrics in parallel-ish (sequential for simplicity, but fast)
    try:
        steps = await fetch_steps(access_token, target_date)
        if steps is not None:
            metrics["steps"] = steps
    except Exception as e:
        errors.append(f"steps: {e}")

    try:
        sleep = await fetch_sleep(access_token, target_date)
        if sleep:
            metrics["sleep_hours"] = sleep["hours"]
            metrics["sleep_quality"] = _estimate_sleep_quality(sleep)
    except Exception as e:
        errors.append(f"sleep: {e}")

    try:
        hr = await fetch_heart_rate(access_token, target_date)
        if hr:
            metrics["resting_heart_rate"] = hr["resting"]
    except Exception as e:
        errors.append(f"heart_rate: {e}")

    try:
        spo2 = await fetch_spo2(access_token, target_date)
        if spo2 is not None:
            metrics["spo2"] = spo2
    except Exception as e:
        errors.append(f"spo2: {e}")

    try:
        stress = await fetch_stress(access_token, target_date)
        if stress is not None:
            metrics["stress_score"] = stress
    except Exception as e:
        errors.append(f"stress: {e}")

    if len(metrics) <= 1:  # Only metric_date
        return {
            "error": "no_data",
            "message": f"Keine Daten von Huawei Health für {target_date}.",
            "details": errors,
        }

    # Use existing sync infrastructure
    result = await sync_health_metrics(session, user, metrics, source="huawei_health_kit")
    if errors:
        result["partial_errors"] = errors

    logger.info(f"Huawei Health sync for user {user.id}: {result.get('stored', [])}")
    return result


def _estimate_sleep_quality(sleep: dict) -> int:
    """Estimate sleep quality 1-10 from sleep phase data."""
    hours = sleep.get("hours", 0)
    deep = sleep.get("deep_hours", 0)
    rem = sleep.get("rem_hours", 0)

    score = 5  # baseline

    # Duration scoring
    if hours >= 7.5:
        score += 2
    elif hours >= 7:
        score += 1
    elif hours < 6:
        score -= 2
    elif hours < 6.5:
        score -= 1

    # Deep sleep: ideal is 1.5-2h (20-25% of total)
    if hours > 0:
        deep_pct = deep / hours
        if deep_pct >= 0.20:
            score += 1
        elif deep_pct < 0.10:
            score -= 1

    # REM: ideal is 1.5-2h (20-25% of total)
    if hours > 0:
        rem_pct = rem / hours
        if rem_pct >= 0.20:
            score += 1
        elif rem_pct < 0.10:
            score -= 1

    return max(1, min(10, score))


# ── Backfill ─────────────────────────────────────────────────────────────────

async def backfill_huawei_health(
    session: AsyncSession,
    user: User,
    days: int = 30,
) -> dict:
    """Sync the last N days of Huawei Health data (for initial setup)."""
    results = []
    today = date.today()

    for i in range(days, 0, -1):
        target = today - timedelta(days=i)
        try:
            result = await sync_huawei_health(session, user, target_date=target)
            if result.get("stored"):
                results.append({"date": str(target), "stored": result["stored"]})
        except Exception:
            logger.exception(f"Backfill failed for {target}")

    return {
        "days_synced": len(results),
        "days_requested": days,
        "details": results,
    }
