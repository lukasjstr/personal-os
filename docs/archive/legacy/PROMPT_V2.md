# Personal OS — V2 Rebuild

Lies SPEC_V2.txt für die vollständige, definitive Spezifikation.

## KRITISCHE ÄNDERUNGEN vs. aktuellem Code:

### 1. OPENAI statt Anthropic!
- Die Spec sagt "Haiku" aber wir nutzen **OpenAI SDK** (`openai` package)
- Model: `gpt-4o` für Chat, `gpt-4o-mini` für einfache Tasks
- ERSETZE alle `anthropic` imports durch `openai`
- ERSETZE den Tool-Call-Loop für OpenAI function calling format
- Config: `OPENAI_API_KEY` statt `ANTHROPIC_API_KEY`
- Die .env hat bereits `OPENAI_API_KEY` — nutze diesen

### 2. Was NEU gebaut werden muss:
- **15 DB Tabellen** (aktuell 10) — neue: DailyBrief, ScheduledReminder, WeeklyReflection, WeeklyPriority, UserInsight
- **21 Tools** statt 17 — neue: get_shopping_list, complete_shopping, update_user_settings, log_food (optional)
- **Toggle System**: /settings, /toggle, /times Commands in telegram/commands.py
- **Shopping als Task-Kategorie** (category="shopping")
- **Next-Action Prinzip**: Nach jeder Erledigung → nächsten Schritt vorschlagen
- **Phase 2+3 Stubs**: Dateien mit Docstrings + Signaturen ohne Logik
- **Erweiterter Context Builder**: Shopping-Items, Mood-Trend, User Settings

### 3. Was BEHALTEN wird:
- Grundstruktur bot/, telegram/, ai/, core/, jobs/, database/, api/
- PostgreSQL, FastAPI, async SQLAlchemy
- Webhook-basierter Telegram Bot
- iCal Feed

### 4. Arbeitsverzeichnis
Du arbeitest in /Users/macbot/projects/personal-os/
Der aktuelle Code ist bereits committed. Baue DARAUF auf — refactore was nötig ist.

### 5. Nach dem Build
```
git add -A
git commit -m "feat: Personal OS V2 — OpenAI, 15 tables, 21 tools, toggles, shopping, next-action"
```

Dann deployen wir auf den Server.

## WICHTIG:
- OPENAI, nicht Anthropic! Überall wo "Haiku" oder "anthropic" steht → OpenAI
- Alle Phase 1 Dateien VOLLSTÄNDIG implementiert
- Phase 2+3 als Stubs mit Docstrings
- Kein TODO, kein Placeholder im Phase 1 Code
