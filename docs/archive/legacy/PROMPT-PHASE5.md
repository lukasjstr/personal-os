# Phase 5: Deep Relations + Smart Planning + Shopping + Fitness Splits

Lies SPEC.txt und alle existierenden Dateien die du aendern musst bevor du anfaengst.

## 1. TASK-OBJECTIVE-GOAL DEEP RELATIONS

### Datenbank-Aenderungen (Alembic Migration erstellen!):
- Task.objective_id: FK -> objectives (nullable) — Task gehoert zu einem Objective
- Task.parent_task_id: FK -> tasks (nullable) — Sub-Tasks / Abhaengigkeiten
- Task.blocked_by_task_id: FK -> tasks (nullable) — Task ist blockiert durch andere Task
- Objective.parent_objective_id: FK -> objectives (nullable) — Goal -> Sub-Objective Hierarchie

### Bot AI Verhalten (bot/ai/prompts.py):
Fuege zum SYSTEM_PROMPT hinzu:
```
TASK-ZIEL ZUORDNUNG:
- JEDE neue Task sollte einem Objective zugeordnet werden wenn moeglich
- Wenn ein neues Goal/Objective erstellt wird: Schlage 3-5 konkrete Tasks vor und erstelle sie
- Wenn eine Task erstellt wird ohne Objective: Frage ob sie einem bestehenden Ziel zugeordnet werden soll
- Zeige Abhaengigkeiten: "Task X muss zuerst erledigt werden bevor Y"
- Wenn alle Tasks eines Objectives erledigt sind: Feiere und frage nach neuen Tasks

TAGESPLANUNG:
- Wenn der User fragt "Plan meinen Tag" oder aehnlich:
  1. Lade alle offenen Tasks sortiert nach Priority + Due Date
  2. Lade heutige Routinen
  3. Lade Kalender-Events
  4. Erstelle einen Zeitplan mit konkreten Zeitbloecken
  5. Erstelle Calendar Events fuer jeden Block
  6. Sende den Plan als uebersichtliche Nachricht
```

### AI Tools (bot/ai/tools.py) — neue/geaenderte Tools:
- create_task: Neuer Parameter objective_id (optional) 
- create_objective: Nach Erstellung automatisch 3-5 Tasks vorschlagen
- plan_my_day: Neues Tool — erstellt Tagesplan mit Zeitbloecken als Calendar Events
- suggest_tasks_for_objective: Neues Tool — schlaegt Tasks fuer ein Objective vor

### Dashboard (dashboard/src/app/objectives/page.tsx):
- Objective-Card zeigt zugehoerige Tasks als Checklist
- Progress berechnet aus: erledigte Tasks / alle Tasks des Objectives
- Klappbar: Objective aufklappen -> Tasks sehen
- Hierarchie visualisieren: Goal -> Sub-Objectives -> Tasks

### Dashboard (dashboard/src/app/tasks/page.tsx):
- Jede Task zeigt ihr Objective als farbigen Badge
- Filter nach Objective moeglich
- Blockierte Tasks ausgegraut mit "Blockiert durch: [Task Name]"
- Sub-Tasks eingerueckt unter Parent-Task

## 2. KALENDER + TAGESPLANUNG

### Bot:
- "Plan meinen Tag" -> Bot erstellt Zeitplan mit allen Tasks als Calendar Events
- Kalender-Notizen: "Notiz fuer morgen 14:00: Design Review beachten" -> Calendar Event mit Notiz
- Bot schlaegt proaktiv Termine vor basierend auf Task-Deadlines

### Dashboard (dashboard/src/app/calendar/page.tsx):
- Events anklickbar -> Detail-Panel mit Notizen
- Notiz-Feld pro Event (editierbar)
- Tagesansicht mit Zeitbloecken (nicht nur Monatsansicht)
- Wochenansicht
- Drag & Drop fuer Events (optional, nice-to-have)

### API:
- POST /api/calendar - Event erstellen
- PUT /api/calendar/{id} - Event updaten (Notizen)
- POST /api/calendar/{id}/notes - Notiz hinzufuegen

## 3. FITNESS SPLITS + PLAN

### Datenbank:
- Neue Tabelle: fitness_splits
  - id, user_id, name (z.B. "Push", "Pull", "Legs", "Oberkörper", "Unterkörper")
  - exercises: JSON (Liste von Uebungen mit Ziel-Sets/Reps/Gewicht)
  - day_of_week: Integer (nullable, 0=Mo, 6=So)
  - order_in_rotation: Integer

### Bot AI:
```
FITNESS:
- Erkenne Split-Referenzen: "Push Day", "Pull Tag", "Leg Day", "Oberkörper"
- Wenn User Workout loggt: Ordne dem aktuellen Split zu
- Schlage naechsten Split vor basierend auf Rotation
- Tracke Progression pro Uebung (letztes Gewicht, Steigerung)
- Morning Brief: "Heute ist Push Day: Bankdruecken, Schulterduecken, Trizeps"
```

### Dashboard (dashboard/src/app/fitness/page.tsx):
- Split-Uebersicht: Welcher Split wann (Wochen-Rotation)
- Pro Split: Liste der Uebungen mit letztem Gewicht + Ziel
- Progression-Chart pro Uebung (Gewicht ueber Zeit)
- "Naechstes Workout" Empfehlung

## 4. ROUTINEN: MORGENS / MITTAGS / ABENDS

### Datenbank-Aenderung:
- Routine.time_of_day: String (morning/midday/evening/anytime)
- Routine.sort_order: Integer (Reihenfolge innerhalb der Tageszeit)

### Bot:
- Routinen werden nach Tageszeit gruppiert
- Morning Brief zeigt nur Morgen-Routinen
- Mittags-Reminder (z.B. 12:00) zeigt Mittags-Routinen  
- Abend-Reminder (z.B. 18:00) zeigt Abend-Routinen
- "Zeig meine Morgenroutine" -> Liste

### Dashboard (dashboard/src/app/routines/page.tsx):
- 3 Sektionen: 🌅 Morgens | ☀️ Mittags | 🌙 Abends
- Jede Sektion zeigt Routinen mit Checkbox
- Completion direkt im Dashboard moeglich (POST /api/routines/{id}/complete)

## 5. EINKAUFSLISTE UPGRADE

### Datenbank-Aenderung:
- Task: Neues Feld is_recurring_shopping: Boolean, default False
- Oder besser: Neue Tabelle shopping_defaults
  - id, user_id, title, category (Gemuese, Fleisch, Basics, etc.), active: Boolean

### Bot:
```
EINKAUFSLISTE:
- "Standard-Einkaufsliste" -> Lade alle shopping_defaults und erstelle Tasks
- "Einkaufsliste fuer diese Woche" -> Standard + zusaetzliche Items
- Kategorien erkennen: Bacon -> Fleisch, Spinat -> Gemuese, Olivenoel -> Basics
- "Eingekauft" -> Alle Shopping-Tasks als erledigt markieren
- Standard-Items merken: Wenn ein Item 3x gekauft wurde -> als Standard vorschlagen
```

### Dashboard (dashboard/src/app/shopping/page.tsx):
- Kategorien als Sektionen: 🥬 Gemuese | 🥩 Fleisch | 🥫 Basics | 🧴 Haushalt
- Standard-Items mit Stern markiert (⭐)
- Checkbox zum Abhaken
- "Standard-Liste laden" Button
- Preis-Schaetzung pro Item (optional, nice-to-have)
- "Guenstig einkaufen" Hinweise basierend auf Saison (optional)

### API:
- GET /api/shopping/defaults - Standard-Einkaufsliste
- POST /api/shopping/defaults - Neues Standard-Item
- POST /api/shopping/load-defaults - Standard-Items als Tasks erstellen

## 6. DASHBOARD UX IMPROVEMENTS

### Allgemein:
- Smooth Transitions zwischen Seiten
- Skeleton Loading statt Spinner
- Toast Notifications bei Aktionen (Task erledigt, Routine gecheckt)
- Breadcrumbs auf Unterseiten
- "Zum Bot" Button (Telegram Deep Link) auf jeder Seite

### Mobile:
- Bottom Navigation Bar statt Hamburger (wie eine echte App)
- Swipe-Gesten fuer Task-Completion (swipe right = done)
- Pull-to-Refresh

## TECHNISCHE REGELN:
- OpenAI GPT-4o (NICHT Anthropic)
- Alembic Migration fuer DB-Aenderungen erstellen UND ausfuehren
- Dashboard: keine neuen npm deps
- Python: async everywhere
- Commit alles am Ende
