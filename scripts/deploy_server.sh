#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/personal-os"
SSH_KEY="/root/.ssh/id_ed25519_personal_os"
export GIT_SSH_COMMAND="ssh -i ${SSH_KEY} -o IdentitiesOnly=yes"

cd "$REPO_DIR"

# ---------------------------------------------------------------------------
# Preflight checks — fail fast before touching anything
# ---------------------------------------------------------------------------

echo "==> Preflight checks"

# 1. .env must exist on server (never committed to repo)
if [[ ! -f .env ]]; then
  echo "ERROR: $REPO_DIR/.env missing — aborting to protect runtime secrets" >&2
  exit 1
fi

# 2. Required env keys must be present in .env
for key in TELEGRAM_BOT_TOKEN TELEGRAM_WEBHOOK_URL OPENAI_API_KEY; do
  if ! grep -qE "^${key}=" .env; then
    echo "ERROR: required key '${key}' not found in .env" >&2
    exit 1
  fi
done

# 3. Alembic must have exactly one head (no branched history)
HEADS=$(venv/bin/alembic heads 2>/dev/null | grep -c "(head)" || true)
if [[ "$HEADS" -ne 1 ]]; then
  echo "ERROR: alembic reports ${HEADS} head(s) — expected exactly 1. Resolve before deploying." >&2
  echo "       Run: venv/bin/alembic heads" >&2
  exit 1
fi

# 4. Disk space — require at least 500 MB free on /
FREE_KB=$(df -k / | awk 'NR==2 {print $4}')
if [[ "$FREE_KB" -lt 512000 ]]; then
  echo "ERROR: less than 500 MB free on / (${FREE_KB} kB) — clean up before deploying" >&2
  exit 1
fi

echo "    .env keys: OK"
echo "    alembic heads: 1 (clean)"
echo "    disk free: $(( FREE_KB / 1024 )) MB"

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

echo "==> Fetching latest main"
git fetch origin
git checkout main
git pull --ff-only origin main

echo "==> Running DB migration"
venv/bin/alembic upgrade head

echo "==> Restarting API"
systemctl restart personal-os

echo "==> Building dashboard"
cd "$REPO_DIR/dashboard"
npm run build
systemctl restart personal-os-dashboard

sleep 3

echo "==> Health checks"
echo "BOT=$(systemctl is-active personal-os)"
echo "DASH=$(systemctl is-active personal-os-dashboard)"
printf "HEALTH="; curl -s http://localhost:8000/api/health; echo
printf "DASH_HTTP="; curl -I -s http://localhost:3001 | head -n 1
