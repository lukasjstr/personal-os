#!/bin/bash
# Recovery script for broken encryption state
# Run on server: bash /opt/personal-os/scripts/recover_encryption.sh

set -e

echo "=== Personal OS Recovery Script ==="
echo ""

# 1. Check service status
echo "[1] Service status:"
systemctl is-active personal-os || echo "  !! personal-os is NOT running"
echo ""

# 2. Show recent service logs (last 50 lines)
echo "[2] Recent service logs:"
journalctl -u personal-os -n 50 --no-pager
echo ""

# 3. Check .env file exists
echo "[3] Checking .env file:"
if [ -f /opt/personal-os/.env ]; then
    echo "  .env exists"
    # Check if TELEGRAM_BOT_TOKEN is set and looks valid (numbers:alphanumeric format)
    if grep -q "^TELEGRAM_BOT_TOKEN=" /opt/personal-os/.env; then
        TOKEN_VALUE=$(grep "^TELEGRAM_BOT_TOKEN=" /opt/personal-os/.env | cut -d'=' -f2-)
        TOKEN_LENGTH=${#TOKEN_VALUE}
        echo "  TELEGRAM_BOT_TOKEN is set (length: $TOKEN_LENGTH chars)"
        # Valid bot tokens look like: 1234567890:ABCdefGHIjklMNOpqrSTUvwxyz_-...
        if echo "$TOKEN_VALUE" | grep -qE "^[0-9]+:[A-Za-z0-9_-]{35,}$"; then
            echo "  Token format looks VALID"
        else
            echo "  !! Token format looks INVALID (expected: 123456789:ABCabc...)"
        fi
    else
        echo "  !! TELEGRAM_BOT_TOKEN not found in .env!"
    fi
else
    echo "  !! .env file not found at /opt/personal-os/.env"
fi
echo ""

# 4. Check Python imports (cryptography/fernet installed?)
echo "[4] Checking for unexpected crypto packages:"
if [ -d /opt/personal-os/venv ]; then
    /opt/personal-os/venv/bin/pip list 2>/dev/null | grep -iE "cryptography|fernet|bcrypt|argon|pycrypto" || echo "  No unexpected crypto packages found"
else
    echo "  venv not found at /opt/personal-os/venv"
fi
echo ""

# 5. Check if server code differs from what's expected
echo "[5] Checking auth.py on server:"
if [ -f /opt/personal-os/bot/api/auth.py ]; then
    grep -n "encrypt\|decrypt\|hash\|bcrypt\|fernet" /opt/personal-os/bot/api/auth.py || echo "  No encryption code found in auth.py (good)"
else
    echo "  !! auth.py not found"
fi
echo ""

# 6. Reset API tokens in database (so users can regenerate with /token)
echo "[6] Resetting all API tokens in database..."
echo "  This will clear all stored tokens - users must run /token in Telegram to get a new one"
read -p "  Reset all api_tokens? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PGPASSWORD=personalos2026 psql -U pos_user -d personal_os -h localhost -c "UPDATE users SET api_token = NULL;"
    echo "  Done! All tokens cleared."
else
    echo "  Skipped."
fi
echo ""

# 7. Restart service
echo "[7] Restarting personal-os service..."
read -p "  Restart now? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl restart personal-os
    sleep 3
    systemctl status personal-os --no-pager -l | tail -20
else
    echo "  Skipped."
fi

echo ""
echo "=== Recovery steps complete ==="
echo ""
echo "Next steps:"
echo "  1. If TELEGRAM_BOT_TOKEN was invalid, fix it in /opt/personal-os/.env"
echo "  2. Restart: systemctl restart personal-os"
echo "  3. Test Telegram: send /start to your bot"
echo "  4. Get new API token: send /token to your bot"
echo "  5. Enter new token in the dashboard"
