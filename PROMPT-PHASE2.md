# Personal OS — Phase 2: Web Dashboard

Lies SPEC.txt für die vollständige Projekt-Spezifikation. Das Backend (Phase 1) läuft bereits.

## ÜBERBLICK
Baue ein Next.js Web-Dashboard das die bestehende FastAPI REST API nutzt. Das Dashboard zeigt alle Personal OS Daten übersichtlich an.

## BESTEHENDE API
Die REST API läuft auf dem gleichen Server (Port 8000). Alle Endpoints sind bereits gebaut:

### Endpoints (siehe bot/api/routes.py):
- `GET /api/objectives/{user_id}` — Alle Objectives/Goals
- `GET /api/tasks/{user_id}` — Alle Tasks  
- `GET /api/tasks/{user_id}?status=todo` — Tasks filtern
- `GET /api/logs/{user_id}` — Alle Logs
- `GET /api/logs/{user_id}?log_type=workout` — Logs filtern
- `GET /api/routines/{user_id}` — Alle Routinen
- `GET /api/calendar/{user_id}` — Kalender-Events
- `GET /api/brain-dumps/{user_id}` — Brain Dumps
- `GET /api/progress/{user_id}` — Fortschritts-Report
- `GET /api/ical/{user_id}` — iCal Feed
- `GET /health` — Health Check

## WAS DU BAUEN SOLLST

### 1. Next.js App (App Router, TypeScript, Tailwind CSS)
Erstelle im Ordner `dashboard/` innerhalb des Projekts.

### 2. Seiten / Views:
- **Dashboard (/)** — Übersicht: Tages-Prioritäten, aktive Objectives, offene Tasks, letzte Logs
- **Objectives (/objectives)** — Alle Ziele mit Status, Key Results, Fortschrittsbalken
- **Tasks (/tasks)** — Task-Liste mit Filter (status, priority), Drag & Drop für Status-Änderung
- **Logs (/logs)** — Timeline aller Logs (Workout, Mood, Water etc.) mit Filtern
- **Routinen (/routines)** — Routine-Tracker mit Streak-Anzeige
- **Kalender (/calendar)** — Kalender-Ansicht (Monats/Wochen-View)
- **Brain Dumps (/brain-dumps)** — Alle Brain Dumps durchsuchbar
- **Dokumente (/docs)** — Statische Dokumente wie Morgenroutine, Einkaufsliste etc.

### 3. Design
- Dark Mode als Default, Light Mode Toggle
- Modern, clean, minimalistisch
- Responsive (Mobile-First, da Hauptnutzung am Handy)
- Tailwind CSS + shadcn/ui Komponenten
- Emojis als visuelle Akzente (passend zum Telegram-Bot Style)

### 4. Features
- Real-time Daten von der API (SWR oder React Query)
- Keine Auth nötig für Phase 2 (kommt später) — user_id=1 hardcoded erstmal
- Charts für Fortschritt (z.B. Workouts pro Woche, Mood-Verlauf)
- Quick-Actions: Task erstellen, als erledigt markieren

### 5. Deployment
- Dockerfile für das Dashboard (eigenständig)
- Nginx-Config um /dashboard auf den Next.js Container zu routen
- Oder: Standalone Next.js auf Port 3000, Nginx reverse proxy

## WICHTIG
- Das Backend (FastAPI) änderst du NICHT
- API Base URL konfigurierbar via Environment Variable
- TypeScript strict mode
- Erstelle `dashboard/package.json`, `dashboard/tsconfig.json` etc.
- Nutze `npx create-next-app@latest dashboard --typescript --tailwind --app --src-dir`
