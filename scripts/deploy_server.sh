#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/personal-os"
SSH_KEY="/root/.ssh/id_ed25519_personal_os"
export GIT_SSH_COMMAND="ssh -i ${SSH_KEY} -o IdentitiesOnly=yes"

cd "$REPO_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: $REPO_DIR/.env missing — aborting to protect runtime secrets" >&2
  exit 1
fi

echo "==> Fetching latest main"
git fetch origin
git checkout main
git pull --ff-only origin main

echo "==> Running DB migration"
venv/bin/alembic upgrade 018

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
