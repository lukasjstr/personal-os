"""DB activity audit — row counts and last-activity per table.

Read-only. Idempotent. Default --dry-run (reads only; never writes).
Run: python3 scripts/audit_db.py > /tmp/audit_db.md
"""
import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import text

from bot.database.connection import get_session


# Tables where MAX(created_at) is the natural recency signal.
# Some tables use other timestamps; we fall back gracefully.
RECENCY_COLUMNS = [
    "created_at",
    "logged_at",
    "completed_at",
    "scheduled_for",
    "brief_date",
    "session_date",
]


async def list_tables(session) -> list[str]:
    result = await session.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ))
    return [r[0] for r in result]


async def count_rows(session, table: str) -> int | None:
    try:
        result = await session.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
        return result.scalar() or 0
    except Exception:
        return None


async def last_activity(session, table: str) -> tuple[str | None, str | None]:
    """Try each known recency column; return (col_used, max_value) or (None, None)."""
    # Get available columns first
    cols_result = await session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=:t"
    ), {"t": table})
    cols = {r[0] for r in cols_result}
    for col in RECENCY_COLUMNS:
        if col in cols:
            try:
                result = await session.execute(text(f'SELECT MAX("{col}") FROM "{table}"'))
                val = result.scalar()
                if val is not None:
                    return col, val.isoformat() if hasattr(val, "isoformat") else str(val)
                return col, None
            except Exception:
                continue
    return None, None


async def run(dry_run: bool) -> None:
    print("# AUDIT REPORT — DB Activity\n")
    print(f"_Generated: {datetime.now(timezone.utc).isoformat()}_\n")
    print(f"_Mode: {'dry-run (read-only)' if dry_run else 'live'}_\n")

    async with get_session() as session:
        tables = await list_tables(session)
        print(f"_Tables found: {len(tables)}_\n")
        print("| Table | Rows | Last activity | Column | Status |")
        print("|---|---:|---|---|---|")

        empty: list[str] = []
        stale: list[tuple[str, str]] = []  # (table, last_iso)
        for table in tables:
            count = await count_rows(session, table)
            col, last = await last_activity(session, table)
            if count is None:
                status = "ERROR"
            elif count == 0:
                status = "EMPTY"
                empty.append(table)
            else:
                status = "ACTIVE"
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        days = (datetime.now(timezone.utc) - last_dt).days
                        if days > 30:
                            status = f"STALE ({days}d)"
                            stale.append((table, last))
                    except ValueError:
                        pass
            count_str = "—" if count is None else str(count)
            last_str = last or "—"
            col_str = col or "—"
            print(f"| {table} | {count_str} | {last_str} | {col_str} | **{status}** |")

        print("\n## Top Findings\n")
        print("### Empty tables (0 rows)\n")
        if not empty:
            print("_None._")
        else:
            for t in empty:
                print(f"- `{t}` — never populated, candidate for review")

        print("\n### Stale tables (last activity > 30 days)\n")
        if not stale:
            print("_None._")
        else:
            for t, last in stale:
                print(f"- `{t}` — last activity: {last}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DB activity audit (read-only).")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Read-only mode (default; no writes ever happen).")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
