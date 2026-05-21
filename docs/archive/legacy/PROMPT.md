# Personal OS — Phase 1: Backend + Telegram Bot

Lies SPEC.txt für die vollständige Projekt-Spezifikation. Du arbeitest in /opt/personal-os/.

## ÜBERBLICK
Personal OS = KI-gesteuerter persönlicher COO über Telegram. User schickt alles rein (Text, Bilder, Voice), das System versteht, kategorisiert, priorisiert und antwortet intelligent.

## WAS DU BAUEN SOLLST

### 1. PROJEKTSTRUKTUR
Erstelle die komplette Dateistruktur wie in SPEC.txt beschrieben (personal-os/bot/...).
Erstelle requirements.txt mit allen Dependencies.

### 2. DATABASE MODELS (SQLAlchemy 2.0 async)
Erstelle alle Models wie in SPEC.txt:
- User, Objective, KeyResult, Task, Log, Routine, RoutineCompletion, CalendarEvent, BrainDump, Conversation
- Nutze asyncpg + async SQLAlchemy
- Connection string aus .env: postgresql+asyncpg://pos_user:personalos2026@localhost:5432/personal_os
- Alembic für Migrations (erstelle initial migration und führe sie aus)

### 3. TELEGRAM BOT
- python-telegram-bot v20+ (async)
- Webhook-Modus auf POST /webhook/telegram
- Webhook wird beim App-Start registriert (mit self-signed cert: /etc/nginx/ssl/webhook.pem)
- Verarbeitet: text, photo, voice
- Jede Nachricht wird in conversations gespeichert
- get_or_create User bei jeder Nachricht

### 4. OPENAI INTEGRATION (NICHT Anthropic!)
- Nutze OpenAI Python SDK (`openai`)
- Model: `gpt-4o` für Chat, `gpt-4o-mini` für einfache Tasks
- Function Calling / Tool Use
- System Prompt aus SPEC.txt (der COO Prompt)
- Context Builder lädt aus DB: aktive OKRs, heutige Tasks, letzte Logs, offene Routinen, letzte 5 Conversations
- 17 Tools wie in SPEC.txt definiert (create_objective, log_workout, etc.)

### 5. CRON JOBS (APScheduler)
- 06:30: Morning Brief → sendet Tagesplan via Telegram
- 21:00: Evening Review → sendet Tages-Zusammenfassung
- Routine-Reminders basierend auf Cron-Schedules

### 6. iCAL FEED
- GET /cal/{user_token}.ics
- Generiert iCal aus calendar_events + routine schedules
- Für Google Cal / Apple Cal Abo

### 7. REST API (für Dashboard)
- GET /api/objectives — Alle OKRs mit Key Results
- GET /api/tasks — Offene Tasks
- GET /api/logs?type=workout&days=30 — Logs filtern
- GET /api/routines — Routinen mit Completion-Status
- GET /api/brain-dumps — Alle Brain Dumps
- GET /api/dashboard — Aggregierte Dashboard-Daten
- POST /api/auth/telegram — Telegram Login (Magic Link Token)
- Alle Endpoints brauchen User-Auth (Bearer Token)

### 8. MIGRATION VON CLOUDBRAIN
Erstelle ein Script `scripts/migrate_cloudbrain.py`:
- Liest /data/db/cloudbrain.db (SQLite)
- Migriert: life_areas → objectives (mapped), goals → objectives, tasks → tasks, entries → logs
- Behält alle Daten bei

## TECHNISCHE DETAILS
- Python 3.12 (bereits installiert)
- Virtualenv in /opt/personal-os/venv
- .env liegt schon in /opt/personal-os/.env
- PostgreSQL läuft auf localhost:5432 (DB: personal_os, User: pos_user)
- Telegram Webhook cert: /etc/nginx/ssl/webhook.pem
- nginx reverse proxy auf port 443 → localhost:8000
- ALLES async (asyncio, async SQLAlchemy, async telegram)
- structlog für Logging
- Type Hints überall

## NACH DEM BUILD
1. `pip install -r requirements.txt` im venv
2. Alembic migration ausführen
3. App starten und testen dass der Bot antwortet
4. Erstelle ein systemd service file: /etc/systemd/system/personal-os.service

## GIT
```
cd /opt/personal-os
git init
git add -A
git commit -m "feat: Personal OS Phase 1 — Backend, Telegram Bot, API, iCal, Migration"
```

Erstelle ALLE Dateien mit vollständigem, funktionsfähigem Code.
Kein Placeholder. Kein "TODO". Alles implementiert.
