# Phase 3: Dashboard Overhaul — "Gamifizierte Schaltzentrale"

## VISION
Das Dashboard soll sich anfühlen wie eine **gamifizierte Schaltzentrale** — wie ein RPG Character Sheet trifft auf Notion trifft auf Fitbit. Jeder Datenpunkt soll auf einen Blick verständlich sein, visuell ansprechend, und zum Weiterarbeiten motivieren.

## BESTEHENDE DATEIEN
Lies alle existierenden Dateien bevor du Änderungen machst. Das Projekt besteht aus:
- Backend: `bot/` (Python/FastAPI) — NICHT ändern außer wo explizit genannt
- Dashboard: `dashboard/` (Next.js 14, TypeScript, Tailwind, recharts, lucide-react, date-fns, swr)
- API-Client: `dashboard/src/lib/api.ts`
- Utils: `dashboard/src/lib/utils.ts`

## TEIL 1: TOKEN-FLOW (Telegram → Dashboard)

### 1a. Telegram /token Command
Datei: `bot/telegram/handler.py` + `bot/telegram/commands.py`

Neuer Command `/token`:
```python
async def handle_token(update, context):
    # Generiere API Token für den User
    # Schicke ihn per Telegram DM
    # Format: "🔑 Dein Dashboard Token:\n\n`TOKEN_HIER`\n\nÖffne http://95.111.252.176:3000 und füge den Token ein."
```
Registriere den Handler in `setup_handlers()`.

### 1b. Dashboard TokenGate verbessern
Datei: `dashboard/src/components/TokenGate.tsx`

Design:
- Großes Telegram-Logo/Icon oben
- Text: "Verbinde dein Dashboard"
- Anleitung: "1. Öffne @PersonalOperatingSystem_Bot auf Telegram → 2. Schreib /token → 3. Füge den Token hier ein"
- Eingabefeld mit Paste-Button
- "Verbinden" Button
- Bei Fehler: rote Meldung "Token ungültig — schreib /token an den Bot"
- Clean, dunkel, einladend

## TEIL 2: DASHBOARD HAUPTSEITE — Die Schaltzentrale

Datei: `dashboard/src/app/page.tsx`

### Layout (Top → Bottom):

**Hero-Bereich:**
- Greeting + Datum + Wochentag
- Level/XP-Anzeige (berechnet aus: erledigte Tasks = 10 XP, Workouts = 25 XP, Routinen = 15 XP, Mood-Logs = 5 XP)
- Formel: Level = floor(sqrt(total_xp / 100))
- Progress-Bar bis zum nächsten Level

**4 Stat-Cards (Grid):**
- 🎯 Aktive Ziele (klickbar → /objectives)
- ✅ Offene Tasks (klickbar → /tasks) — rot wenn >15, gelb wenn >10
- 💧 Wasser heute (Kreisdiagramm, Ziel: 3L) — klickbar → /logs?type=water
- 🔥 Streak (Tage in Folge mit mindestens 1 Log) — neues Feature

**Tages-Mission Board (gamifiziert):**
- "Heutige Missionen" mit Checkbox-Style
- Routinen als Daily Quests (✅ oder ☐)
- Top 3 Tasks als Hauptmissionen
- Fortschritts-Ring: X/Y Missionen heute erledigt

**Aktivitäts-Timeline:**
- Letzte 8 Logs, schön formatiert (wie jetzt, aber besser)
- Jeder Log-Typ hat eigene Farbe + Icon
- Relative Zeitangabe ("vor 2 Stunden")

**Wochen-Heatmap:**
- 7-Tage Grid (Mo-So)
- Farb-Intensität basierend auf Anzahl Logs/Aktivitäten pro Tag
- Hover zeigt Details

## TEIL 3: LOGS-SEITE — Activity Feed

Datei: `dashboard/src/app/logs/page.tsx`

### Probleme aktuell:
- Log-Cards sind okay aber unübersichtlich
- Charts sind gut, Layout könnte besser sein

### Verbesserungen:
- **Workout-Karte**: Zeige Exercise-Name groß, dann Details als Chips (80kg, 10 reps, 3 sets)
- **Wasser-Karte**: Fortschrittsring (Tagesgesamt vs. 3L Ziel)
- **Mood-Karte**: Emoji groß, Score als farbige Zahl (grün>7, gelb>4, rot<4)
- **Gratitude-Karte**: Zitat-Style mit Anführungszeichen, rosa Akzent
- **Kein raw JSON anzeigen — NIEMALS**
- Filter-Buttons als Pill-Badges mit Farben (nicht nur Text)

### Charts verbessern:
- Workout-Chart: Stacked Bar nach Exercise-Typ, mit Gewichts-Progression als Line overlay
- Water-Chart: Tägliche Bars mit 3L-Zielline
- Mood-Chart: Area-Chart statt Line, mit Farbverlauf (rot→gelb→grün)

## TEIL 4: OBJECTIVES-SEITE — Goal Tracker

Datei: `dashboard/src/app/objectives/page.tsx`

### Category-Farbsystem (konsistent überall):
```
health     → emerald/green  (#10b981) → 🏥
fitness    → blue           (#3b82f6) → 💪  
finance    → amber/yellow   (#f59e0b) → 💰
learning   → violet/purple  (#8b5cf6) → 📚
personal   → zinc/gray      (#71717a) → 🧠
business   → orange         (#f97316) → 💼
```

### Layout:
- Objectives als große Cards mit Category-Farbbalken links
- "Life Areas" (Objectives ohne Key Results) als kompakte Chips/Tags oben
- Echte Objectives (mit KRs) als expandierbare Cards
- Jeder KR hat Progress-Ring + aktuelle/Ziel-Werte
- Overall-Fortschritt pro Objective als dicke Progress-Bar

## TEIL 5: TASKS-SEITE — Aufgaben-Board

Datei: `dashboard/src/app/tasks/page.tsx`

### Layout:
- Kanban-artige Sections: "Offen" | "In Arbeit" | "Erledigt"
- Jede Task-Card: Priority-Dot (farbig), Titel, Category-Badge, Due-Date
- Filter: Category, Priority, Status
- Gruppierung toggle: nach Category oder nach Status
- Überfällige Tasks rot hervorheben mit ⚠️

## TEIL 6: ROUTINEN-SEITE — Habit Tracker

Datei: `dashboard/src/app/routines/page.tsx`

### Layout:
- Großes Grid mit Routine-Cards
- Jede Card: Titel, Frequenz, Completion-Ring (heute/Woche/Monat)
- Streak-Counter pro Routine
- Wochentags-Grid (Mo-So) zeigt wann erledigt wurde (wie GitHub Contribution Graph)

## TEIL 7: FITNESS-BEREICH (Neues Feature!)

### Neue API Endpoints nötig (bot/api/routes.py):
```python
@router.get("/fitness/summary")
# Letzte Workouts, Volumen-Trend, PRs, Split-Übersicht

@router.get("/fitness/exercises")  
# Unique exercises mit Stats (max weight, frequency, last done)

@router.get("/fitness/prs")
# Personal Records (höchstes Gewicht pro Übung)
```

### Neue Dashboard-Seite: `dashboard/src/app/fitness/page.tsx`

Layout:
- **Workout-Kalender**: Welche Tage trainiert (Heatmap)
- **Exercise-Library**: Alle geloggten Übungen mit Stats
  - Bankdrücken: Max 80kg, 12x trainiert, letztes Mal: gestern
  - Laufen: Ø 42min, 8x diese Woche
- **Volumen-Chart**: Gesamt-Gewicht pro Woche (Trend)
- **PR Board**: Personal Records mit 🏆 Emojis
- **Split-Tracker**: Push/Pull/Legs Rotation sichtbar
- **Letzte Workouts**: Detaillierte Cards der letzten 5 Sessions

## TEIL 8: BRAIN DUMP VERBESSERUNG

### Bot-seitig (bot/ai/prompts.py + bot/ai/tools.py):
Der Bot soll Brain Dumps intelligent kategorisieren:
- Erkennt ob ein Brain Dump eigentlich ein Task ist → erstellt beides
- Erkennt Ideen → taggt sie
- Erkennt Einkaufsartikel → Shopping-Task
- Erkennt Termine → Calendar Event + Brain Dump

### Dashboard (dashboard/src/app/brain-dumps/page.tsx):
- Cards mit AI-Interpretation anzeigen
- Verlinktes Objective anzeigen
- Such- und Filter-Funktion
- Tags/Kategorien

## TEIL 9: KALENDER-VERBESSERUNG

Datei: `dashboard/src/app/calendar/page.tsx`

- Richtiger Monatskalender mit Tagen als Grid
- Events als farbige Dots/Chips im Kalender
- Klick auf Tag zeigt Details
- Heute hervorgehoben
- Event-Typen farbig unterschieden

## TEIL 10: SIDEBAR + NAVIGATION

Datei: `dashboard/src/components/Sidebar.tsx`

- Fitness als neuer Menüpunkt
- Badge-Counter an Tasks (Anzahl offene), Shopping (Anzahl Items)
- Aktiver Menüpunkt hervorgehoben
- Collapse-Toggle für Mobile
- Kleine XP/Level Anzeige unten in der Sidebar

## TECHNISCHE REGELN
1. Keine neuen npm dependencies — nutze nur: next, react, swr, recharts, lucide-react, clsx, date-fns
2. TypeScript strict
3. Dark Mode als Default (bg-zinc-950, cards bg-zinc-900, borders border-zinc-800)
4. Farbsystem konsistent (siehe Category-Farben oben)
5. Mobile-First responsive
6. API-Calls über bestehenden `api.*` Client in `dashboard/src/lib/api.ts`
7. Neue API Types in `dashboard/src/lib/api.ts` hinzufügen
8. Neue API Routes in `bot/api/routes.py` hinzufügen
9. Nach CORS fragen: FastAPI hat CORS Middleware — prüfe ob `http://95.111.252.176:3000` erlaubt ist
10. Alles committen wenn fertig

## NEUE DATEIEN DIE ERSTELLT WERDEN MÜSSEN:
- `dashboard/src/app/fitness/page.tsx`
- `dashboard/src/components/XPBar.tsx` (Level/XP Anzeige)
- `dashboard/src/components/WeekHeatmap.tsx` (7-Tage Aktivitäts-Grid)
- `dashboard/src/components/MissionBoard.tsx` (Tages-Missionen)
- `dashboard/src/components/CircularProgress.tsx` (Ring-Charts)

## DATEIEN DIE GEÄNDERT WERDEN:
- `dashboard/src/app/page.tsx` — komplett überarbeiten
- `dashboard/src/app/logs/page.tsx` — Cards + Charts verbessern
- `dashboard/src/app/objectives/page.tsx` — Category-Farben + Layout
- `dashboard/src/app/tasks/page.tsx` — Kanban + Category + Priority
- `dashboard/src/app/routines/page.tsx` — Habit Tracker Grid
- `dashboard/src/app/calendar/page.tsx` — echtes Kalender-Grid
- `dashboard/src/app/brain-dumps/page.tsx` — bessere Cards
- `dashboard/src/components/Sidebar.tsx` — Fitness + Badges + XP
- `dashboard/src/components/TokenGate.tsx` — besserer Login
- `dashboard/src/lib/api.ts` — neue Types + Endpoints
- `dashboard/src/lib/utils.ts` — Category-Farben als Konstanten
- `bot/api/routes.py` — Fitness Endpoints + Streak Endpoint
- `bot/telegram/handler.py` — /token Command
- `bot/telegram/commands.py` — /token Implementation
