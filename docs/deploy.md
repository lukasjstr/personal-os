# Deploy & Rollback — Personal OS

Server: `95.111.252.176` (SSH as root)
Deploy target: `/opt/personal-os/`

---

## Standard deploy

```bash
# 1. Push changes locally
git push origin main

# 2. Sync files to server (never syncs venv, __pycache__, .git, or .env)
rsync -avz --exclude venv --exclude __pycache__ --exclude .git --exclude .env \
  ./ root@95.111.252.176:/opt/personal-os/

# 3. SSH and run deploy script
ssh root@95.111.252.176 "bash /opt/personal-os/scripts/deploy_server.sh"
```

The deploy script runs preflight checks, migrates the DB, restarts both services, and prints a health summary. It will abort with an error if:
- `.env` is missing or lacks required keys
- Alembic has more than one head (branched migration history)
- Less than 500 MB free on disk

---

## Rollback

### API service rollback (no schema change)

```bash
ssh root@95.111.252.176
cd /opt/personal-os

# Roll back to a specific git commit
git log --oneline -10           # find the commit you want
git checkout <commit-sha>       # detach HEAD to that commit
systemctl restart personal-os
systemctl restart personal-os-dashboard
```

To return to main after testing:

```bash
git checkout main
```

### Database rollback (migration already ran)

```bash
ssh root@95.111.252.176
cd /opt/personal-os

# Roll back one migration
venv/bin/alembic downgrade -1

# Roll back to a specific revision
venv/bin/alembic downgrade 018

# Check current state
venv/bin/alembic current
venv/bin/alembic history --verbose
```

> **Warning:** downgrading destroys any data that the migration added (new columns, tables). Take a backup first if in doubt.

### Full emergency rollback

```bash
# 1. Take a backup of current state
cd /opt/personal-os
venv/bin/python scripts/backup_restore.py backup

# 2. Downgrade DB to last known-good revision
venv/bin/alembic downgrade <revision>

# 3. Restore previous code
git checkout <known-good-commit>

# 4. Restart services
systemctl restart personal-os personal-os-dashboard

# 5. Verify
systemctl is-active personal-os personal-os-dashboard
curl -s http://localhost:8000/api/health
```

---

## Useful commands on the server

```bash
# Live logs
journalctl -u personal-os -f
journalctl -u personal-os-dashboard -f

# Service status
systemctl status personal-os personal-os-dashboard

# Check migration state
cd /opt/personal-os && venv/bin/alembic current
cd /opt/personal-os && venv/bin/alembic heads

# Health endpoints
curl -s http://localhost:8000/api/health
curl -I http://localhost:3001
```

---

## .env management

`.env` is **never committed**. It lives only at `/opt/personal-os/.env` on the server.

Required keys:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_URL`
- `OPENAI_API_KEY`

If you need to update a value: edit `.env` directly on the server, then `systemctl restart personal-os`.

---

## Adding a new migration

```bash
# Locally — generate a new revision
venv/bin/alembic revision -m "describe_change" --rev-id=021

# Edit the generated file in bot/database/migrations/versions/
# Then test locally, commit, and deploy
```

Always verify `alembic heads` shows exactly one head before deploying.
