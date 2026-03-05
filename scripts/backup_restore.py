#!/usr/bin/env python3
"""G5: Data backup and restore utilities for Personal OS.

Usage:
    # Create backup
    python3 scripts/backup_restore.py backup --output /opt/personal-os/backups/

    # List backups
    python3 scripts/backup_restore.py list --dir /opt/personal-os/backups/

    # Verify backup integrity
    python3 scripts/backup_restore.py verify --file backup_2026-03-05.sql.gz

    # Check migration safety (pending migrations)
    python3 scripts/backup_restore.py check-migrations

    # Restore from backup (DRY RUN by default — pass --execute to apply)
    python3 scripts/backup_restore.py restore --file backup_2026-03-05.sql.gz --execute

Requires: pg_dump, pg_restore, psql, gzip in PATH.
DB credentials from environment or CLAUDE.md defaults.
"""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DB_NAME = os.environ.get("DB_NAME", "personal_os")
DB_USER = os.environ.get("DB_USER", "pos_user")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")


def _run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=capture, text=True)
    return result


def cmd_backup(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    dump_path = output_dir / f"personal_os_backup_{ts}.sql"
    gz_path = dump_path.with_suffix(".sql.gz")

    print(f"Creating backup: {gz_path}")

    # pg_dump to plain SQL
    pg_cmd = [
        "pg_dump",
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-U", DB_USER,
        "-d", DB_NAME,
        "--no-password",
        "-f", str(dump_path),
    ]
    result = _run(pg_cmd, capture=False)
    if result.returncode != 0:
        print(f"ERROR: pg_dump failed (exit {result.returncode})", file=sys.stderr)
        return 1

    # Compress
    with open(dump_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        f_out.write(f_in.read())
    dump_path.unlink()

    # Write manifest
    sha256 = hashlib.sha256(gz_path.read_bytes()).hexdigest()
    size_kb = gz_path.stat().st_size // 1024
    manifest = {
        "file": gz_path.name,
        "created_at": datetime.utcnow().isoformat(),
        "sha256": sha256,
        "size_kb": size_kb,
        "db": DB_NAME,
        "host": DB_HOST,
    }
    manifest_path = gz_path.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"Backup complete: {gz_path} ({size_kb} KB)")
    print(f"SHA256: {sha256}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    backup_dir = Path(args.dir)
    if not backup_dir.exists():
        print(f"No backup directory found: {backup_dir}")
        return 0

    backups = sorted(backup_dir.glob("*.sql.gz"), reverse=True)
    if not backups:
        print("No backups found.")
        return 0

    print(f"{'File':<50} {'Size':>8}  {'Date'}")
    print("-" * 75)
    for b in backups:
        size_kb = b.stat().st_size // 1024
        mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{b.name:<50} {size_kb:>6} KB  {mtime}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    gz_path = Path(args.file)
    if not gz_path.exists():
        print(f"ERROR: File not found: {gz_path}", file=sys.stderr)
        return 1

    manifest_path = gz_path.with_suffix(".json")
    if not manifest_path.exists():
        print("WARNING: No manifest found — cannot verify checksum.")
    else:
        manifest = json.loads(manifest_path.read_text())
        expected_sha256 = manifest.get("sha256")
        actual_sha256 = hashlib.sha256(gz_path.read_bytes()).hexdigest()
        if expected_sha256 and expected_sha256 != actual_sha256:
            print(f"ERROR: Checksum mismatch!\n  Expected: {expected_sha256}\n  Got:      {actual_sha256}")
            return 1
        print(f"Checksum OK: {actual_sha256}")
        print(f"Created: {manifest.get('created_at')}  Size: {manifest.get('size_kb')} KB")

    # Try decompressing to verify gzip integrity
    try:
        with gzip.open(gz_path, "rb") as f:
            first_bytes = f.read(512)
        if b"PostgreSQL" in first_bytes or b"--" in first_bytes:
            print("Content: valid PostgreSQL dump")
        else:
            print("Content: decompressed OK (format unrecognized)")
    except Exception as e:
        print(f"ERROR: Failed to decompress: {e}", file=sys.stderr)
        return 1

    print("Verification PASSED")
    return 0


def cmd_check_migrations(args: argparse.Namespace) -> int:
    """Check for pending Alembic migrations."""
    result = _run(["alembic", "current"])
    if result.returncode != 0:
        print(f"WARNING: alembic current failed: {result.stderr}")
    else:
        print(f"Current revision:\n{result.stdout}")

    result2 = _run(["alembic", "heads"])
    if result2.returncode != 0:
        print(f"WARNING: alembic heads failed: {result2.stderr}")
    else:
        print(f"Head revision(s):\n{result2.stdout}")

    if result.returncode == 0 and result2.returncode == 0:
        current = result.stdout.strip()
        head = result2.stdout.strip()
        if current == head or head in current:
            print("Migration status: UP TO DATE")
        else:
            print("Migration status: PENDING MIGRATIONS DETECTED")
            return 1
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    gz_path = Path(args.file)
    if not gz_path.exists():
        print(f"ERROR: File not found: {gz_path}", file=sys.stderr)
        return 1

    if not args.execute:
        print(f"DRY RUN: Would restore {gz_path} → {DB_NAME}@{DB_HOST}")
        print("Pass --execute to perform the actual restore.")
        return 0

    print(f"RESTORING: {gz_path} → {DB_NAME}@{DB_HOST}")
    print("WARNING: This will DROP and recreate the database!")

    # Decompress to temp file
    tmp_sql = gz_path.with_suffix("")
    with gzip.open(gz_path, "rb") as f_in, open(tmp_sql, "wb") as f_out:
        f_out.write(f_in.read())

    try:
        result = _run([
            "psql",
            "-h", DB_HOST,
            "-p", DB_PORT,
            "-U", DB_USER,
            "-d", DB_NAME,
            "-f", str(tmp_sql),
        ], capture=False)
        if result.returncode != 0:
            print(f"ERROR: Restore failed (exit {result.returncode})", file=sys.stderr)
            return 1
        print("Restore complete.")
    finally:
        tmp_sql.unlink(missing_ok=True)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Personal OS backup/restore utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", help="Create a compressed database backup")
    p_backup.add_argument("--output", default="/opt/personal-os/backups/", help="Output directory")

    p_list = sub.add_parser("list", help="List available backups")
    p_list.add_argument("--dir", default="/opt/personal-os/backups/", help="Backup directory")

    p_verify = sub.add_parser("verify", help="Verify backup integrity")
    p_verify.add_argument("--file", required=True, help="Path to .sql.gz backup file")

    sub.add_parser("check-migrations", help="Check for pending Alembic migrations")

    p_restore = sub.add_parser("restore", help="Restore from backup (dry-run by default)")
    p_restore.add_argument("--file", required=True, help="Path to .sql.gz backup file")
    p_restore.add_argument("--execute", action="store_true", help="Actually perform restore (default: dry-run)")

    args = parser.parse_args()

    dispatch = {
        "backup": cmd_backup,
        "list": cmd_list,
        "verify": cmd_verify,
        "check-migrations": cmd_check_migrations,
        "restore": cmd_restore,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
