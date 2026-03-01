#!/usr/bin/env bash
# Personal OS setup script for Contabo VPS
set -euo pipefail

DEPLOY_DIR="/opt/personal-os"
VENV_DIR="$DEPLOY_DIR/venv"
SERVICE_FILE="/etc/systemd/system/personal-os.service"

echo "=== Personal OS Setup ==="

# 1. Install system dependencies
apt-get update -q
apt-get install -y -q python3.12 python3.12-venv python3-pip libpq-dev git postgresql-client

# 2. Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    python3.12 -m venv "$VENV_DIR"
    echo "Virtual environment created"
fi

# 3. Install Python dependencies
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$DEPLOY_DIR/requirements.txt" -q
echo "Dependencies installed"

# 4. Run database migrations
cd "$DEPLOY_DIR"
"$VENV_DIR/bin/alembic" upgrade head
echo "Database migrations applied"

# 5. Copy systemd service
if [ -f "$DEPLOY_DIR/personal-os.service" ]; then
    cp "$DEPLOY_DIR/personal-os.service" "$SERVICE_FILE"
    systemctl daemon-reload
    systemctl enable personal-os
    echo "Systemd service installed"
fi

# 6. Start/restart service
systemctl restart personal-os
systemctl status personal-os --no-pager

echo "=== Setup Complete ==="
echo "Logs: journalctl -u personal-os -f"
