# CLAUDE.md

## Project: Personal OS
Personal COO Telegram Bot + Web Dashboard

## Server
- Contabo VPS: 95.111.252.176 (SSH as root)
- PostgreSQL: localhost:5432, DB=personal_os, User=pos_user, PW=personalos2026
- nginx: 443 → 8000, self-signed cert at /etc/nginx/ssl/webhook.pem
- Deploy target: /opt/personal-os/

## After building locally
- Copy files to server: `rsync -avz --exclude venv --exclude __pycache__ --exclude .git --exclude .env --exclude node_modules --exclude .next ./ root@95.111.252.176:/opt/personal-os/`
- NEVER use `--delete` with rsync (it will wipe the server .env with secrets)
- Then on server: `cd /opt/personal-os && source venv/bin/activate && alembic upgrade head && systemctl restart personal-os`
- Dashboard: `cd /opt/personal-os/dashboard && npm run build && cp -r .next/static .next/standalone/.next/static && cp -r public .next/standalone/public && systemctl restart personal-os-dashboard`
- Note: nginx serves `/_next/static/` directly from `.next/standalone/.next/static/` — so the cp step above is required after every build

## Tech Stack
- Python 3.12, FastAPI, uvicorn
- SQLAlchemy 2.0 async + asyncpg
- python-telegram-bot v20+ async
- OpenAI SDK (GPT-4o)
- APScheduler
- PostgreSQL 15

## Git
- user.name=lukasjstr, user.email=lukasjstr@gmail.com
