# ROADMAP – Personal Operating System (POS)

## Aktueller Stand

### ✅ Committed
- **Phase 1**: Backend (FastAPI), Telegram Bot, API, iCal, Migration, PostgreSQL
- **Phase 2**: Next.js Dashboard, 15 DB Tables, 21 AI Tools, Toggles, Shopping, Next-Action
- **Phase 3**: Gamified Dashboard (XP/Levels, Token Flow, Log-Formatting, Stat Cards, Heatmap, Mission Board)
- Chat History Context, Brain Dump Processing, Mobile Responsive

### 🔧 Uncommitted Changes (in working tree)
+1256 Zeilen in: routes.py, morning_brief, evening_review, reminders, scheduler, weekly_reflection_trigger, api.ts
Neue Endpoints: weekly-summary, priorities, routine-history, task/routine complete, brief/today

### 📝 Phase 5 Prompt (geschrieben, NICHT implementiert)
Deep Relations, Calendar Planning, Fitness Splits, Routine Tageszeiten, Shopping Upgrade, Dashboard UX

## Architektur

```
User → Telegram Bot (python-telegram-bot)
         ↕ OpenAI GPT-4o (AI Tools)
         ↕ PostgreSQL (15 Tabellen, Contabo VPS)
         ↕ FastAPI REST API
               ↕
         Next.js Dashboard (Port 3000)

Alles auf EINEM Contabo VPS (95.111.252.176)
- PostgreSQL: localhost:5432
- FastAPI: Port 8000 (nginx reverse proxy, HTTPS)
- Dashboard: Port 3000
```

**Warum kein Supabase/Vercel?**
- Alles ist self-hosted auf EINEM Server → volle Kontrolle, keine Vendor-Abhängigkeit
- PostgreSQL direkt → schneller, billiger, kein Overhead
- Telegram Bot braucht persistent connection → passt nicht zu Serverless (Vercel)
- APScheduler für Cron Jobs (Morning Brief, Reminders) → braucht laufenden Prozess
- Für 1-10 User ist das perfekt. Skalierung kommt wenn nötig.

**Daten-Speicherung:**
- Alles in PostgreSQL (15 Tabellen), kein Prompt-Bloat
- AI-Calls senden nur relevanten Kontext (~2-4k Tokens)
- Chat History: letzte 20 Messages als Kontext
- Pro User: ~5-20 DB Queries pro Interaktion

**Prompt-Länge:**
- System Prompt: ~3k Tokens (fix)
- User Context (Goals, Tasks, Routines, letzte Logs): ~2-4k Tokens (dynamisch geladen)
- Gesamt pro Call: ~6-8k Tokens → weit unter Limit
- Skaliert linear pro User, aber jeder User hat eigenen Context

---

## Phase 4.5: Uncommitted Changes committen & deployen

### Prompt 4.5 – Stabilize & Deploy
```
Lies CLAUDE.md und SPEC_V2.txt.

Im Working Tree gibt es uncommitted Changes in:
- bot/api/routes.py (weekly-summary, priorities, routine-history, task/routine complete, brief/today endpoints)
- bot/jobs/evening_review.py, morning_brief.py, reminders.py, scheduler.py, weekly_reflection_trigger.py
- bot/main.py
- dashboard/src/lib/api.ts

1. Prüfe ob alle Änderungen konsistent sind und zusammenpassen
2. Teste: Starte den Bot lokal (python -m bot.main) und prüfe ob er startet
3. Teste die neuen API-Endpoints einzeln mit curl
4. Wenn alles funktioniert: commit mit "feat: enhanced jobs, weekly summary, priorities, routine history"
5. Erstelle die Alembic Migration falls DB-Änderungen nötig sind

NICHT deployen, nur committen und testen.
```

---

## Phase 5: Deep Relations & Smart Planning (aufgeteilt in Einzel-Prompts)

### Prompt 5.1 – Task-Objective Deep Relations
```
Lies CLAUDE.md und SPEC_V2.txt.

Implementiere Task-Objective Verknüpfungen:

1. ALEMBIC MIGRATION erstellen:
   - Task.objective_id: FK → objectives (nullable)
   - Task.parent_task_id: FK → tasks (nullable, für Sub-Tasks)
   - Task.blocked_by_task_id: FK → tasks (nullable)
   - Objective.parent_objective_id: FK → objectives (nullable, für Goal → Sub-Objective)

2. MODELS updaten (bot/database/models.py):
   - Relationships hinzufügen mit back_populates
   - Task.objective, Task.parent_task, Task.blocked_by
   - Objective.parent_objective, Objective.sub_objectives, Objective.tasks

3. AI TOOLS (bot/ai/tools.py):
   - create_task: Neuer Parameter objective_id (optional)
   - create_objective: Nach Erstellung automatisch 3-5 Tasks vorschlagen und erstellen
   - suggest_tasks_for_objective: Neues Tool

4. AI PROMPT (bot/ai/prompts.py):
   Ergänze SYSTEM_PROMPT:
   "TASK-ZIEL ZUORDNUNG:
   - JEDE neue Task sollte einem Objective zugeordnet werden wenn möglich
   - Wenn ein Goal/Objective erstellt wird: Erstelle automatisch 3-5 konkrete Tasks
   - Wenn eine Task ohne Objective erstellt wird: Frage ob sie zugeordnet werden soll
   - Wenn alle Tasks eines Objectives erledigt sind: Feiere und frage nach neuen"

5. DASHBOARD (dashboard/src/app/objectives/page.tsx):
   - Objective-Card zeigt zugehörige Tasks als Checklist
   - Progress = erledigte Tasks / alle Tasks
   - Aufklappbar: Tasks unter Objective sehen

6. DASHBOARD (dashboard/src/app/tasks/page.tsx):
   - Task zeigt Objective als farbigen Badge
   - Filter nach Objective
   - Blockierte Tasks ausgegraut
   - Sub-Tasks eingerückt

Commit: "feat: task-objective deep relations with auto-task generation"
```

### Prompt 5.2 – Kalender & Tagesplanung
```
Lies CLAUDE.md.

Erweitere den Kalender:

1. AI TOOL (bot/ai/tools.py):
   - plan_my_day: Neues Tool
     1. Lade offene Tasks sortiert nach Priority + Due Date
     2. Lade heutige Routinen
     3. Lade Kalender-Events
     4. Erstelle Zeitplan mit konkreten Blöcken
     5. Erstelle Calendar Events für jeden Block
     6. Sende Plan als übersichtliche Nachricht

2. AI PROMPT ergänzen:
   "TAGESPLANUNG: Wenn User 'Plan meinen Tag' sagt → plan_my_day aufrufen"

3. DASHBOARD (dashboard/src/app/calendar/page.tsx):
   - Tagesansicht mit Zeitblöcken (nicht nur Monat)
   - Wochenansicht
   - Events anklickbar → Detail mit Notizen
   - Notiz-Feld pro Event (editierbar)

4. API:
   - PUT /api/calendar/{id} (Event updaten)
   - POST /api/calendar/{id}/notes (Notiz hinzufügen)

Commit: "feat: day planning tool and enhanced calendar views"
```

### Prompt 5.3 – Fitness Splits & Workout-Plan
```
Lies CLAUDE.md.

1. ALEMBIC MIGRATION:
   CREATE TABLE fitness_splits (
     id SERIAL PRIMARY KEY,
     user_id INTEGER REFERENCES users(id),
     name TEXT NOT NULL,
     exercises JSONB NOT NULL,
     day_of_week INTEGER,
     order_in_rotation INTEGER,
     created_at TIMESTAMP DEFAULT now()
   );

2. MODELS: FitnessSplit Klasse in models.py

3. AI TOOLS:
   - create_fitness_split: Name + Übungen + Wochentag
   - get_fitness_plan: Zeigt aktuelle Split-Rotation
   - log_workout schon vorhanden → erweitern: Split zuordnen

4. AI PROMPT ergänzen:
   "FITNESS: Erkenne Split-Referenzen (Push/Pull/Leg Day). Schlage nächsten Split vor. Morning Brief: 'Heute ist Push Day: Bankdrücken, Schulterdrücken, Trizeps'"

5. DASHBOARD (dashboard/src/app/fitness/page.tsx):
   - Split-Übersicht: Welcher Split wann
   - Pro Split: Übungen + letztes Gewicht + Ziel
   - Progression-Chart pro Übung
   - "Nächstes Workout" Empfehlung

6. API:
   - GET /api/fitness/splits
   - POST /api/fitness/splits
   - GET /api/fitness/progression/{exercise}

Commit: "feat: fitness splits with progression tracking"
```

### Prompt 5.4 – Routinen: Tageszeiten + Einkaufsliste Upgrade
```
Lies CLAUDE.md.

1. ALEMBIC MIGRATION:
   - Routine: time_of_day TEXT (morning/midday/evening/anytime), sort_order INTEGER
   - Shopping Defaults Tabelle:
     CREATE TABLE shopping_defaults (
       id SERIAL PRIMARY KEY,
       user_id INTEGER REFERENCES users(id),
       title TEXT NOT NULL,
       category TEXT,
       active BOOLEAN DEFAULT true
     );

2. ROUTINEN-TAGESZEITEN:
   - Bot: Routinen nach Tageszeit gruppiert
   - Morning Brief zeigt nur Morgen-Routinen
   - Mittags-Reminder (12:00) → Mittags-Routinen
   - Abend-Reminder (18:00) → Abend-Routinen
   
   Dashboard (dashboard/src/app/routines/page.tsx):
   - 3 Sektionen: 🌅 Morgens | ☀️ Mittags | 🌙 Abends
   - Checkbox direkt im Dashboard

3. EINKAUFSLISTE:
   - AI erkennt: "Standard-Einkaufsliste" → lade Defaults
   - Kategorien: 🥬 Gemüse | 🥩 Fleisch | 🥫 Basics | 🧴 Haushalt
   - Items die 3x gekauft werden → als Standard vorschlagen
   
   Dashboard (dashboard/src/app/shopping/page.tsx):
   - Kategorien als Sektionen
   - Standard-Items mit ⭐
   - "Standard-Liste laden" Button

4. API:
   - GET/POST /api/shopping/defaults
   - POST /api/shopping/load-defaults

Commit: "feat: routine time-of-day groups and shopping defaults"
```

---

## Phase 6: Dashboard Mehrwert & CRUD (3 Prompts)

### Prompt 6.1 – Dashboard Schnellübersicht mit echtem Mehrwert
```
Lies CLAUDE.md.

Überarbeite dashboard/src/app/page.tsx:

1. QUICK STATS erweitern:
   - 🎯 Goal-Fortschritt: Gesamtprogress aller aktiven Objectives (%)
   - 🔥 Streak: Längste aktive Streak + Trend vs letzte Woche
   - ⚡ Energie/Mood: Letzter Mood-Score oder "Noch nicht getrackt" als CTA
   - 📊 Woche: X von Y Tasks erledigt mit Progress Ring
   - 💧 Wasser heute: Liter getrackt (Kreisdiagramm vs 3L Ziel)

2. SCHNELLZUGRIFF-KARTEN (klickbar, leiten weiter):
   - "💪 Dein Fitnessplan" → /fitness (zeigt "Nächstes Workout: Push Day")
   - "🌅 Deine Routine" → /routines (zeigt "3 von 7 erledigt")
   - "🧠 AI Coach" → Telegram Deep Link
   - "📥 Brain Dump" → /brain-dumps
   - "🛒 Einkaufsliste" → /shopping (zeigt "5 Items offen")
   Jede Karte zeigt 1-2 relevante Live-Zahlen.

3. MOBILE: Karten stacken vertikal, Quick Stats horizontal scrollbar.

Commit: "feat: enhanced dashboard with quick stats and smart shortcuts"
```

### Prompt 6.2 – Dokumente/Einträge bearbeiten & löschen
```
Lies CLAUDE.md.

Füge überall Edit + Delete hinzu:

1. OBJECTIVES (dashboard/src/app/objectives/page.tsx):
   - Edit Button → Modal: Title, Category, Description, Target Date
   - Delete Button → Confirmation Dialog → Cascade Delete (Objective + KRs + Tasks)
   - API: PUT /api/objectives/{id}, DELETE /api/objectives/{id}

2. TASKS (dashboard/src/app/tasks/page.tsx):
   - Edit Button → Modal: Title, Category, Priority, Due Date, Status, Objective-Zuordnung
   - Delete Button → Confirmation
   - API: PUT /api/tasks/{id}, DELETE /api/tasks/{id}

3. ROUTINES (dashboard/src/app/routines/page.tsx):
   - Edit Button → Modal: Name, Frequency, Time of Day, Active toggle
   - Delete Button → Confirmation
   - API: PUT /api/routines/{id}, DELETE /api/routines/{id}

4. BRAIN DUMPS (dashboard/src/app/brain-dumps/page.tsx):
   - Edit + Delete Buttons
   - API: PUT /api/brain-dumps/{id}, DELETE /api/brain-dumps/{id}

5. LOGS (dashboard/src/app/logs/page.tsx):
   - Delete Button (zum Korrigieren falscher Einträge)
   - API: DELETE /api/logs/{id}

Pattern: Immer Confirmation Dialog vor Delete. Toast nach Aktion. Optimistic UI.

Commit: "feat: full CRUD for objectives, tasks, routines, brain dumps, logs"
```

### Prompt 6.3 – Einstellungen: Name ändern & Profil
```
Lies CLAUDE.md.

Erweitere dashboard/src/app/settings/page.tsx:

1. NAME ÄNDERN:
   - Feld "Dein Name" (vorausgefüllt aus User.full_name oder User.telegram_name)
   - Speichern Button → PUT /api/settings/profile
   - Name sofort im Header aktualisiert

2. WEITERE SETTINGS:
   - Telegram Username (read-only)
   - Alle Toggles visuell (Priorities, Review, Proactive, Reflection) — aktuell per /toggle
   - Zeiten ändern (Morning Brief, Evening Review) — aktuell per /times
   - Dimensionen/Kategorien-Gewichtung (Slider)
   - Daten-Export (JSON-Download aller eigenen Daten)
   - Account löschen (mit Confirmation)

3. API:
   - PUT /api/settings/profile (name, etc.)
   - GET /api/settings/export (JSON-Export)
   - GET /api/settings (alle Settings mit Toggles + Zeiten)
   - PUT /api/settings (Toggles + Zeiten updaten)

Commit: "feat: settings page with profile editing and data export"
```

---

## Phase 7: Gamification & Meilensteine (2 Prompts)

### Prompt 7.1 – Achievements & Meilensteine
```
Lies CLAUDE.md.

1. ALEMBIC MIGRATION:
   CREATE TABLE achievements (
     id SERIAL PRIMARY KEY,
     key TEXT UNIQUE NOT NULL,
     title TEXT NOT NULL,
     description TEXT NOT NULL,
     emoji TEXT NOT NULL,
     category TEXT NOT NULL,
     xp_reward INTEGER DEFAULT 0,
     condition_type TEXT NOT NULL,
     condition_value INTEGER NOT NULL
   );

   CREATE TABLE user_achievements (
     id SERIAL PRIMARY KEY,
     user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
     achievement_id INTEGER REFERENCES achievements(id),
     unlocked_at TIMESTAMP DEFAULT now(),
     UNIQUE(user_id, achievement_id)
   );

   INSERT INTO achievements (seed data):
   - 🎓 "Erster Schritt" – Onboarding abgeschlossen (condition: milestone, 1)
   - ✅ "Macher" – 10 Tasks erledigt (count, 10)
   - 💯 "Hundertschaft" – 100 Tasks erledigt (count, 100)
   - 🎯 "Zielstrebig" – Erstes Objective erstellt (count, 1)
   - 🏅 "Key Result Knacker" – Erstes KR zu 100% (count, 1)
   - 🔥 "Feuer gefangen" – 7-Tage-Streak (streak, 7)
   - 💎 "Diamant-Disziplin" – 30-Tage-Streak (streak, 30)
   - 🌟 "Legende" – 100-Tage-Streak (streak, 100)
   - 🪞 "Selbstreflektiert" – Erste Reflection (count, 1)
   - 💧 "Hydration Hero" – 100 Liter Wasser getrackt (count, 100)
   - 🎯 "Perfekte Woche" – 100% Task Completion in einer Woche (milestone, 1)
   - 🔄 "Comeback Kid" – Nach 7 Tagen Pause wieder aktiv (milestone, 1)
   - 🧠 "Brain Dumper" – 50 Brain Dumps (count, 50)
   - 💪 "Gym Rat" – 100 Workouts geloggt (count, 100)

2. ENGINE (bot/core/achievements.py):
   - check_achievements(user_id, session): Prüft alle Conditions, unlocked neue
   - Returns: Liste neu freigeschalteter Achievements
   - Aufrufen nach: Task complete, Log erstellen, Reflection, Brain Dump

3. TELEGRAM:
   - Bei neuem Achievement: Bot sendet "🏆 ACHIEVEMENT UNLOCKED!\n{emoji} {title}\n{description}\n+{xp} XP!"

4. API:
   - GET /api/achievements (alle + unlocked Status)
   - GET /api/achievements/recent (letzte 5 freigeschaltete)

5. DASHBOARD (neue Seite dashboard/src/app/achievements/page.tsx):
   - Grid aller Achievements
   - Freigeschaltete: farbig mit Datum
   - Gesperrte: ausgegraut mit Hint
   - Progress bei Count-basierten (z.B. "47/100 Tasks")
   - Navigation: Link in Sidebar

Commit: "feat: achievement system with auto-unlock and telegram notifications"
```

### Prompt 7.2 – Gamification Dashboard Integration
```
Lies CLAUDE.md.

1. DASHBOARD HEADER (dashboard/src/app/layout.tsx oder page.tsx):
   - Level + XP-Bar neben Username
   - Format: "Level 5 | ████░░ 340/600 XP"

2. DASHBOARD MAIN (dashboard/src/app/page.tsx):
   - Neue Karte "🏆 Letzte Erfolge" → 3 neueste Achievements
   - "Alle anzeigen →" Link zu /achievements

3. STREAK CELEBRATIONS:
   - 7er, 14er, 30er Streaks: Spezielle Icons (🔥→🔥🔥→🔥🔥🔥)

4. TELEGRAM BOT:
   - Morning Brief: "Dein Streak: 🔥 14 Tage! Nächster Meilenstein: 💎 bei 30 Tagen"
   - Weekly Reflection: Section "Deine Erfolge diese Woche" mit neuen Achievements

Commit: "feat: gamification UI in dashboard header, main page, and telegram"
```

---

## Phase 8: Smart Reflection & Automation (2 Prompts)

### Prompt 8.1 – Erweiterte Reflexion mit Prioritäten & AI-Vorschlägen
```
Lies CLAUDE.md.

Erweitere die Weekly Reflection (bot/core/weekly_reflections.py + bot/jobs/weekly_reflection_trigger.py):

1. NEUE REFLEXIONS-FRAGEN (Telegram-Flow):
   - Frage 6: "Welche 3 Lebensbereiche willst du nächste Woche priorisieren?"
     → Bot zeigt Kategorien mit aktuellem Fortschritt
     → User wählt Top 3
     → Speichere in weekly_priorities
   
   - Frage 7: "Was sind deine 1-3 wichtigsten Ziele für die nächsten 4 Wochen?"
     → Freitext
     → AI generiert konkrete Objectives + Tasks daraus
     → Bot fragt: "Soll ich diese Ziele für dich anlegen?"
     → Bei Ja: Erstelle Objectives + Tasks automatisch

2. AI-ZUSAMMENFASSUNG am Ende:
   - Input: Alle Antworten + Wochendaten + Patterns
   - AI generiert:
     a) Top 3 Empfehlungen für nächste Woche
     b) Vorgeschlagene Ziel-Anpassungen
     c) Neue Goal-Vorschläge (basierend auf Dimension-Lücken)
     d) Personalisierte Motivations-Nachricht
   - Bot sendet alles formatiert

3. DASHBOARD (dashboard/src/app/docs/page.tsx oder neue Reflections-Seite):
   - Liste aller Reflections mit AI-Analyse
   - Trend: Zufriedenheit über Wochen (Chart)

Commit: "feat: enhanced reflection with priority setting and AI goal suggestions"
```

### Prompt 8.2 – Automatische Daily Suggestions
```
Lies CLAUDE.md.

1. NEUER SCHEDULED JOB (bot/jobs/daily_suggestions.py):
   - Läuft morgens VOR dem Morning Brief (z.B. 06:30)
   - Holt: Goals, KRs, letzte 7 Tage Entries, Mood, Patterns, letzte Reflection
   - AI generiert:
     a) "Fokus heute": Die 3 wichtigsten Tasks mit Begründung
     b) "Tipp des Tages": Personalisierter Produktivitäts-Tipp
     c) "Streak-Warnung": Falls ein Streak in Gefahr
     d) "Dimension-Check": Falls priorisierte Dimension vernachlässigt

2. DB: daily_suggestions Tabelle (user_id, date, suggestions JSONB, UNIQUE(user_id, date))

3. MORNING BRIEF INTEGRATION:
   - Morning Brief enthält jetzt die AI-Suggestions
   - "💡 Dein AI-Coach sagt: [Fokus + Tipp]"

4. DASHBOARD:
   - Neue Section auf Hauptseite: "💡 Tagesempfehlung"
   - Collapsible Card
   - API: GET /api/suggestions/today

5. SMART PRIORITY (bot/ai/prompts.py):
   - Priorisierung berücksichtigt jetzt: 40% Deadline, 30% Dimension-Priority (aus Reflection), 20% Streak-Risk, 10% Mood/Energy

Commit: "feat: daily AI suggestions with smart priority integration"
```

---

## Zusammenfassung: Prompt-Reihenfolge

| # | Prompt | Was | Prio |
|---|--------|-----|------|
| **4.5** | Stabilize & Commit | Uncommitted Changes testen + committen | JETZT |
| **5.1** | Deep Relations | Task↔Objective Verknüpfung + Auto-Tasks | Hoch |
| **5.2** | Kalender & Tagesplan | "Plan meinen Tag", Tages/Wochenansicht | Hoch |
| **5.3** | Fitness Splits | Workout-Pläne mit Progression | Mittel |
| **5.4** | Routinen + Shopping | Tageszeiten, Standard-Einkaufsliste | Mittel |
| **6.1** | Dashboard Schnellübersicht | Quick Stats, klickbare Shortcuts | Hoch |
| **6.2** | CRUD überall | Edit/Delete für alles | Hoch |
| **6.3** | Einstellungen erweitern | Name ändern, Toggles, Export | Mittel |
| **7.1** | Achievements | Meilensteine mit Auto-Unlock | Fun |
| **7.2** | Gamification UI | XP/Level im Dashboard + Telegram | Fun |
| **8.1** | Smart Reflection | Prioritäten + AI Goal-Vorschläge | Hoch |
| **8.2** | Daily Suggestions | AI-Tagesempfehlungen | Mittel |

**Empfohlene Reihenfolge:** 4.5 → 5.1 → 6.1 → 6.2 → 5.2 → 6.3 → 8.1 → 7.1 → 5.3 → 5.4 → 7.2 → 8.2
