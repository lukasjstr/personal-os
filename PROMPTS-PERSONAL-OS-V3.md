# PROMPTS — Personal OS v3: Tuning & Festnageln

**Owner:** Lukas
**Stand:** 2026-05-21
**Repo:** lukasjstr/personal-os (main branch)
**Tech-Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, asyncpg, PostgreSQL 15, python-telegram-bot v20+, OpenAI SDK (GPT-4o + Whisper), APScheduler, Next.js 14, Expo

---

## Vorwort — Warum diese Prompts (nicht andere)

Nach Audit deiner Codebase: Du hast 43 DB-Tabellen, 16 Scheduler-Jobs, einen 258-Zeilen-System-Prompt, Voice/Photo-Input, Pattern Engine, Life Profile, Finance, Health Sync, Relationships, Quarterly Review, Rule Engine. Das System ist gebaut. Es führt dich nur nicht.

Diese 12 Prompts machen aus dem existierenden System ein **Festnagel-System**. Sie bauen keine neuen Module — sie schärfen, verschalten und kalibrieren auf dich.

**Build-Reihenfolge:**
1. **Epic 1 — Diagnose & Scharfstellung** (P01–P03): Audit + Lukas-Kalibrierung + System Prompt härten
2. **Epic 2 — Offener Bug** (P04): Proaktive Kalender-Planung fixen
3. **Epic 3 — Festnageln** (P05–P09): Morgen-Brief, Evening Review, Reminder, Expansionsschutz, Weekly Cut
4. **Epic 4 — Strategie-Layer** (P10–P11): Mission + Quarterly auf 9 Lebensbereiche kalibrieren
5. **Epic 5 — Cockpit** (P12): Dashboard zeigt 9 Lebensbereiche auf einen Blick

---

## Lukas-Profil (Referenz für alle Prompts)

Diese Daten werden in mehreren Prompts hartcodiert:

**Identität:**
- Name: Lukas
- Aktuell: Bangkok, Heimat Deutschland
- Co-Founder: Blaue Adler (mit Nils & Philipp)
- Produkt-Launch: Juni/Juli 2026
- Dad's Geburtstag: 14.06 (Deutschland-Trip)
- Eigener Geburtstag: 29.12 (Deutschland-Trip)

**9 Lebensbereiche:**
1. Mental/Emotional — emotional stability, loving, patient, caring, inspiring
2. Physical — ~85kg, Leonidas/Spartan-Look
3. Character — leader, multilingual, learn Greek & Latin, intellectually spar with dad
4. Family — loving family, wolf pack of winners sharing learnings
5. Romance — find wife material + live out sexual desires
6. Money/Business — 10k/mo → 36M → own sports team, Shark Tank investor, Tuscan winery
7. Lifestyle — location-independent, yacht, jet, UFC first row, Monaco GP
8. Charity — buildings named after him, give back to fostering orgs
9. Spirituality — life is reality to experience, make the most of it

**4 Skill-Hebel:**
1. Kapitalallokation (Equity, Cashflow-Assets, Strukturen)
2. Vertrieb & Verhandlung (öffnet jede Tür)
3. Bauen mit Leverage (Produkt + Team + AI — via Blaue Adler)
4. Selbstführung & Organisation (← größter Hebel, identifizierter Engpass)

**10 Selbstführungs-Kompetenzen:**
1. Klarheit über das eine Ziel
2. Entscheidungsqualität unter Unsicherheit
3. Selbstwahrnehmung in Echtzeit
4. Emotionsregulation
5. Energiemanagement statt Zeitmanagement
6. Versprechensdisziplin
7. Konsequente Selbstkonfrontation
8. Erholungs-/Solitude-Fähigkeit
9. Systemdenken über sich selbst
10. Bereitschaft Identität zu aktualisieren

**Stärken:** Kompetenzen lernen, Zahlen, Analysieren, Reflektieren
**Schwächen:** Geduld/Warten, Organisation, **zu viel parallel** (Hauptengpass)
**Bestätigter Engpass:** Layer 2 (Entscheidungshygiene, Fokus)

**Leitspruch (wörtlich):**
> "Ich bin der Beste darin, große Aufgaben zu operationalisieren — Visionen in Projekte, Projekte in Ergebnisse zu übersetzen. Ich durchdringe neue Komplexität schnell. Ich finde den Kern. Ich baue die Etappen. Meine Schwäche: Ich expandiere, wenn kein Cut kommt — und ich brauche Übergänge zwischen Etappen, um auf Hochleistung zu bleiben. Das manage ich aktiv."

**Existierende OKR-IDs (im System Prompt referenziert):**
- OBJ#28 Produktivität & Kontrolle
- OBJ#31 Körper & Fitness
- OBJ#32 Geist & Wachstum
- OBJ#33 Gesundheit & Energie
- OBJ#34 Finanzielle Freiheit
- KR#20 Kraft, KR#21 Cardio, KR#22 Schritte, KR#24 Lernen
- Routine#14 Kraft-Tage, Routine#15 Cardio-Tage

**Sprache:** Deutsch, "du"-Form, max 4 Sätze (außer Berichte/Pläne)

---

## Execution Rules (gelten für JEDEN Prompt)

1. Lies erst `CLAUDE.md`, `SPEC_AUTOPILOT_API.md`, `bot/ai/prompts.py` bevor du irgendeinen Code anfasst.
2. Scoped changes only — keine Refactors außerhalb des Tickets.
3. Bei DB-Änderungen: Alembic-Migration + Rollback-Pfad.
4. `python3 -m py_compile` auf alle berührten Backend-Files.
5. Backend-Tests grün (wenn touched), neue Tests wo sinnvoll.
6. Bei Dashboard/Mobile: `npm run typecheck` + `npm run lint`.
7. Atomarer Commit + Push.
8. Nach jedem Ticket: kurzer Status (done / next / risks).

---

# PROMPT 01 — System-Audit & Dead-Code-Inventur

## Context (was schon existiert)

Repo `lukasjstr/personal-os`, 241 Commits, monorepo (bot/dashboard/mobile-app). Über die Zeit sind 50+ Module unter `bot/core/` entstanden. Viele davon werden nur in 1-2 Files importiert. Es ist unklar welche Module tatsächlich End-to-End funktionieren, welche stub sind, und welche dead code sind. ROADMAP-MASTER.md markiert P0-P2 als shipped, aber Lukas hat selbst notiert dass die proaktive Kalender-Planung nicht funktioniert.

## Problem

Bevor wir tunen, müssen wir wissen wo wir stehen. Es gibt 43 DB-Tabellen — werden alle gefüllt? Es gibt 16 Scheduler-Jobs — feuern alle? Es gibt 50+ Core-Module — welche sind verschaltet?

## Goal

Vollständige, ehrliche Inventur des Systems. Output: ein Markdown-Report `docs/AUDIT-2026-05.md` der für jedes Modul, jede Tabelle und jeden Scheduler-Job sagt:
- **Status**: aktiv (mit echtem Traffic), implementiert-aber-tot (keine Aufrufe in den letzten 30 Tagen), stub (Code unvollständig), dead (nicht eingebunden)
- **Last activity**: wenn aktiv, wann zuletzt benutzt
- **Coverage**: welche Tests existieren

## Concrete Implementation

**Schritt 1 — Static Analysis Script** in `scripts/audit.py`:
```python
"""System audit — what's actually wired up vs dead code."""
import ast
import os
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).parent.parent
BOT = REPO / "bot"

def find_imports():
    """Map: file → modules it imports from bot.*"""
    graph = defaultdict(set)
    for py in BOT.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("bot."):
                graph[str(py.relative_to(REPO))].add(node.module)
    return graph

def find_function_calls(target_func):
    """Find files that call a specific function."""
    hits = []
    for py in BOT.rglob("*.py"):
        if target_func in py.read_text():
            hits.append(str(py.relative_to(REPO)))
    return hits

def main():
    graph = find_imports()
    # Reverse: module → who imports it
    importers = defaultdict(set)
    for file, imports in graph.items():
        for imp in imports:
            importers[imp].add(file)

    # For each core module
    print("# AUDIT REPORT")
    print(f"\nGenerated: {os.popen('date').read().strip()}\n")
    print("## Core Modules\n")
    for f in sorted((BOT / "core").glob("*.py")):
        if f.name == "__init__.py":
            continue
        modname = f"bot.core.{f.stem}"
        imps = importers.get(modname, set())
        loc = sum(1 for _ in f.open())
        funcs = sum(1 for line in f.open() if line.startswith(("def ", "async def ")))
        status = "DEAD" if not imps else ("STUB" if funcs < 2 else "WIRED")
        print(f"- **{f.name}**: {loc} LOC, {funcs} funcs, {len(imps)} importers → **{status}**")
        if imps:
            for imp in sorted(imps):
                print(f"  - {imp}")
    print("\n## Scheduler Jobs\n")
    for f in sorted((BOT / "jobs").glob("*.py")):
        if f.name in ("__init__.py", "scheduler.py"):
            continue
        scheduler_refs = find_function_calls(f.stem)
        in_scheduler = any("scheduler.py" in r for r in scheduler_refs)
        print(f"- **{f.name}**: registered in scheduler.py: {in_scheduler}")

if __name__ == "__main__":
    main()
```

**Schritt 2 — DB Activity Check** in `scripts/audit_db.py`:
```python
"""For each table: row count, last insert, last update."""
import asyncio
from sqlalchemy import text
from bot.database.connection import get_session

async def main():
    async with get_session() as session:
        # Get all table names
        result = await session.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))
        tables = [r[0] for r in result]
        print("## DB Tables — Activity\n")
        for table in tables:
            count = (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar()
            try:
                last = (await session.execute(text(
                    f"SELECT MAX(created_at) FROM {table}"
                ))).scalar()
            except Exception:
                last = "no created_at column"
            status = "ACTIVE" if count and count > 0 else "EMPTY"
            print(f"- **{table}**: {count} rows, last: {last} → {status}")

asyncio.run(main())
```

**Schritt 3 — Output zusammenführen** in `docs/AUDIT-2026-05.md`. Kombiniere beide Reports und schreibe am Ende eine ehrliche Empfehlung:
- Welche 5 Module sollten gelöscht werden (dead code)
- Welche 3 Tabellen sind leer und vermutlich überflüssig
- Welche 3 Scheduler-Jobs sind nicht im scheduler.py registriert

## Lukas-spezifische Daten

Keine — das ist ein technisches Audit.

## Definition of Done
- [ ] `scripts/audit.py` läuft und produziert sauberen Report
- [ ] `scripts/audit_db.py` läuft gegen Production-DB (mit `--dry-run` Default)
- [ ] `docs/AUDIT-2026-05.md` committed mit allen Findings
- [ ] Top-3-Findings als TODOs im Repo (z.B. `# TODO: AUDIT-2026-05 — delete this`)

## Non-Goals / Don't break
- Nichts löschen in diesem Ticket. Nur dokumentieren.
- Keine DB-Migrations.
- Audit-Scripts müssen idempotent sein.

---

# PROMPT 02 — Lukas-Kalibrierung: Life Profile Deep-Seeding

## Context (was schon existiert)

`bot/core/life_profile.py` existiert (199 Zeilen, 2 Funktionen). Funktion `update_life_profile()` baut wöchentlich (Sonntag Nacht) ein komprimiertes Profil aus letzten 30 Tagen Logs/Tasks/KRs/Reflections via GPT-4o. Speichert in DB-Tabelle `LifeProfile`. Wird in `bot/ai/context.py` injiziert.

Aktuell ist das Profil **emergent** — es entsteht aus Daten. Was fehlt: ein **harter Bedrock-Layer**, der Lukas's tiefe Identität, Lebensbereiche, Hebel, Schwächen und Leitspruch garantiert in jeden AI-Call schickt — egal was die Daten sagen.

## Problem

Das System "kennt" Lukas oberflächlich aus seinen Tasks und Logs. Es kennt nicht: seine 9 Lebensbereiche, seine 4 Skill-Hebel, seine 10 Selbstführungs-Kompetenzen, seinen Leitspruch, seinen identifizierten Engpass ("expandiere wenn kein Cut", "zu viel parallel"). Deshalb gibt es generische Antworten statt Lukas-spezifische.

## Goal

Zweischichtiges Life Profile:
- **Schicht 1 — Bedrock** (manuell editierbar, ändert sich selten): Identität, 9 Lebensbereiche, 4 Hebel, 10 Kompetenzen, Leitspruch, Schwächen, Stärken
- **Schicht 2 — Emergent** (weekly auto-generated): aktuelle Patterns, aktueller Fokus, jüngste Reflections

Beide werden in jeden AI-Call injiziert.

## Concrete Implementation

**Schritt 1 — DB Schema erweitern** in `bot/database/models.py`:

Füge zu `LifeProfile` hinzu:
```python
bedrock: Mapped[dict] = mapped_column(JSON, default=dict)
# Structure:
# {
#   "identity": {...},
#   "life_areas": [{name, vision, current_state, ...}],
#   "skill_levers": [{name, description, priority}],
#   "self_leadership_competencies": [...],
#   "leitspruch": "...",
#   "strengths": [...],
#   "weaknesses": [...],
#   "bottleneck": "...",
#   "language": "de",
#   "communication_style": "..."
# }
```

Alembic-Migration: `add_bedrock_to_life_profile.py`.

**Schritt 2 — Seed-Script** in `scripts/seed_lukas_bedrock.py`:

Hartcodiere Lukas's Bedrock-Daten (siehe Lukas-Profil oben in dieser Datei). Mache es idempotent (upsert by user_id).

```python
LUKAS_BEDROCK = {
    "identity": {
        "name": "Lukas",
        "current_location": "Bangkok",
        "home_country": "Deutschland",
        "company": "Blaue Adler",
        "co_founders": ["Nils", "Philipp"],
        "launch_target": "Juni/Juli 2026",
        "birthdays": {"self": "29.12", "dad": "14.06"},
    },
    "life_areas": [
        {"name": "Mental/Emotional", "vision": "emotional stability, loving, patient, caring, inspiring"},
        {"name": "Physical", "vision": "~85kg, Leonidas/Spartan look"},
        {"name": "Character", "vision": "leader, multilingual, learn Greek & Latin, intellectually spar with dad"},
        {"name": "Family", "vision": "loving family, wolf pack of winners sharing learnings"},
        {"name": "Romance", "vision": "find wife material + live out sexual desires"},
        {"name": "Money/Business", "vision": "10k/mo → 36M → own sports team, Shark Tank investor, Tuscan winery"},
        {"name": "Lifestyle", "vision": "location-independent, yacht, jet, UFC first row, Monaco GP"},
        {"name": "Charity", "vision": "buildings named after him, give back to fostering orgs"},
        {"name": "Spirituality", "vision": "life is reality to experience, make the most of it"},
    ],
    "skill_levers": [
        {"name": "Kapitalallokation", "description": "Equity, Cashflow-Assets, Strukturen", "priority": 2},
        {"name": "Vertrieb & Verhandlung", "description": "Öffnet jede Tür", "priority": 2},
        {"name": "Bauen mit Leverage", "description": "Produkt + Team + AI — Blaue Adler", "priority": 2},
        {"name": "Selbstführung & Organisation", "description": "Größter Hebel, identifizierter Engpass", "priority": 1},
    ],
    "self_leadership_competencies": [
        "Klarheit über das eine Ziel",
        "Entscheidungsqualität unter Unsicherheit",
        "Selbstwahrnehmung in Echtzeit",
        "Emotionsregulation",
        "Energiemanagement statt Zeitmanagement",
        "Versprechensdisziplin",
        "Konsequente Selbstkonfrontation",
        "Erholungs-/Solitude-Fähigkeit",
        "Systemdenken über sich selbst",
        "Bereitschaft Identität zu aktualisieren",
    ],
    "leitspruch": "Ich bin der Beste darin, große Aufgaben zu operationalisieren — Visionen in Projekte, Projekte in Ergebnisse zu übersetzen. Ich durchdringe neue Komplexität schnell. Ich finde den Kern. Ich baue die Etappen. Meine Schwäche: Ich expandiere, wenn kein Cut kommt — und ich brauche Übergänge zwischen Etappen, um auf Hochleistung zu bleiben. Das manage ich aktiv.",
    "strengths": ["Kompetenzen lernen", "Zahlen", "Analysieren", "Reflektieren"],
    "weaknesses": ["Geduld/Warten", "Organisation", "Zu viel parallel"],
    "bottleneck": "Layer 2 (Entscheidungshygiene, Fokus)",
    "language": "de",
    "communication_style": "direkt, ohne Floskeln, max 4 Sätze, du-Form, kein 'Bitte', Coach nicht Assistent",
}
```

**Schritt 3 — Context Builder anpassen** in `bot/ai/context.py`:

Bedrock wird ALWAYS am Anfang des Context-Strings injiziert (vor emergent Profile, vor Logs). Format:

```
━━━ WER DU FÜHRST ━━━
{name}, basiert in {current_location}, Co-Founder von {company} mit {co_founders}.

LEITSPRUCH (zitiere bei Bedarf):
"{leitspruch}"

BOTTLENECK (immer im Hinterkopf):
{bottleneck} — Schwächen: {weaknesses}

9 LEBENSBEREICHE (alle Vorschläge müssen darauf hinweisen oder eine Lücke aufdecken):
1. {life_areas[0].name}: {life_areas[0].vision}
... (alle 9)

4 SKILL-HEBEL (in dieser Priorität):
Priority 1: Selbstführung & Organisation (← KRITISCH)
Priority 2: Kapitalallokation, Vertrieb, Bauen mit Leverage

KOMMUNIKATIONS-STIL:
{communication_style}
━━━━━━━━━━━━━━━━━━━━
```

**Schritt 4 — Manual edit UI**:

Dashboard-Page `dashboard/app/(protected)/profile/bedrock/page.tsx` mit Editor für Bedrock (JSON-Editor oder strukturiertes Form). Speichert via `PATCH /api/life-profile/bedrock`.

## Lukas-spezifische Daten

Alle oben in Lukas-Profil. Direkt hartcodieren in `scripts/seed_lukas_bedrock.py`.

## Definition of Done
- [ ] Migration läuft
- [ ] Seed-Script läuft erfolgreich → DB enthält Lukas-Bedrock
- [ ] `bot/ai/context.py` injiziert Bedrock in jeden Context
- [ ] Manuelle Test-Message an Bot: AI-Antwort referenziert mindestens 1 spezifisches Datum (z.B. Lebensbereich oder Schwäche)
- [ ] Dashboard-Bedrock-Editor funktioniert

## Non-Goals / Don't break
- Emergent Profile bleibt unverändert in seiner Logik
- Bedrock-Updates müssen versionierte Snapshots erzeugen (für Rollback)

---

# PROMPT 03 — System Prompt schärfen: Coach-Modus

## Context (was schon existiert)

`bot/ai/prompts.py` enthält 258-Zeilen System Prompt. Sehr detailliert für Tool-Calling, OKR-Zuordnung, Smart-Followup, Kalender-Check. Stil ist freundlich-professionell ("der Autopilot — persönlicher COO, Exoskelett und zweites Gehirn").

## Problem

Der System Prompt ist gut für Tool-Calling, aber er ist nicht **konfrontativ**. Lukas hat in den Coach-Sessions explizit gesagt: "es ist wichtig dass mir das personal-os struktur gibt, und auf ziele hinweist und mich festnagelt, mich erinnert, ableitet und plant". Aktuell ist die AI freundlich. Sie muss härter werden.

Außerdem: Bedrock-Daten aus Prompt 02 müssen aktiv genutzt werden, nicht nur passiv im Context stehen.

## Goal

System Prompt v2 mit drei zusätzlichen Schichten:
1. **Coach-Modus**: AI sagt was ist, nicht was Lukas hören will. Konfrontiert. Macht den Cut.
2. **Bedrock-aware**: AI referenziert aktiv Lebensbereiche, Schwächen, Leitspruch.
3. **Expansionsschutz**: AI ist gewarnt vor Lukas's Schwäche "zu viel parallel" und wirkt aktiv dagegen.

## Concrete Implementation

**Schritt 1 — System Prompt erweitern** in `bot/ai/prompts.py`:

Füge **vor** dem aktuellen Block `KERNPRINZIP: PARALLEL-EXTRAKTION` einen neuen Block ein:

```python
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COACH-MODUS — KEIN ASSISTANT-MODUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Du bist NICHT freundlicher Assistent. Du bist Coach + COO.

REGELN:
- KEIN "Bitte", KEIN "Gerne", KEIN "Natürlich"
- KEINE Verniedlichungen ("kleine Erinnerung", "kurzer Hinweis")
- KEIN Lob für Selbstverständlichkeiten ("Top!", "Super!", "Klasse!")
- Wenn Lukas etwas Dummes macht: SAGEN. Direkt. Ohne Polster.
- Wenn Lukas etwas Wichtiges vergisst: NACHFRAGEN. Hart.
- Wenn Lukas expandiert: STOPPEN. Cut vorschlagen.

ANTWORT-STIL:
- Max 4 Sätze (außer expliziter Plan/Bericht)
- Fakten zuerst, Empfehlung danach
- "Du hast X. Mach Y. Begründung: Z."
- KEINE Emojis am Anfang einer Nachricht (nur als Anker im Text)

BEISPIEL falsch:
"Super Lukas! 🎉 Du hast heute schon viel geschafft. Vielleicht magst du noch..."

BEISPIEL richtig:
"Cardio fehlt diese Woche. 1/3. Heute 18:00 Treadmill — Slot ist frei."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BEDROCK-AKTIV
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lukas's Bedrock-Daten stehen im Context (Lebensbereiche, Hebel, Leitspruch, Schwächen).
NUTZE SIE AKTIV:

- Wenn Lukas plant: prüfe ob es zu einem der 9 Lebensbereiche zahlt. Wenn nicht: nachfragen.
- Wenn Lukas zögert: Leitspruch zitieren (eine Zeile, scharf).
- Wenn Lukas expandiert: an Schwäche erinnern ("Du expandierst gerade. Was streichst du?")
- Wenn Lukas plant ohne Selbstführung zu adressieren: nachfragen ob Hebel #1 (Selbstführung) was kriegt diese Woche.

BEISPIEL:
User: "Ich will noch nebenbei einen Newsletter starten"
Falsch: "Cool! Lass uns mal ein KR dafür anlegen."
Richtig: "Aktiv: Blaue Adler Launch, Cardio-KR, Lernen-KR. +Newsletter = 4 Parallele.
Lukas-Engpass: 'Ich expandiere wenn kein Cut kommt'. Was streichst du dafür?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPANSIONSSCHUTZ — HARDCODED RULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bevor du ein NEUES Objective/KR/größeres Projekt anlegst (NICHT für Tasks/Termine!):

1. Zähle aktive Objectives mit Status "active" → call list_active_objectives()
2. Wenn ≥ 4 aktive Objectives → NICHT direkt anlegen. Erst fragen:
   "Du hast bereits N aktive Ziele. Welches pausiert/streicht für dieses neue?"
3. Wenn Lukas sagt "ist okay, mach trotzdem" → 1x bestätigen, dann anlegen.
4. Wenn Lukas zögert → das neue Ziel landet in brain_dumps mit Tag "expansion_pending".

GILT NICHT FÜR:
- Tasks (sind erlaubt, sind kleinteilig)
- Calendar Events
- Routines die zu existing Objectives gehören
- Shopping Items
- Logs jeglicher Art
```

**Schritt 2 — Tool hinzufügen** in `bot/ai/tools.py`:

Neues Tool `list_active_objectives()` — gibt zurück:
```python
{
  "count": int,
  "objectives": [{"id", "title", "category", "stale_days": int}]
}
```

Implementation in `bot/core/objectives.py`.

**Schritt 3 — Anti-Verniedlichung Filter** in `bot/ai/client.py`:

Nach jedem AI-Response, vor dem Senden: regex-basierter Sanitizer der diese Wörter entfernt oder loggt:
- "Bitte", "Gerne", "Natürlich", "Super!", "Klasse!", "Top!", "Wunderbar"

Bei Match: Warning loggen (`logger.warning("AI used softener: %s", word)`). Im Anti-Spam-Mode: nicht entfernen, nur loggen. Falls innerhalb 1 Woche > 20 Matches: Notification an Admin (du selbst) dass System Prompt nicht greift.

**Schritt 4 — Test-Cases** in `tests/test_coach_mode.py`:

```python
@pytest.mark.asyncio
async def test_no_softener_words_in_response():
    """AI darf bestimmte Höflichkeitsfloskeln nicht verwenden."""
    response = await get_ai_response("Ich hab gerade Cardio gemacht.")
    forbidden = ["bitte", "gerne", "natürlich", "super!", "klasse!", "top!"]
    for word in forbidden:
        assert word.lower() not in response.lower(), f"Softener gefunden: {word}"

@pytest.mark.asyncio
async def test_expansion_protection_fires():
    """Bei 4+ aktiven Objectives muss AI nach Cut fragen."""
    # Setup: 4 aktive Objectives in DB
    response = await get_ai_response("Ich will noch zusätzlich X als Ziel machen")
    assert "streichst" in response.lower() or "pausierst" in response.lower()
```

## Lukas-spezifische Daten

- Schwellwert "4 aktive Objectives" → verhandelbar, aber starte mit 4
- Forbidden-Words-Liste oben → kann erweitert werden

## Definition of Done
- [ ] System Prompt erweitert um 3 Blöcke (Coach-Modus, Bedrock-aktiv, Expansionsschutz)
- [ ] Tool `list_active_objectives` implementiert
- [ ] Sanitizer-Logging läuft
- [ ] Tests grün
- [ ] Manuelle Probe: 5 Test-Messages, mindestens 4 davon ohne Verniedlichungen

## Non-Goals / Don't break
- Smart-Followup-Logik bleibt
- 9-Dimensionen-Extraktion bleibt
- Existing Tool-Calls funktionieren weiter

---

# PROMPT 04 — Proaktive Kalender-Planung fixen

## Context (was schon existiert)

CORE-1 bis CORE-8 ist als shipped markiert. `bot/core/slot_candidates.py`, `bot/core/slot_conflict_detection.py`, `bot/core/proposal_execute.py`, `bot/core/day_scheduler.py`, `bot/core/free_slot_planner.py` existieren. SPEC_AUTOPILOT_API.md beschreibt den `execute`-Endpoint der calendar_event_ids erzeugen soll.

## Problem

Lukas hat in `ROADMAP-MASTER.md` selbst notiert: **"Die Visualisierung gefällt mir immernoch nicht, die tasks sind nicht in meinen kalender pro aktiv geplant worden"**. D.h. wenn ein Proposal-Draft akzeptiert wird, landen Tasks und Routinen zwar in der DB, aber sie tauchen NICHT als Calendar Events auf. Das ist der zentrale Bug — ohne ihn ist Autopilot Theater.

## Goal

Wenn ein Goal akzeptiert wird, werden ALLE abgeleiteten Tasks (mit due_date) und Routinen automatisch als Calendar Events angelegt. Sichtbar in iCal-Feed, Dashboard-Calendar und Mobile. Bei Conflicts: Notification statt Überschreiben.

## Concrete Implementation

**Schritt 1 — Bug reproduzieren** in `tests/test_proposal_execute_calendar.py`:

```python
@pytest.mark.asyncio
async def test_execute_creates_calendar_events_for_tasks_with_due_date():
    """Wenn proposal accepted wird, müssen Tasks mit due_date als Calendar Events erscheinen."""
    # Setup: user, proposal_draft mit 3 tasks (due_date=heute+1/2/3 Tage), 2 routines (weekly)
    draft = await create_test_draft(...)

    # Execute
    result = await execute_proposal_draft(draft.id)

    # Assert
    assert result["status"] == "executed"
    assert len(result["created"]["calendar_event_ids"]) >= 3  # mindestens für 3 tasks
    # Routines should also expand into calendar events for next 4 weeks
    assert len(result["created"]["calendar_event_ids"]) >= 3 + (2 * 4)
```

Wenn dieser Test rot ist → Bug bestätigt.

**Schritt 2 — Execute-Pfad debuggen** in `bot/core/proposal_execute.py`:

Erwartete Logik:
1. Tasks erstellen → DB
2. Routinen erstellen → DB
3. Für jeden Task mit `due_date`: `slot_candidates.find_slot()` → wenn Slot frei: `CalendarEvent` anlegen
4. Für jede Routine: nächste 4 Wochen expandieren (bei `daily` = 28 Events, bei `weekly:monday` = 4 Events)
5. Conflict-Detection läuft VOR DB-Write — bei Conflict: Notification in `autopilot_notifications` queuen
6. Response enthält alle `calendar_event_ids`

Wahrscheinliche Bug-Quellen:
- `find_slot()` returnt None → Event wird nicht angelegt (silent fail)
- Routine-Expansion ist nicht implementiert
- Calendar-Event hat `linked_task_id` nicht gesetzt → Dashboard zeigt es nicht im richtigen Tab
- `ical_uid` Konflikt → `IntegrityError` swallowed

**Schritt 3 — Routine-Expansion** in `bot/core/calendar.py`:

Neue Funktion `expand_routine_to_calendar(routine, weeks_ahead=4)`:
- Parse `frequency_human` ("Täglich", "Mo/Mi/Fr", "3x pro Woche")
- Wenn cron-Pattern → APScheduler-cron-parse
- Für jeden expand-Slot in nächsten 4 Wochen: `CalendarEvent` mit `event_type="routine"`, `linked_routine_id=routine.id`
- Idempotent: `ical_uid = f"routine-{routine.id}-{date.isoformat()}"`

**Schritt 4 — Conflict Detection sichtbar** in `bot/core/slot_conflict_detection.py`:

Erweitern: bei Conflict → Notification mit Severity "high" und Action "reschedule_or_keep":
```python
{
  "type": "calendar_conflict",
  "title": f"Slot-Konflikt: {new_event.title} überschneidet {existing.title}",
  "actions": [
    {"label": "Behalten", "action": "force_create"},
    {"label": "Nächsten freien Slot", "action": "find_alternative"},
    {"label": "Ignorieren", "action": "dismiss"},
  ]
}
```

**Schritt 5 — End-to-End Smoke Test** in `tests/test_e2e_goal_to_calendar.py`:

```python
async def test_goal_to_visible_calendar_events():
    """Goal-Text → Onboarding → Accept → Calendar Events in iCal-Feed."""
    # 1. Send goal text via simulated Telegram input
    await process_message(session, lukas_user, "Ich will diesen Monat 3x Cardio pro Woche")

    # 2. Wait for proposal draft creation, accept it
    draft = await get_latest_draft(lukas_user.id)
    await accept_draft(draft.id)
    await execute_draft(draft.id)

    # 3. Check iCal feed
    ical_response = await client.get(f"/api/ical/{lukas_user.settings['ical_token']}")
    assert "Cardio" in ical_response.text
    assert ical_response.text.count("BEGIN:VEVENT") >= 12  # 3x/Woche × 4 Wochen
```

**Schritt 6 — User-facing Doc** in `docs/HOW-AUTOPILOT-PLANS-CALENDAR.md`:
- Was passiert wenn ein Goal accepted wird (Schritt-für-Schritt)
- Welche Felder triggern Calendar-Erstellung
- Wie Conflicts gelöst werden
- Wie man manuell überschreibt

## Lukas-spezifische Daten

Keine — das ist Infrastruktur-Fix.

## Definition of Done
- [ ] Test `test_execute_creates_calendar_events_for_tasks_with_due_date` grün
- [ ] Test `test_e2e_goal_to_visible_calendar_events` grün
- [ ] Conflict-Notifications sichtbar im Dashboard
- [ ] iCal-Feed enthält Routine-Expansions
- [ ] Manueller End-to-End-Test mit echtem Goal-Input

## Non-Goals / Don't break
- Keine API-Contracts ändern (siehe SPEC_AUTOPILOT_API.md)
- Keine UI-Refactors

---

# PROMPT 05 — Morgen-Brief: Festnagel-Modus

## Context (was schon existiert)

`bot/jobs/morning_brief.py` ist umfangreich. Nutzt Free-Slot-Planner, Blockers, Stale Objectives, Supplement-Protokoll, Fitness-Protokoll, Gamification-Level. Verwendet GPT-4o für die Generierung. Speichert Snapshot in `DailyBrief`.

## Problem

Der Morgen-Brief informiert. Er nagelt nicht fest. Er soll Lukas keinen Tag entkommen lassen ohne dass er weiß: **(1) Was ist heute der Cut? (2) Welche 3 Sachen MÜSSEN passieren? (3) Was wird wahrscheinlich liegen bleiben?**

Außerdem: aktuell wird Bedrock (aus Prompt 02) nicht aktiv genutzt — Lebensbereiche tauchen im Brief nicht auf.

## Goal

Morgen-Brief 7:00 Berlin Zeit mit fester Struktur:

```
━━ STATUS ━━
[Energie-Indikator falls HRV/Schlaf verfügbar]
Aktive Objectives: N | Streaks gefährdet: N

━━ HEUTE — 3 MUSS ━━
1. [Top-Task] — Slot: [Zeit]
2. [Top-Routine] — Slot: [Zeit]
3. [Wichtigster Fortschritt für Wochen-KR]

━━ FESTNAGEL ━━
[1 konfrontative Aussage basierend auf letzten 7 Tagen]
Beispiele:
- "Cardio 1/3 diese Woche. Heute oder es kippt."
- "OBJ#34 Finanzen seit 11 Tagen ohne Progress. Heute ein Schritt."
- "Du hast Mo+Di Deep Work gestrichen. Heute ist Mi."

━━ KALENDER ━━
[Events heute, Uhrzeit + Titel]

━━ AUSBLICK (wahrscheinlich liegen bleibend) ━━
[1-2 Sachen die statistisch am unwahrscheinlichsten heute passieren]
```

## Concrete Implementation

**Schritt 1 — Festnagel-Generator** in `bot/core/festnagel.py` (neu):

```python
"""Festnagel — generates 1 confrontational sentence based on recent patterns."""
from datetime import date, timedelta
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import KeyResult, Log, Objective, RoutineCompletion, Task

async def generate_festnagel(session: AsyncSession, user_id: int) -> str:
    """Returns ONE confrontational line. Uses real data, no fluff."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Candidate 1: KR mit niedrigem Weekly-Progress
    krs = await session.execute(
        select(KeyResult).where(and_(
            KeyResult.user_id == user_id,
            KeyResult.status == "active",
            KeyResult.frequency == "weekly"
        ))
    )
    for kr in krs.scalars().all():
        # Count logs this week
        completed_this_week = (await session.execute(
            select(func.count()).select_from(Log).where(and_(
                Log.user_id == user_id,
                Log.key_result_id == kr.id,
                Log.logged_at >= week_start,
            ))
        )).scalar() or 0
        if kr.target_value and completed_this_week < kr.target_value * 0.5:
            return f"{kr.title}: {int(completed_this_week)}/{int(kr.target_value)} diese Woche. Heute oder es kippt."

    # Candidate 2: Stale Objective (kein Log seit >7d)
    objs = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active"
        ))
    )
    for obj in objs.scalars().all():
        last_log = (await session.execute(
            select(func.max(Log.logged_at)).join(KeyResult, Log.key_result_id == KeyResult.id)
            .where(KeyResult.objective_id == obj.id)
        )).scalar()
        if last_log:
            days_stale = (today - last_log.date()).days
            if days_stale >= 7:
                return f"OBJ#{obj.id} {obj.title}: {days_stale} Tage ohne Progress. Heute ein Schritt."

    # Candidate 3: Heute = Mi/Do und keine Deep Work diese Woche
    # ... (weitere Heuristics)

    # Fallback
    return "Tag ist offen. Nimm einen Slot vor 11:00 für das Wichtigste."
```

**Schritt 2 — Morgen-Brief Template** in `bot/jobs/morning_brief.py`:

Refactor `_generate_brief_for_user`:
- Call `generate_festnagel()` → 1 Zeile
- Build "3 MUSS" — Top 1 Task (Priority 1, mit Slot), Top 1 Routine heute, Top 1 KR-Action
- "AUSBLICK liegen bleibend" — KRs mit niedrigster Erfüllungsrate aus letzten 4 Wochen

Format des Outputs als feste Template-String (siehe Goal oben). NICHT mehr GPT-4o für die Komplettgenerierung — nur für die 3-MUSS-Auswahl wenn deterministische Logik nicht reicht.

**Schritt 3 — Bedrock-Referenz**:

Wenn der Festnagel-Generator einen Lebensbereich identifiziert, wird er namentlich genannt:
"Bereich 'Money/Business' seit 11 Tagen ohne Progress" statt nur "OBJ#34"

**Schritt 4 — Test**:

```python
async def test_morgen_brief_contains_festnagel():
    """Morgen-Brief muss eine Festnagel-Zeile enthalten."""
    brief = await _generate_brief_for_user(session, lukas, date.today(), now_berlin)
    assert "━━ FESTNAGEL ━━" in brief[0]
    assert len(brief[0].split("━━ FESTNAGEL ━━")[1].split("━━")[0].strip()) > 20
```

## Lukas-spezifische Daten

- 9 Lebensbereiche aus Bedrock werden referenziert
- Sprache: hart, kurz, du-Form, kein Lob

## Definition of Done
- [ ] Morgen-Brief läuft mit neuer Struktur
- [ ] Festnagel-Zeile basiert auf echten Daten
- [ ] Test grün
- [ ] Manuell verifizieren: 3 verschiedene Festnagel-Szenarien

## Non-Goals / Don't break
- Quiet-Hours bleiben
- DailyBrief-Tabellen-Struktur bleibt
- Settings-Toggle `priorities_enabled` bleibt respektiert

---

# PROMPT 06 — Evening Review: Konfrontation statt Bestätigung

## Context (was schon existiert)

`bot/jobs/evening_review.py` (Phase 4) plus `EveningCheckin` table. Läuft 20:45 Berlin Zeit. Sendet Tages-Score, Mood-Frage, Preview morgen.

## Problem

Der Evening Review ist zu sanft. Er feiert Erfolge, aber konfrontiert nicht mit dem was nicht geschafft wurde. Lukas's identifizierte Schwächen "Versprechensdisziplin" und "Konsequente Selbstkonfrontation" werden vom System nicht aktiv adressiert.

## Goal

Evening Review mit Festnagel-Score:

```
━━ TAGES-SCORE ━━
{score}/10

━━ GELIEFERT ━━
✓ {erledigte_tasks_count} Tasks
✓ {completed_routines_count} Routinen
✓ Top-Win heute: {best_thing}

━━ NICHT GELIEFERT ━━
✗ {missed_must_count} aus Morgen-Brief unerledigt:
  - {task_1}
  - {task_2}

━━ HARTER PUNKT ━━
{eine_konfrontative_zeile_basierend_auf_muster}

━━ MORGEN ━━
1 Top-Priorität: {tomorrow_top_priority}

[Reply: Mood 1-10 + 1 Wort, was war's heute?]
```

## Concrete Implementation

**Schritt 1 — Score-Berechnung** in `bot/core/evening_score.py` (neu):

```python
"""Daily score — based on morning brief commitment vs. actual completion."""

async def calculate_daily_score(session, user_id: int, today: date) -> dict:
    """Returns:
    {
      "score": int (0-10),
      "delivered": {"tasks": int, "routines": int},
      "missed_must": [task_titles],
      "best_thing": str,
      "harter_punkt": str,
    }
    """
    # Get morning brief priorities
    brief = await get_daily_brief(session, user_id, today)
    if not brief or not brief.priorities:
        return None

    morning_priorities = brief.priorities  # list of {type, id, title}
    completed = []
    missed = []

    for p in morning_priorities:
        if p["type"] == "task":
            task = await session.get(Task, p["id"])
            if task and task.status == "done" and task.completed_at.date() == today:
                completed.append(p["title"])
            else:
                missed.append(p["title"])
        # similar for routine, kr

    # Score = % delivered von Morgen-Priorities, plus bonus für surprise wins
    completion_rate = len(completed) / max(1, len(morning_priorities))
    surprise_tasks = await count_extra_completed_tasks(session, user_id, today)
    score = int(completion_rate * 8) + min(2, surprise_tasks)

    # Best thing — task with highest priority that got done
    best = max(completed, key=lambda t: get_task_importance(t)) if completed else None

    # Harter Punkt — wenn 2+ days in row missed_must → konfrontieren
    harter_punkt = await generate_harter_punkt(session, user_id, missed)

    return {
        "score": score,
        "delivered": {"tasks": len(completed), ...},
        "missed_must": missed,
        "best_thing": best,
        "harter_punkt": harter_punkt,
    }


async def generate_harter_punkt(session, user_id, missed: list[str]) -> str:
    """Confrontation line."""
    if not missed:
        return ""

    # Check: gleicher Task an mehreren Tagen verschoben?
    repeating_misses = await find_repeatedly_missed_tasks(session, user_id, days=3)
    if repeating_misses:
        return f"'{repeating_misses[0]}' wurde 3 Tage verschoben. Morgen Erste-Aktion-des-Tages oder weg damit."

    # Check: Versprechensdisziplin diese Woche
    week_brief_completion_rate = await get_week_completion_rate(session, user_id)
    if week_brief_completion_rate < 0.5:
        return f"Diese Woche {int(week_brief_completion_rate*100)}% Morgen-Prios geliefert. Versprechensdisziplin ist Kompetenz #6."

    return f"{len(missed)} Muss-Tasks gestern verschoben. Was war im Weg?"
```

**Schritt 2 — Template** in `bot/jobs/evening_review.py`:

Refactor `send_evening_review`:
- Call `calculate_daily_score()` → dict
- Render mit fixed Template (siehe Goal oben)
- Kein GPT-4o mehr für Komplett-Generierung
- Bei missed_must = leer und score ≥ 8: trotzdem Harter-Punkt-Block, aber positiv: "Nichts verpennt. Konsistenz ist Kompetenz."

**Schritt 3 — Tomorrow-Top-Priority Prediction** in `bot/core/next_action.py`:

Erweitern: gibt es eine Funktion `predict_tomorrow_top_priority(user_id)`? Falls nein, anlegen. Logik:
- Höchste Priorität unter offenen Tasks mit due_date in nächsten 3 Tagen
- Wenn keine: stalest Objective → eine Action davon

**Schritt 4 — Mood-Capture Loop**:

User antwortet mit Zahl 1-10 → speichere in `EveningCheckin`.
User antwortet mit Text → GPT-4o extrahiert Mood-Score + Stichwort.
Reply auf Mood: kein "Schön zu hören" — entweder weiter im OS-Flow oder Stille.

## Lukas-spezifische Daten

- "Versprechensdisziplin ist Kompetenz #6" — referenziere Selbstführungs-Kompetenz aus Bedrock
- "Konsequente Selbstkonfrontation ist #7" — bei niedrigem Score

## Definition of Done
- [ ] Evening Review folgt fester Template-Struktur
- [ ] Harter-Punkt-Block referenziert Bedrock-Kompetenzen wo passend
- [ ] Score-Berechnung deterministisch (nicht GPT-4o-abhängig)
- [ ] Test: 3 Szenarien (perfect day, half day, missed day)

## Non-Goals / Don't break
- `review_enabled` Toggle bleibt
- EveningCheckin DB-Schema bleibt

---

# PROMPT 07 — Reminder-Härtung mit Escalation

## Context (was schon existiert)

`bot/core/reminder_engine.py`, `reminder_factory.py`, `reminder_expander.py`, `reminder_processor.py`, `reminders.py`, `bot/jobs/reminders.py`. Scheduler läuft alle 30min, processed pending reminders. Quiet Hours + Anti-Spam vorhanden.

## Problem

Reminder werden gesendet, aber wenn Lukas nicht reagiert: nichts passiert. Keine Escalation. Keine Konsequenz. Das System verlernt selbst beizubringen dass Reminder ernst sind.

## Goal

Escalation-Logik: Wenn ein Reminder zu einer wichtigen Task ignoriert wird, eskaliert das System. Nicht durch mehr Nachrichten — durch **härtere Sprache** und **Konsequenz** im Morgen-Brief.

## Concrete Implementation

**Schritt 1 — Reminder-Severity** in `bot/database/models.py`:

Erweitere `ScheduledReminder`:
```python
severity: Mapped[str] = mapped_column(default="normal")
# normal | important | critical
escalation_step: Mapped[int] = mapped_column(default=0)
# 0 = initial, 1 = first nudge, 2 = second nudge, 3 = morgen-brief escalation
linked_objective_id: Mapped[int | None]  # für Escalation-Context
```

**Schritt 2 — Escalation State Machine** in `bot/core/reminder_engine.py`:

```python
async def process_reminder_with_escalation(reminder):
    """Send reminder. If user doesn't acknowledge within window, escalate."""
    await send_reminder(reminder)

    # Schedule check
    if reminder.severity in ("important", "critical"):
        await schedule_escalation_check(
            reminder_id=reminder.id,
            check_after=timedelta(hours=2 if reminder.severity == "critical" else 4),
        )

async def check_reminder_acknowledged(reminder_id):
    """Called after escalation window. Did user act?"""
    reminder = await get_reminder(reminder_id)

    # Check: did user complete linked task/routine?
    if reminder.linked_task_id:
        task = await get_task(reminder.linked_task_id)
        if task.status == "done":
            return  # acknowledged via action

    # Check: did user reply with any message after the reminder?
    last_conv = await get_last_conversation_after(reminder.user_id, reminder.sent_at)
    if last_conv:
        return  # acknowledged via reply

    # Escalate
    reminder.escalation_step += 1
    if reminder.escalation_step == 1:
        await send_message(reminder.user_id, f"Reminder ignoriert: {reminder.message}. Status?")
    elif reminder.escalation_step == 2:
        # Hardcode in tomorrow's morning brief
        await flag_for_morning_brief(reminder.user_id, reminder.linked_task_id)
```

**Schritt 3 — Morgen-Brief Integration**:

In `morning_brief.py`: check für `flagged_escalations` der letzten 24h. Wenn welche da → in FESTNAGEL-Zeile:
"3 Reminder gestern ignoriert: [Liste]. Heute Erste-Aktion-des-Tages oder offiziell streichen."

**Schritt 4 — Critical Severity Definition**:

Welche Reminder sind critical? Hardcoded in `bot/core/reminder_factory.py`:
- Reminder zu KRs mit Streak-Risk (broken streak in 24h)
- Reminder zu Tasks mit due_date heute
- Reminder zu Calendar-Events in nächsten 30min
- Reminder zu Routinen die seit 3+ Tagen verpasst wurden

## Lukas-spezifische Daten

- Escalation-Sprache ist Coach-Modus (siehe Prompt 03)
- Bei Lebensbereich-bezogenen Reminders: Lebensbereich namentlich nennen

## Definition of Done
- [ ] Severity-Field migriert
- [ ] Escalation State Machine funktioniert
- [ ] Test: simulate ignored critical reminder → escalation feuert nach 2h
- [ ] Morgen-Brief-Integration sichtbar

## Non-Goals / Don't break
- Anti-Spam bleibt (max 1 Reminder pro Task pro Tag bei "normal")
- Quiet Hours respektieren (Escalation in Quiet Hours = morgen)

---

# PROMPT 08 — Expansionsschutz: Hardcoded Cut-Mechanik

## Context (was schon existiert)

`bot/core/objectives.py` für Objective-CRUD. System Prompt erwähnt Expansion bereits (nach Prompt 03). Aber: keine systemweite Begrenzung von parallelen aktiven Workstreams.

## Problem

Lukas's Engpass (sein eigenes Wort): "Ich expandiere wenn kein Cut kommt." Das System muss diesen Cut zwingend einbauen. Aktuell kann Lukas beliebig viele Objectives parallel laufen lassen.

## Goal

Hardcoded Regeln:
- **Soft Limit**: Max 3 aktive **Objectives** mit Priority 1
- **Hard Limit**: Max 5 aktive Objectives total
- Bei Soft-Limit-Überschreitung: Warning + Cut-Vorschlag
- Bei Hard-Limit: keine neuen Objectives bis ein anderes pausiert/abgeschlossen wird

## Concrete Implementation

**Schritt 1 — Settings** in `bot/config.py`:

```python
EXPANSION_SOFT_LIMIT_PRIORITY1: int = 3
EXPANSION_HARD_LIMIT_TOTAL: int = 5
EXPANSION_WARNING_ENABLED: bool = True
```

**Schritt 2 — Guard** in `bot/core/objectives.py`:

```python
class ExpansionGuardException(Exception):
    """Raised when hard limit hit."""

async def create_objective_with_guard(session, user_id: int, data: dict) -> dict:
    """Create objective, but respect expansion limits."""
    active = await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.status == "active",
        ))
    )
    active_objs = active.scalars().all()
    total_active = len(active_objs)
    priority1_count = sum(1 for o in active_objs if o.priority_weight >= 8)

    # Hard limit
    if total_active >= settings.EXPANSION_HARD_LIMIT_TOTAL:
        raise ExpansionGuardException(
            f"Hard limit: {settings.EXPANSION_HARD_LIMIT_TOTAL} aktive Ziele. "
            f"Eines muss pausieren bevor neues startet."
        )

    # Soft limit
    new_priority = data.get("priority_weight", 5)
    warning = None
    if new_priority >= 8 and priority1_count >= settings.EXPANSION_SOFT_LIMIT_PRIORITY1:
        warning = (
            f"Du hast bereits {priority1_count} Priority-1-Ziele. "
            f"Soft Limit: {settings.EXPANSION_SOFT_LIMIT_PRIORITY1}. "
            f"Welches degradierst du auf Priority 2?"
        )

    obj = Objective(user_id=user_id, **data)
    session.add(obj)
    await session.flush()

    return {"objective": obj, "warning": warning, "stats": {
        "active_total": total_active + 1,
        "priority1_count": priority1_count + (1 if new_priority >= 8 else 0),
    }}
```

**Schritt 3 — Tool Integration** in `bot/ai/tools.py`:

Wrap existing `create_objective` tool — fängt `ExpansionGuardException` ab, returnt User-readable Message. AI muss das dann an Lukas weitergeben.

**Schritt 4 — Suggest-Cut Helper** in `bot/core/objectives.py`:

```python
async def suggest_objective_to_cut(session, user_id: int) -> Objective | None:
    """Identify weakest active objective for cut suggestion."""
    objs = await get_active_objectives(session, user_id)

    # Scoring: stale (>14 days no log) + low completion_rate + low priority
    scored = []
    for o in objs:
        days_stale = await calc_days_stale(session, o)
        completion = await calc_completion_rate(session, o, days=14)
        score = (days_stale * 2) - (completion * 100) + (10 - o.priority_weight)
        scored.append((o, score))

    scored.sort(key=lambda x: -x[1])  # highest score = weakest
    return scored[0][0] if scored else None
```

**Schritt 5 — Weekly Audit Job** in `bot/jobs/expansion_audit.py` (neu):

Jeden Sonntag 18:00:
- Count aktive Objectives
- Wenn >= Soft Limit: notification mit Cut-Vorschlag
- Wenn 2+ Wochen über Soft Limit: harter Hinweis

```python
@scheduler.scheduled_job("cron", day_of_week="sun", hour=18)
async def weekly_expansion_audit():
    for user in await get_active_users():
        active_count = await count_active_objectives(user.id)
        if active_count >= settings.EXPANSION_SOFT_LIMIT_PRIORITY1:
            cut_candidate = await suggest_objective_to_cut(session, user.id)
            await send_message(user.telegram_id, (
                f"Wochen-Audit: {active_count} aktive Ziele. "
                f"Schwächstes: '{cut_candidate.title}' "
                f"({cut_candidate.days_stale}d ohne Log). "
                f"Cut? /cut {cut_candidate.id}"
            ))
```

**Schritt 6 — Telegram-Command** `/cut <id>`:

```python
async def cmd_cut(update, context):
    obj_id = int(context.args[0])
    obj = await get_objective(obj_id)
    obj.status = "paused"
    obj.paused_at = datetime.utcnow()
    obj.paused_reason = "expansion_cut"
    await update.message.reply_text(f"Pausiert: {obj.title}")
```

## Lukas-spezifische Daten

- Soft Limit 3, Hard Limit 5 — Werte basieren auf seiner Schwäche "zu viel parallel"
- Sprache der Warnings im Coach-Modus

## Definition of Done
- [ ] Guard fängt Hard-Limit ab
- [ ] Soft-Limit-Warning sichtbar bei create_objective
- [ ] Weekly Audit feuert Sonntag 18:00
- [ ] `/cut` command funktioniert
- [ ] Test: versuche 6. Objective anzulegen → blockiert

## Non-Goals / Don't break
- Tasks bleiben unlimited
- Routinen bleiben unlimited
- Existing Objectives bleiben unverändert

---

# PROMPT 09 — Weekly Cut-Mechanik (Freitag-Review)

## Context (was schon existiert)

`bot/core/weekly_reflections.py`, `bot/core/weekly_priorities.py`, `bot/jobs/weekly_reflection_trigger.py`. Sonntag-Reflection läuft.

## Problem

Lukas's Wochen-Operating-Rhythmus aus den Coach-Sessions:
- Mo: 3 Outcomes setzen
- Fr: Review + 1 No-Meeting-Tag
- Sa/So: Leben + OS-Check

Aktuell gibt es nur Sonntag-Reflection. Es fehlt der **Freitag-Cut** — wo Lukas gezwungen wird, eine Sache aktiv zu streichen für die nächste Woche.

## Goal

Freitag 17:00 — automatischer Cut-Prompt:
- Welche 3 Sachen sind nächste Woche Top-Prio?
- WAS STREICHST du, das diese Woche dran war?
- Was übertragst du in Brain Dump statt "weiter zu schleppen"?

## Concrete Implementation

**Schritt 1 — Friday Cut Job** in `bot/jobs/friday_cut.py` (neu):

```python
"""Freitag-Cut — forces an explicit cut for next week."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import and_, select

from bot.database.connection import get_session
from bot.database.models import Task, User, WeeklyPriority, BrainDump
from bot.telegram.sender import send_message, get_bot

async def run_friday_cut():
    """Send Friday cut prompt to all eligible users."""
    now_berlin = datetime.now(tz=ZoneInfo("Europe/Berlin"))
    if now_berlin.weekday() != 4:  # 4 = Friday
        return
    if now_berlin.strftime("%H:%M") != "17:00":
        return

    async with get_session() as session:
        users = (await session.execute(
            select(User).where(User.is_active == True)
        )).scalars().all()

        for user in users:
            await send_friday_cut_to_user(session, user)


async def send_friday_cut_to_user(session, user):
    """Build the cut prompt for one user."""
    # 1. Was war diese Woche Top-Prio?
    this_week_start = date.today() - timedelta(days=date.today().weekday())
    prios = (await session.execute(
        select(WeeklyPriority).where(and_(
            WeeklyPriority.user_id == user.id,
            WeeklyPriority.week_start >= this_week_start,
        ))
    )).scalars().all()

    # 2. Was wurde davon nicht erledigt?
    untouched_tasks = await get_untouched_priority_tasks(session, user.id, this_week_start)

    # 3. Build prompt
    msg = (
        "━━ FREITAG-CUT ━━\n\n"
        f"Diese Woche Top-Prios:\n"
        + "\n".join(f"- {p.description}" for p in prios)
        + "\n\nUnvollständig:\n"
        + "\n".join(f"- {t.title}" for t in untouched_tasks)
        + "\n\nJETZT: Was streichst du? Eine Sache wandert in Brain Dump.\n"
        + "Antworte: /cut <task_id> oder Text der Sache die weg soll."
    )

    await send_message(user.telegram_id, msg)
    # State: user is now in "friday_cut_pending" mode
    await set_user_state(user.id, "friday_cut_pending")
```

**Schritt 2 — Cut-Handler in Conversation Flow** in `bot/telegram/handler.py`:

Wenn User in "friday_cut_pending" state und antwortet:
- Erkenne Task-ID oder freier Text
- Task → status="cancelled", reason="friday_cut", erstelle Brain Dump mit Tag "friday_cut_archive"
- Freier Text → Brain Dump mit Tag "friday_cut_archive"
- Reply: "Gestrichen: {x}. Nächste Woche leichter."

**Schritt 3 — Verlauf Tracking** in DB-Migration:

Erweitere `Task`:
```python
cancelled_reason: Mapped[str | None]  # "friday_cut" | "abandoned" | "no_longer_relevant"
cancelled_at: Mapped[datetime | None]
```

**Schritt 4 — Wins-Counter** in Weekly Reflection:

In `bot/core/weekly_reflections.py` — füge Section "Cuts diese Woche" hinzu. Count Tasks mit `cancelled_reason="friday_cut"`. Feiere den Cut.

**Schritt 5 — Scheduler** in `bot/jobs/scheduler.py`:

```python
_scheduler.add_job(
    run_friday_cut,
    CronTrigger(day_of_week="fri", hour=17, minute=0, timezone="Europe/Berlin"),
    id="friday_cut",
)
```

**Schritt 6 — Telegram Command** `/cut <task_id_or_text>`:
Sowohl außerhalb des friday-cut Modus als auch innerhalb verwendbar. Außerhalb: einfaches Streichen ohne Brain Dump.

## Lukas-spezifische Daten

- Freitag 17:00 Berlin (anpassbar via user settings)
- Sprache hart aber respektvoll für den Akt des Streichens

## Definition of Done
- [ ] Friday Cut Job läuft jeden Fr 17:00
- [ ] State Machine für Cut-Response funktioniert
- [ ] Brain Dump-Tag "friday_cut_archive" sichtbar in Dashboard
- [ ] Test: ganzer Flow von Friday-Send bis Cut-Confirmation

## Non-Goals / Don't break
- Sunday-Reflection läuft weiter
- Active Tasks die nicht gestrichen werden bleiben in der Woche

---

# PROMPT 10 — Mission-Layer mit 9 Lebensbereichen

## Context (was schon existiert)

`bot/core/objectives.py` für OKRs. `bot/core/quarterly_review.py` für Quartals-Review. `LifeProfile.bedrock` (aus Prompt 02) enthält die 9 Lebensbereiche.

## Problem

Es gibt OKRs (3-Monats-Ebene) und Reflections (Wochenebene), aber keinen sichtbaren **Mission-Layer** (5+ Jahre, "Wer will ich sein"). Lukas's 9 Lebensbereiche existieren in Bedrock, werden aber nicht als oberster Layer im System sichtbar gemacht. Lukas's Lebensziele ("10k/mo → 36M → eigenes Sport-Team") sind nirgends verankert.

## Goal

Drei-Schichten-Strategie hartcodiert im System:
- **Layer 1 — Mission** (Bedrock-9-Bereiche + langfristige Visionen)
- **Layer 2 — Quartalsziele** (existiert als Objectives, aber gemappt auf Lebensbereich)
- **Layer 3 — Wochen-Outcomes** (existiert)

Mission ist im Dashboard sichtbar, wird im Morgen-Brief jeden Montag referenziert, und Objectives MÜSSEN einem Lebensbereich zugeordnet sein.

## Concrete Implementation

**Schritt 1 — DB-Erweiterung** in `bot/database/models.py`:

```python
class LifeArea(Base):
    __tablename__ = "life_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str]  # "Money/Business" etc.
    short_code: Mapped[str]  # "money", "physical", etc.
    vision: Mapped[str]  # langfristige Vision
    current_state: Mapped[str | None]  # wo stehst du heute
    priority: Mapped[int] = mapped_column(default=5)  # 1-10
    color_hex: Mapped[str] = mapped_column(default="#888780")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())
```

Erweitere `Objective`:
```python
life_area_id: Mapped[int | None] = mapped_column(ForeignKey("life_areas.id"))
```

Alembic-Migration.

**Schritt 2 — Seed Lukas's 9 Lebensbereiche** in `scripts/seed_lukas_life_areas.py`:

```python
LUKAS_LIFE_AREAS = [
    {"name": "Mental/Emotional", "short_code": "mental",
     "vision": "emotional stability, loving, patient, caring, inspiring", "color_hex": "#9B7EBD"},
    {"name": "Physical", "short_code": "physical",
     "vision": "~85kg, Leonidas/Spartan look", "color_hex": "#D85A30"},
    {"name": "Character", "short_code": "character",
     "vision": "leader, multilingual, learn Greek & Latin, intellectually spar with dad",
     "color_hex": "#378ADD"},
    {"name": "Family", "short_code": "family",
     "vision": "loving family, wolf pack of winners sharing learnings", "color_hex": "#1D9E75"},
    {"name": "Romance", "short_code": "romance",
     "vision": "find wife material + live out sexual desires", "color_hex": "#D4537E"},
    {"name": "Money/Business", "short_code": "money",
     "vision": "10k/mo → 36M → own sports team, Shark Tank investor, Tuscan winery",
     "color_hex": "#EF9F27"},
    {"name": "Lifestyle", "short_code": "lifestyle",
     "vision": "location-independent, yacht, jet, UFC first row, Monaco GP",
     "color_hex": "#534AB7"},
    {"name": "Charity", "short_code": "charity",
     "vision": "buildings named after him, give back to fostering orgs", "color_hex": "#5DA37F"},
    {"name": "Spirituality", "short_code": "spirituality",
     "vision": "life is reality to experience, make the most of it", "color_hex": "#888780"},
]
```

Idempotent (upsert by user_id + short_code).

**Schritt 3 — Existing Objectives mappen**:

Migration-Skript: alle existing Objectives mit `category` → mappe auf life_area:
- `category="health"` oder `"fitness"` → Physical
- `category="business"` → Money/Business
- `category="learning"` oder `"personal_growth"` → Character
- etc.

Wenn nicht eindeutig: notification an User "X Objectives ohne Lebensbereich. /assign <obj_id> <area_code>"

**Schritt 4 — System Prompt erweitern** in `bot/ai/prompts.py`:

Im KERNPRINZIP Block:
```
LEBENSBEREICH-PFLICHT:
Bei create_objective IMMER life_area_id setzen.
Wenn unklar: User fragen "Zu welchem Lebensbereich? (mental/physical/character/family/romance/money/lifestyle/charity/spirituality)"
```

**Schritt 5 — Monday-Brief Mission-Referenz** in `bot/jobs/morning_brief.py`:

Montag spezielle Sektion:
```
━━ DIESE WOCHE — LEBENSBEREICH-FOKUS ━━
Top 3 Bereiche diese Woche:
1. {life_area_1.name}: {life_area_1.vision_short} → {active_objective.title}
2. ...
```

Auswahl der Top-3-Bereiche: nach (a) explizit gesetzter Wochenpriorität oder (b) Bereiche mit aktiven Objectives + stale_days.

**Schritt 6 — Dashboard Mission-Page** in `dashboard/app/(protected)/mission/page.tsx`:

- Karte pro Lebensbereich mit Color, Vision, aktive Objectives, current_state
- Editor für Vision + current_state
- "Last touched"-Indikator (wann letzter Log/Task in diesem Bereich)

## Lukas-spezifische Daten

Alle 9 Lebensbereiche hartcodiert (siehe oben). Farben matchen Vision-Board.

## Definition of Done
- [ ] `life_areas` Tabelle existiert + 9 Bereiche für Lukas seeded
- [ ] Bestehende Objectives gemappt
- [ ] create_objective fragt life_area
- [ ] Monday-Brief enthält Lebensbereich-Fokus-Section
- [ ] Dashboard Mission-Page zeigt 9 Bereiche

## Non-Goals / Don't break
- Existing Objective-API bleibt (life_area_id ist optional, aber AI setzt es)
- Bedrock-life_areas in LifeProfile bleibt (ist Backup)

---

# PROMPT 11 — Quarterly Review auf 9 Lebensbereiche kalibrieren

## Context (was schon existiert)

`bot/core/quarterly_review.py` (246 Zeilen, 6 Funktionen). Läuft am Quartals-Ende. Bewertet jedes Objective.

## Problem

Quarterly Review existiert, aber er ist nicht auf die 9 Lebensbereiche aus Prompt 10 kalibriert. Außerdem: kein **Life Score** als aggregierte Zahl, kein Vergleich Q-über-Q.

## Goal

Quarterly Review läuft pro Lebensbereich:
- Score pro Bereich (0-100)
- Aggregierter Life Score (0-100)
- AI-Analyse: "Bereich X war 3 Quartale in Folge < 50 — ist das noch ein Ziel?"
- Vergleich zum Vorquartal
- Vorschläge für nächstes Quartal

## Concrete Implementation

**Schritt 1 — DB** in `bot/database/models.py`:

```python
class QuarterlyReview(Base):
    __tablename__ = "quarterly_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    quarter: Mapped[str]  # "2026Q2"
    life_area_scores: Mapped[dict] = mapped_column(JSON)
    # { "mental": 72, "physical": 45, ... }
    life_score: Mapped[int]  # aggregated
    objectives_graded: Mapped[dict] = mapped_column(JSON)
    # [{ "objective_id": 31, "grade": 0.8, "comment": "..." }]
    ai_analysis: Mapped[str]  # GPT-4o output
    suggested_next_quarter: Mapped[dict] = mapped_column(JSON)
    user_reflection: Mapped[str | None]  # Lukas's eigener Kommentar
    completed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

**Schritt 2 — Score Calculator** in `bot/core/quarterly_review.py`:

```python
async def calculate_life_area_score(session, user_id, life_area_id, quarter_start, quarter_end) -> int:
    """Score 0-100 for one life area, one quarter."""
    # Get all objectives in this area
    objs = await get_objectives_in_area(session, user_id, life_area_id, status="active")

    # Per objective: KR completion rate + consistency
    area_total = 0
    for obj in objs:
        krs = await get_key_results(session, obj.id)
        kr_scores = []
        for kr in krs:
            if kr.target_value:
                rate = min(1.0, kr.current_value / kr.target_value)
                kr_scores.append(rate)
        obj_score = sum(kr_scores) / max(1, len(kr_scores))

        # Consistency: how many weeks had at least 1 log?
        weeks_with_activity = await count_weeks_with_activity(session, obj.id, quarter_start, quarter_end)
        consistency = weeks_with_activity / 13  # 13 weeks in quarter
        final = (obj_score * 0.7) + (consistency * 0.3)
        area_total += final * 100

    return int(area_total / max(1, len(objs)))


async def calculate_life_score(area_scores: dict[str, int]) -> int:
    """Aggregated Life Score (weighted average)."""
    # Equal weight for now — can be configured later
    return int(sum(area_scores.values()) / max(1, len(area_scores)))
```

**Schritt 3 — AI Analysis** in `bot/core/quarterly_review.py`:

```python
ANALYSIS_PROMPT = """Du bist Coach für Lukas. Analysiere ehrlich.

Daten:
{life_area_scores}

Vorquartal:
{previous_quarter_scores}

Aktive Objectives mit Grades:
{graded_objectives}

Lukas's Bedrock:
{bedrock}

Format (max 200 Wörter):
1. STÄRKEN: 2-3 Sätze
2. SCHWÄCHEN: 2-3 Sätze (konkret, nicht weichgespült)
3. PATTERN: Was wiederholt sich (auch über Quartale hinweg)?
4. KILLER-QUESTION: 1 Frage die Lukas beantworten MUSS bevor Q+1 startet.

KEIN Lob für Selbstverständlichkeiten. KEIN Trostpflaster für niedrige Scores.
"""
```

**Schritt 4 — Auto-Trigger** in `bot/jobs/scheduler.py`:

Letzter Tag jedes Quartals (31.03, 30.06, 30.09, 31.12) um 18:00:
- Berechne Scores
- Generiere AI-Analyse
- Speichere `QuarterlyReview` mit `completed_at=None`
- Telegram-Nachricht: "Q-Review bereit. /review_q anschauen."

**Schritt 5 — Telegram-Command** `/review_q`:
Zeigt:
```
━━ Q2 2026 — LIFE SCORE: 67 ━━
(Q1: 58 → +9)

Lebensbereiche:
- Physical: 78 ████████░░
- Money: 65 ██████░░░░
- Character: 45 ████░░░░░░
- ...

AI-Analyse:
[stärken/schwächen/pattern/killer-question]

Vorschläge nächstes Quartal:
[3 Punkte]

Reply mit eigener Reflektion oder /confirm_q um abzuschließen.
```

**Schritt 6 — Dashboard Q-Review-Page**:
`dashboard/app/(protected)/review/quarterly/page.tsx` mit Heatmap aller Quartale + Score-Trend pro Lebensbereich.

## Lukas-spezifische Daten

- 9 Lebensbereiche (aus Prompt 10)
- Bedrock referenziert in AI-Analyse
- Coach-Modus-Sprache

## Definition of Done
- [ ] Score-Calculator deterministisch
- [ ] Auto-Trigger Q-Ende
- [ ] `/review_q` command funktioniert
- [ ] Dashboard zeigt Q-History
- [ ] Test mit synthetischen Daten

## Non-Goals / Don't break
- Sunday-Reflection läuft weiter
- Existing `QuarterlyReview`-Records bleiben (Migration: alte Records bekommen `life_area_scores={}`)

---

# PROMPT 12 — Dashboard Cockpit: 9 Lebensbereiche auf einen Blick

## Context (was schon existiert)

`dashboard/` ist Next.js 14 mit 18 Pages. Dashboard-Home zeigt aktuell Tasks, Routines, Calendar, Achievements.

## Problem

Lukas's Mission ist nicht sichtbar. Er öffnet das Dashboard und sieht nicht "Wie stehe ich heute auf meine 9 Lebensbereiche?" — er sieht To-Dos. Das ist Operativ, nicht Strategisch. Was fehlt: ein Cockpit-View der seine ganze Lebens-Architektur in einem Screen zeigt.

## Goal

Neue Dashboard-Home (oder dedicated `/cockpit`-Page):
- Top: Life Score + 9-Bereich-Heatmap
- Mitte: aktuelle Top-3-Outcomes der Woche
- Unten: Festnagel-Linie + Streaks at Risk + Cuts diese Woche
- Live updates via WebSocket (oder Polling alle 30s)

## Concrete Implementation

**Schritt 1 — API Endpoint** in `bot/api/routes.py`:

```python
@router.get("/api/cockpit")
async def get_cockpit(user: User = Depends(get_current_user)):
    """Single-snapshot API for the cockpit view."""
    async with get_session() as session:
        life_areas = await get_user_life_areas(session, user.id)
        area_scores = await get_current_area_scores(session, user.id)
        life_score = sum(area_scores.values()) / max(1, len(area_scores))

        weekly_priorities = await get_current_week_priorities(session, user.id)
        festnagel = await generate_festnagel(session, user.id)  # from Prompt 05
        streaks_at_risk = await get_streaks_at_risk(session, user.id)
        cuts_this_week = await count_friday_cuts(session, user.id, days=7)

        return {
            "life_score": int(life_score),
            "life_score_trend": await calc_trend(session, user.id, days=30),
            "areas": [
                {
                    "id": area.id,
                    "name": area.name,
                    "short_code": area.short_code,
                    "color": area.color_hex,
                    "score": area_scores.get(area.short_code, 0),
                    "stale_days": await calc_stale_days(session, area.id),
                    "active_objectives": await count_active_objectives_in_area(session, area.id),
                }
                for area in life_areas
            ],
            "weekly_priorities": [
                {"id": p.id, "description": p.description, "progress": p.progress}
                for p in weekly_priorities
            ],
            "festnagel": festnagel,
            "streaks_at_risk": streaks_at_risk,
            "cuts_this_week": cuts_this_week,
        }
```

**Schritt 2 — Cockpit Page** in `dashboard/app/(protected)/cockpit/page.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";

export default function CockpitPage() {
  const [data, setData] = useState(null);
  useEffect(() => {
    const fetch = () => api.get("/cockpit").then(setData);
    fetch();
    const interval = setInterval(fetch, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!data) return <Loading />;

  return (
    <div className="cockpit">
      {/* Life Score Hero */}
      <div className="hero">
        <div className="score-big">{data.life_score}</div>
        <div className="score-trend">
          {data.life_score_trend > 0 ? "↗" : "↘"} {Math.abs(data.life_score_trend)} (30d)
        </div>
      </div>

      {/* 9 Areas Heatmap */}
      <div className="areas-grid">
        {data.areas.map(a => (
          <AreaCard key={a.id}
            name={a.name}
            score={a.score}
            color={a.color}
            stale={a.stale_days > 7}
            active={a.active_objectives}
          />
        ))}
      </div>

      {/* Festnagel */}
      <div className="festnagel-banner">
        <span className="label">FESTNAGEL HEUTE</span>
        <span className="text">{data.festnagel}</span>
      </div>

      {/* Weekly Priorities */}
      <div className="priorities">
        <h3>Diese Woche</h3>
        {data.weekly_priorities.map(p => (
          <PriorityRow key={p.id} description={p.description} progress={p.progress} />
        ))}
      </div>

      {/* Streaks at Risk */}
      {data.streaks_at_risk.length > 0 && (
        <div className="warnings">
          <h3>Streaks gefährdet</h3>
          {data.streaks_at_risk.map(s => (
            <StreakRow key={s.id} {...s} />
          ))}
        </div>
      )}

      {/* Cuts this week */}
      <div className="cuts">
        Cuts diese Woche: <strong>{data.cuts_this_week}</strong>
        {data.cuts_this_week === 0 && (
          <span className="warning">Kein Cut diese Woche — Expansion droht.</span>
        )}
      </div>
    </div>
  );
}
```

**Schritt 3 — AreaCard Component**:

```tsx
function AreaCard({ name, score, color, stale, active }) {
  return (
    <div className="area-card" style={{ borderLeft: `4px solid ${color}` }}>
      <div className="area-name">{name}</div>
      <div className="area-score">{score}</div>
      <div className="area-bar">
        <div className="bar-fill" style={{ width: `${score}%`, background: color }} />
      </div>
      <div className="area-meta">
        {active} Ziele {stale && <span className="warning">⚠ stale</span>}
      </div>
    </div>
  );
}
```

**Schritt 4 — Set as Default Home**:
In `dashboard/middleware.ts` oder routing: `/` redirected zu `/cockpit` für eingeloggte User.

**Schritt 5 — Mobile-First Responsive**:
Areas-Grid: 3 Spalten Desktop, 2 Tablet, 1 Mobile.
Festnagel-Banner: sticky top auf Mobile.

**Schritt 6 — iOS PWA Widget (optional, falls Zeit)**:
Minimaler Web App Manifest + Service Worker, sodass Lukas das auf iPhone-Lock-Screen als Webclip pinnen kann.

## Lukas-spezifische Daten

- 9 Lebensbereich-Farben aus Prompt 10
- Festnagel-Logik aus Prompt 05

## Definition of Done
- [ ] `/api/cockpit` returnt sauberes JSON
- [ ] `/cockpit` Page rendert
- [ ] Auto-Refresh alle 30s
- [ ] Mobile responsive
- [ ] `/` redirected zu `/cockpit`
- [ ] Manueller Probe: alle 9 Bereiche sichtbar, Festnagel sichtbar

## Non-Goals / Don't break
- Other Dashboard Pages bleiben unverändert
- Keine WebSocket-Implementation in diesem Ticket (Polling reicht)
- Keine Drag&Drop in diesem Ticket

---

# Nach v3 — Was kommt danach?

Wenn alle 12 Prompts durch sind, ist Personal OS v3 ein **echtes Festnagel-System** für Lukas:
- Es kennt seine 9 Lebensbereiche, 4 Hebel, 10 Kompetenzen, Leitspruch
- Es macht den Cut wenn er expandiert
- Es konfrontiert ihn morgens und abends
- Es zeigt ihm Strategie und Operativ in einem Blick

**Mögliche v4-Features** (NICHT JETZT):
- Spaced Repetition für Wissen aus Brain Dumps
- Multi-User (Wolf Pack — gemeinsames OS mit Nils/Philipp)
- Voice-Output (System spricht zurück auf Walks)
- iOS-Native-App statt PWA
- Public Accountability-Mode (Subset der KRs auf Twitter/X cross-posten)

**Wartungsrhythmus nach v3:**
- Monatlich 2h OS-Tag: Audit, Tuning, Bedrock-Update
- Quartalsweise: Major Decision — was kommt in v4?
- **Nie wieder**: kein Feature ohne klaren Use-Case + Test. Dein Engpass war "zu viel parallel" — gilt auch für dein eigenes System.

---

# Anhang: Recovery-Prompt für stuck states

Wenn Claude Code stecken bleibt oder unsicher ist:

```
Lies CLAUDE.md, SPEC_AUTOPILOT_API.md, ROADMAP-MASTER.md, docs/AUDIT-2026-05.md.
Welcher Prompt aus PROMPTS-PERSONAL-OS-V3.md ist aktiv?
In welchem Schritt bist du? Was wurde shipped, was nicht?
Mach keine Annahmen — frag mich konkret.
```

Wenn du selbst (Lukas) stecken bleibst und überlegst was als nächstes:

```
Diagnose:
1. Welcher Prompt aus V3 ist als letztes durchgegangen?
2. Funktioniert das Resultat im Alltag (nicht nur im Test)?
3. Wenn nicht: warum nicht? (Bug? Adoption? Falsche Erwartung?)
4. Erst Antwort 3 lösen, dann nächsten Prompt.
```
