"""
One-time reorganize script: reassigns all tasks wrongly placed under
Objective #1 ("Täglich 5 Minuten meditieren") to their semantically
correct objectives.

Run on server:
    cd /opt/personal-os && source venv/bin/activate
    python -m bot.scripts.reorganize_lukas --dry-run   # preview
    python -m bot.scripts.reorganize_lukas              # apply
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.connection import get_session
from bot.database.models import Task

logger = logging.getLogger(__name__)

# ─── Reassignment Map ────────────────────────────────────────────────────────
# task_id → correct objective_id
# Based on full analysis of all 167 non-shopping tasks.
# Only tasks currently on obj_id=1 (wrong) are listed here.

REASSIGN: dict[int, int] = {

    # ── Besserer Dozent werden (obj 12) ─────────────────────────────────────
    # Unterrichts-Vorbereitung, Slides, Termine
    8:  12,   # Slides vorbereiten (Unterricht 23.03)
    9:  12,   # Unterricht 23.03
    10: 12,   # Slides vorbereiten (Unterricht 20.04)
    11: 12,   # Unterricht 20.04
    12: 12,   # Slides vorbereiten (Unterricht 4.05)
    13: 12,   # Unterricht 4.05
    14: 12,   # Slides vorbereiten (Unterricht 18.05)
    15: 12,   # Unterricht 18.05
    16: 12,   # Slides vorbereiten (Unterricht 1.06)
    17: 12,   # Unterricht 1.06

    # ── KI-Content-Maschine entwickeln (obj 14) ─────────────────────────────
    # Content-Produktion, LinkedIn, YouTube, Social Media, AI-Themen
    4:  14,   # Texte schreiben
    5:  14,   # Bilder auswählen
    24: 14,   # LinkedIn-Poster automatisieren
    25: 14,   # Content Dump → Content-Maschine
    27: 14,   # Content Inbox System
    32: 14,   # YouTube AI Story / Live Record / Shorts
    33: 14,   # 1–2 LinkedIn-Posts pro Woche
    34: 14,   # Month of AI
    35: 14,   # Vergleich Amerika vs. Köln
    36: 14,   # AI Terminology
    37: 14,   # Six Prompt Strategies
    38: 14,   # Stats, Fakten, Begriffe
    39: 14,   # Jailbreak-Thematik
    40: 14,   # Lokale KI vs. klassische Nutzung
    41: 14,   # „In Cloud we trust"-Story
    42: 14,   # Mac Mini als „Praktikant"
    43: 14,   # Blind Curl-Befehl → WhatsApp kaputt
    44: 14,   # Automate your life
    45: 14,   # Personal Operating System
    46: 14,   # Delegate / Prioritize / Sovereignty
    47: 14,   # Datensouveränität (Interview Fernando Fernandez)
    48: 14,   # Zeitaktuell auf Themen reagieren
    49: 14,   # Mediale Aufbereitung
    50: 14,   # Automatisierter Outreach
    51: 14,   # TikTok + TikTok Shop
    52: 14,   # AI Content Repurposing
    53: 14,   # Viral-Mechanismus testen

    # ── Philosophisch-akademisches Buch schreiben (obj 15) ──────────────────
    # Kapitelinhalte, Recherche, Struktur
    54: 15,   # Theoretisches Framework
    55: 15,   # Einseitige Kulturen, Film, Mythologie
    56: 15,   # Star Wars
    57: 15,   # Chinesische Tradition
    58: 15,   # Jedes Kapitel beginnt mit Zitat
    59: 15,   # Diskussion & Analyse
    60: 15,   # Klare & effektive Prompts (Buchkapitel AI)

    # ── Technisches Automatisierungs-Ökosystem aufbauen (obj 13) ────────────
    # Dev-Projekte, Setup, Infrastruktur, Automatisierungen
    6:  13,   # Backend fertig
    7:  13,   # Frontend fertig
    18: 13,   # Mac Mini abholen und einrichten
    20: 13,   # Server auf Hostinger-Rechner installieren
    21: 13,   # Schlachtplan + JSON-Key übergeben
    22: 13,   # Google Sheets mit Service-Account verbinden
    23: 13,   # OpenCloud/OpenClaw Setup
    26: 13,   # NN-Automatisierungen bauen
    28: 13,   # Trading Bot finalisieren
    29: 13,   # HeyGen automatisierte Videos für Kundenprojekt
    30: 13,   # Google-Scripter für Google Maps
    31: 13,   # Accessibility Checker

    # ── Digitale Einkommensquellen aufbauen (obj 16) ─────────────────────────
    # Produkte, Dienstleistungen, neue Einkommensströme
    61: 16,   # Kuscheltiere verkaufen
    62: 16,   # Student Planner erstellen
    63: 16,   # Fitness Planner erstellen
    64: 16,   # Weekly Planner erstellen
    65: 16,   # Date Planner (52 Ideen) erstellen
    66: 16,   # Sugar Baby / E-Girl Konzept entwickeln
    67: 16,   # Affiliate Marketing starten
    68: 16,   # Subscription Modell entwickeln
    69: 16,   # YouTube Automation einrichten
    70: 16,   # Social Recruiting Strategie entwickeln
    71: 16,   # Legal Letter Translator erstellen
    72: 16,   # AI Marketingbewertung durchführen
    73: 16,   # Bewerbungen & Anträge automatisieren
    74: 16,   # Hausflipping starten
    75: 16,   # Auto kaufen & flippen
    76: 16,   # Versteigerung Screening durchführen
    99: 16,   # Restart Hustle starten

    # ── Finanzielle Unabhängigkeit erreichen (obj 17) ────────────────────────
    # Investments, Trading, Finanzen
    77: 17,   # 2.000 € in ETFs, Krypto und Aktien investieren
    78: 17,   # Financial Literacy vertiefen
    79: 17,   # Account Problem lösen
    80: 17,   # Trading Problem lösen

    # ── Körperliche & mentale Disziplin stärken (obj 18) ────────────────────
    # Sport, Gesundheit, körperliche Routinen
    84: 18,   # 3 Liter Wasser täglich trinken
    85: 18,   # Jeden zweiten Tag Sport machen
    86: 18,   # 2–3x Gym/Woche besuchen
    87: 18,   # 1x/Monat Massage buchen
    88: 18,   # 1x/Monat Therme besuchen
    89: 18,   # 2x/Monat Kältekammer besuchen
    90: 18,   # 1–2 Monate Boxen/Kickboxen trainieren
    91: 18,   # Gesund kochen
    93: 18,   # Mens sana in corpore sano umsetzen

    # ── Souveräne, selbstbestimmte Lebensstruktur schaffen (obj 19) ──────────
    # Mindset, Routinen, Selbstführung, Charakter
    81: 19,   # Morgenroutine durchführen
    82: 19,   # Mittagsroutine durchführen
    83: 19,   # Abendroutine durchführen
    92: 19,   # Zimmer aufräumen
    94: 19,   # 9 Uhr aufstehen
    95: 19,   # Erstes Drittel des Tages für dich nutzen
    96: 19,   # Mindfulness praktizieren
    97: 19,   # Kein People Pleaser sein
    98: 19,   # The Power of No anwenden
    100: 19,  # Kein sinnloser Konsum
    101: 19,  # Buch statt YouTube lesen
    102: 19,  # Keine emotionale Reaktion zeigen
    103: 19,  # Keine kognitive Dissonanz zulassen
    105: 19,  # Vision Board updaten
    106: 19,  # Group of peers finden

    # ── Geld, Finanzen & Business (obj 7) ────────────────────────────────────
    # Förderanträge, Stipendien
    107: 7,   # Gründerstipendium beantragen

    # ── Tägliche Aufgaben effizient erledigen (obj 20) ───────────────────────
    # Erledigungen, Reparaturen, Alltagstasks
    19: 20,   # Google-Account für Papa erstellen
    108: 20,  # IWC-Uhr reparieren
    109: 20,  # Anzughose reinigen
    110: 20,  # Infomails schreiben
}

# Task IDs to delete (empty title, no content)
DELETE_TASK_IDS: list[int] = [104]


# ─── Main ────────────────────────────────────────────────────────────────────

async def run(dry_run: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    async with get_session() as session:
        await _run(session, dry_run)
        if not dry_run:
            await session.commit()
            logger.info("✅ All changes committed.")
        else:
            await session.rollback()
            logger.info("🔍 Dry-run — no changes applied.")


async def _run(session: AsyncSession, dry_run: bool) -> None:
    # Load all affected tasks
    all_ids = list(REASSIGN.keys()) + DELETE_TASK_IDS
    result = await session.execute(select(Task).where(Task.id.in_(all_ids)))
    tasks_by_id = {t.id: t for t in result.scalars().all()}

    missing = [tid for tid in all_ids if tid not in tasks_by_id]
    if missing:
        logger.warning("Tasks not found (already deleted?): %s", missing)

    # ── Apply reassignments ──────────────────────────────────────────────────
    changed = 0
    for task_id, new_obj_id in REASSIGN.items():
        task = tasks_by_id.get(task_id)
        if not task:
            continue
        old_obj = task.objective_id
        if old_obj == new_obj_id:
            logger.info("  SKIP  [%d] %s (already correct: obj %d)", task_id, task.title, new_obj_id)
            continue
        action = "WOULD SET" if dry_run else "SET"
        logger.info("  %s  [%d] %-50s  obj %s → %d", action, task_id, task.title[:50], old_obj, new_obj_id)
        if not dry_run:
            task.objective_id = new_obj_id
        changed += 1

    # ── Delete empty tasks ───────────────────────────────────────────────────
    for task_id in DELETE_TASK_IDS:
        task = tasks_by_id.get(task_id)
        if not task:
            continue
        action = "WOULD DELETE" if dry_run else "DELETE"
        logger.info("  %s  [%d] '%s'", action, task_id, task.title)
        if not dry_run:
            await session.delete(task)

    logger.info("")
    logger.info("Summary: %d tasks reassigned, %d tasks deleted%s",
                changed, len([t for t in DELETE_TASK_IDS if t in tasks_by_id]),
                " (dry-run)" if dry_run else "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reorganize Lukas's tasks to correct objectives")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB changes")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))
