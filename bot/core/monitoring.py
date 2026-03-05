"""G3: Monitoring utilities — structured error logging, health probes, and rollback helpers.

Usage:
    from bot.core.monitoring import record_error, health_probe

All errors are logged to the structured error log and optionally to Telegram
when MONITORING_CHAT_ID is configured in settings.
"""
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path for structured error log (JSON Lines format)
_ERROR_LOG_PATH = Path("/opt/personal-os/logs/errors.jsonl")


def _ensure_log_dir() -> None:
    try:
        _ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass  # Non-fatal — may not have write access in dev


def record_error(
    source: str,
    error: Exception | str,
    context: dict[str, Any] | None = None,
    *,
    level: str = "error",
) -> None:
    """Record a structured error entry to the JSON Lines error log.

    Args:
        source: Identifier of the failing component (e.g. 'jobs.daily_suggestions').
        error: Exception or string message.
        context: Optional extra data (user_id, request path, etc.).
        level: 'error' | 'warning' | 'critical'
    """
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "level": level,
        "source": source,
        "message": str(error),
        "context": context or {},
        "traceback": traceback.format_exc() if isinstance(error, Exception) else None,
    }

    log_method = getattr(logger, level, logger.error)
    log_method("[%s] %s | ctx=%s", source, entry["message"], json.dumps(context or {}))

    _ensure_log_dir()
    try:
        with _ERROR_LOG_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as write_err:
        logger.warning("Could not write to error log: %s", write_err)


def get_recent_errors(limit: int = 50, level: str | None = None) -> list[dict]:
    """Read the last N structured error entries from the error log.

    Args:
        limit: Maximum number of entries to return (newest first).
        level: Optional filter by severity level.
    """
    if not _ERROR_LOG_PATH.exists():
        return []

    try:
        lines = _ERROR_LOG_PATH.read_text().strip().splitlines()
    except Exception:
        return []

    entries = []
    for line in reversed(lines):
        try:
            entry = json.loads(line)
            if level and entry.get("level") != level:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break
        except json.JSONDecodeError:
            continue

    return entries


async def health_probe(session) -> dict:
    """Run a quick DB connectivity probe and return status dict.

    Args:
        session: SQLAlchemy AsyncSession.
    """
    from sqlalchemy import text

    status = {"db": "error", "ts": datetime.utcnow().isoformat()}
    try:
        await session.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception as e:
        record_error("health_probe", e, {"check": "db"}, level="critical")
        status["db_error"] = str(e)

    return status
