# Dashboard UX Fix + Token Flow

Du arbeitest am Personal OS Projekt. Das Dashboard (Next.js in `dashboard/`) und der Telegram Bot (Python/FastAPI in `bot/`) laufen bereits.

## PROBLEM 1: Log-Anzeige im Dashboard ist schlecht

Die Logs-Seite (`dashboard/src/app/logs/page.tsx`) zeigt Daten unformatiert an. 

### Log-Typen und wie sie angezeigt werden sollen:

- **workout**: "💪 {exercise}" + Details (weight×reps×sets ODER duration_min + "min") + note falls vorhanden
- **water**: "💧 {amount}L Wasser"  
- **mood**: "😊 Mood {score}/10" + notes
- **food**: "🍽️ {description}" + calories falls vorhanden
- **progress**: "📈 Fortschritt: +{value}" + description
- **gratitude**: "🙏 {note}"
- **general**: "📝 {raw_input oder data.content}"

### Log data Struktur (aus der DB):
```json
// workout
{"exercise": "Bankdrücken", "weight": 80, "reps": 10, "sets": 3}
{"exercise": "Laufen", "duration_min": 45.0}
{"exercise": "Krafttraining", "duration_min": 45.0, "note": "45min Kraft gemacht"}

// gratitude  
{"note": "Dankbar für Familie und Gesundheit"}

// water
{"amount": 1.5}

// mood
{"score": 7, "notes": "Guter Tag"}
```

### Anforderungen:
- Jeder Log-Typ bekommt eine eigene Card-Darstellung mit passendem Emoji + Farbe
- Keine rohen JSON-Daten anzeigen!
- Die "value" Spalte die aktuell "30", "45", "1" zeigt → weg, stattdessen in der Card formatiert
- Workout-Chart: X-Achse = Datum, Y-Achse = Anzahl Workouts, gruppiert nach exercise

## PROBLEM 2: Token-Flow fehlt

Aktuell muss man den Bearer Token manuell kennen. 

### Lösung:
1. **Telegram Bot Command `/token`** — generiert einen API Token und schickt ihn per DM
   - Datei: `bot/telegram/handler.py` — füge einen Command-Handler hinzu
   - Nutze die bestehende `generate_api_token()` aus `bot/api/auth.py`
   
2. **Dashboard Login-Screen** (`dashboard/src/components/TokenGate.tsx`) — verbessern:
   - Text: "Schreib /token an @PersonalOperatingSystem_Bot auf Telegram"
   - Schönes Design mit Telegram-Icon
   - Token-Eingabefeld mit "Verbinden" Button
   - Bei falschem Token: Fehlermeldung

## PROBLEM 3: Allgemeine Dashboard UX

### Objectives-Seite:
- Farb-Badges pro Category: health=grün, fitness=blau, finance=gelb, learning=lila, personal=grau, business=orange
- Objectives die eigentlich "Life Areas" sind (ohne Key Results) anders darstellen als echte Ziele

### Tasks-Seite:
- Category-Badge anzeigen (business, learning, etc.)
- Farbcodierung nach Priority (P1=rot, P2=orange, P3=gelb)
- Gruppierung nach Category möglich

### Dashboard Hauptseite:
- Die Stats-Karten sollten klickbar sein (navigieren zur jeweiligen Seite)
- Letzte Aktivität als Timeline (letzte 5 Logs schön formatiert)

## TECHNISCHES
- Dashboard: `dashboard/` (Next.js 14, TypeScript, Tailwind)
- Bot: `bot/` (Python, FastAPI)
- API Types in `dashboard/src/lib/api.ts`
- Existierende Komponenten: StatCard, Badge, ProgressBar, LoadingSpinner, Header, Sidebar
- NICHT: package.json dependencies ändern (recharts, lucide-react, swr, date-fns sind schon da)
- Commit alles wenn du fertig bist

## DATEIEN DIE DU ÄNDERN MUSST:
1. `dashboard/src/app/logs/page.tsx` — komplett überarbeiten
2. `dashboard/src/app/page.tsx` — Stats klickbar + Activity Timeline
3. `dashboard/src/app/objectives/page.tsx` — Category Farben
4. `dashboard/src/app/tasks/page.tsx` — Category Badge + Priority Farben  
5. `dashboard/src/components/TokenGate.tsx` — besserer Login-Flow
6. `bot/telegram/handler.py` — /token Command hinzufügen
