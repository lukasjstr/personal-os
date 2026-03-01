# CLAUDE.md

## Project: Personal OS
Personal COO Telegram Bot + Web Dashboard

## Server
- Contabo VPS: 95.111.252.176 (SSH as root)
- PostgreSQL: localhost:5432, DB=personal_os, User=pos_user, PW=personalos2026
- nginx: 443 → 8000, self-signed cert at /etc/nginx/ssl/webhook.pem
- Deploy target: /opt/personal-os/

## After building locally
- Copy files to server: `rsync -avz --exclude venv --exclude __pycache__ --exclude .git ./ root@95.111.252.176:/opt/personal-os/`
- Then on server: set up venv, install deps, run migrations, start service

## Tech Stack
- Python 3.12, FastAPI, uvicorn
- SQLAlchemy 2.0 async + asyncpg
- python-telegram-bot v20+ async
- OpenAI SDK (GPT-4o)
- APScheduler
- PostgreSQL 15

## Git
- user.name=lukasjstr, user.email=lukasjstr@gmail.com
