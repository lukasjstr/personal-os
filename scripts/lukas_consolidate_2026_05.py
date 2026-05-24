"""V3-Audit-Konsolidierung (2026-05-21) — einmalig für Lukas.

Drei Operationen, alle idempotent:

  1. Money/Business — neues P1-Objective "Blaue Adler Launch Juni/Juli 2026"
     mit 3 KRs. Erst Operativ-Druck auf den Launch.

  2. Mental/Emotional-Cluster kollabieren — 8 Anti-Goal-Objectives →
     1 "Selbstführung 2026" mit messbaren KRs. Originale werden auf
     status='abandoned' gesetzt, Inhalt in BrainDump archiviert.

  3. Bedrock-Update — Leitspruch, core_line, DE-Visions, Skill-Lever
     priorities 1-4, Romance/Charity neu formuliert.

Idempotency: Operationen prüfen, ob das Ziel-Objekt schon existiert
(Title-Match) bevor sie inserten. Re-runs sind no-ops.

Run: PYTHONPATH=. python3 scripts/lukas_consolidate_2026_05.py [--user-id N]
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime

from sqlalchemy import and_, select

from bot.core.life_profile import update_bedrock
from bot.database.connection import get_session
from bot.database.models import (
    BrainDump, KeyResult, LifeArea, Objective, User,
)


CONSOL_MARKER = "[v3-audit-2026-05]"


# ─── New Money/Business Objective ────────────────────────────────────────────


MONEY_OBJECTIVE = {
    "title": "Blaue Adler Launch Juni/Juli 2026",
    "category": "business",
    "description": (
        "Launch-Block: Pre-Launch, Launch-Date, erste 90 Tage post-launch. "
        "Operativ-Druck auf das Hauptprodukt von Blaue Adler. "
        f"{CONSOL_MARKER}"
    ),
    "priority_weight": 10,
    "target_date": date(2026, 7, 31),
    "krs": [
        {"title": "Launch-Datum in Stein", "metric_type": "boolean",
         "target_value": 1, "unit": "ja/nein", "frequency": "once"},
        {"title": "Pre-Launch Waitlist Sign-ups",
         "metric_type": "number", "target_value": 200, "unit": "sign-ups",
         "frequency": "monthly"},
        {"title": "Erste zahlende Kunden (MRR-Start)",
         "metric_type": "number", "target_value": 10, "unit": "Kunden",
         "frequency": "monthly"},
    ],
}


# ─── Mental/Emotional consolidation ──────────────────────────────────────────


# These are the V3-audit anti-goals that get collapsed into ONE objective.
ANTI_GOAL_TITLES = {
    "Kein People Pleaser sein",
    "The Power of No (Buch lesen + Mindset)",
    "Restart Hustle (Produktivität neu starten)",
    "Kein sinnloser Konsum",
    "Buch statt YouTube",
    "Keine emotionale Reaktion",
    "Keine kognitive Dissonanz",
    "Group of peers finden",
}


SELBSTFUEHRUNG_OBJECTIVE = {
    "title": "Selbstführung 2026",
    "category": "personal",
    "description": (
        "Operationaler Bottleneck: Entscheidungshygiene + Fokus + "
        "Versprechensdisziplin. Mental/Emotional als ein Cluster — "
        f"konsolidiert aus 8 Anti-Goals am 2026-05-21. {CONSOL_MARKER}"
    ),
    "priority_weight": 10,
    "target_date": date(2026, 12, 31),
    "krs": [
        {"title": "Bewusstes Nein pro Woche geloggt",
         "metric_type": "number", "target_value": 3, "unit": "Neins",
         "frequency": "weekly"},
        {"title": "Konsum-frei-Tage pro Woche (kein YouTube/Social-Scroll)",
         "metric_type": "number", "target_value": 5, "unit": "Tage",
         "frequency": "weekly"},
        {"title": "Wöchentlicher Solitude-Block (≥1h)",
         "metric_type": "number", "target_value": 1, "unit": "Block",
         "frequency": "weekly"},
        {"title": "Pages gelesen pro Woche (Buch statt Feed)",
         "metric_type": "number", "target_value": 100, "unit": "Pages",
         "frequency": "weekly"},
    ],
}


# ─── Bedrock V3-audit revision ───────────────────────────────────────────────


LUKAS_BEDROCK_V2 = {
    "identity": {
        "name": "Lukas",
        "current_location": "Bangkok",
        "home_country": "Deutschland",
        "company": "Blaue Adler",
        "co_founders": ["Nils", "Philipp"],
        "launch_target": "Juni/Juli 2026",
        "birthdays": {"self": "29.12", "dad": "14.06"},
    },
    # NEW: short reflex-zitat (Coach-Modus)
    "core_line": "Ich will der beste Operationalisierer sein. Cut kommt vor Expansion.",
    "leitspruch": (
        "Ich will der beste Operationalisierer sein. "
        "Ich übersetze Visionen in Etappen, Etappen in Ergebnisse. "
        "Ich durchdringe Komplexität schnell, finde den Kern, baue die Etappen. "
        "Meine Schwäche: ich expandiere wenn kein Cut kommt — das manage ich aktiv."
    ),
    "life_areas": [
        {"name": "Mental/Emotional", "vision": "Emotionale Stabilität — liebend, geduldig, fürsorglich, inspirierend"},
        {"name": "Physical", "vision": "~85kg, Leonidas/Spartan-Optik"},
        {"name": "Character", "vision": "Anführer, mehrsprachig (Griechisch & Latein lernen), auf Augenhöhe mit Vater diskutieren"},
        {"name": "Family", "vision": "Liebende Familie — wolf pack of winners, das Erkenntnisse teilt"},
        {"name": "Romance", "vision": "Tiefe Partnerschaft als Foundation — gelebte Liebe und Sexualität als Realität darin"},
        {"name": "Money/Business", "vision": "10k/mo → 36M → eigenes Sport-Team, Shark-Tank-Investor, toskanisches Weingut"},
        {"name": "Lifestyle", "vision": "Standortunabhängig, Yacht, Jet, UFC erste Reihe, Monaco GP"},
        {"name": "Charity", "vision": "Spürbarer Impact — Stiftung, Bildungs- und Foster-Care-Programme finanzieren und mitgestalten"},
        {"name": "Spirituality", "vision": "Leben ist Realität zum Erleben — voll präsent, voll dabei"},
    ],
    "skill_levers": [
        {"name": "Selbstführung & Organisation", "description": "Größter Hebel, identifizierter Engpass", "priority": 1},
        {"name": "Kapitalallokation", "description": "Equity, Cashflow-Assets, Strukturen", "priority": 2},
        {"name": "Vertrieb & Verhandlung", "description": "Öffnet jede Tür", "priority": 3},
        {"name": "Bauen mit Leverage", "description": "Produkt + Team + AI — via Blaue Adler", "priority": 4},
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
    "strengths": ["Kompetenzen lernen", "Zahlen", "Analysieren", "Reflektieren"],
    "weaknesses": ["Geduld/Warten", "Organisation", "Zu viel parallel"],
    "bottleneck": "Layer 2 (Entscheidungshygiene, Fokus)",
    "language": "de",
    "communication_style": (
        "direkt, ohne Floskeln, max 4 Sätze, du-Form, kein 'Bitte', Coach nicht Assistent"
    ),
}


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _area_id(session, user_id: int, short_code: str) -> int | None:
    row = (await session.execute(
        select(LifeArea).where(and_(
            LifeArea.user_id == user_id, LifeArea.short_code == short_code,
        ))
    )).scalar_one_or_none()
    return row.id if row else None


async def _objective_exists(session, user_id: int, title: str) -> Objective | None:
    return (await session.execute(
        select(Objective).where(and_(
            Objective.user_id == user_id,
            Objective.title == title,
        ))
    )).scalar_one_or_none()


async def _create_objective_with_krs(
    session, user_id: int, spec: dict, life_area_id: int | None
) -> tuple[Objective, list[KeyResult], bool]:
    """Returns (objective, krs, created_new)."""
    existing = await _objective_exists(session, user_id, spec["title"])
    if existing is not None:
        # Just resync linkage; do not duplicate KRs
        if life_area_id is not None and existing.life_area_id != life_area_id:
            existing.life_area_id = life_area_id
        if existing.priority_weight != spec.get("priority_weight", 5):
            existing.priority_weight = spec.get("priority_weight", 5)
        await session.flush()
        krs = (await session.execute(
            select(KeyResult).where(KeyResult.objective_id == existing.id)
        )).scalars().all()
        return existing, list(krs), False

    obj = Objective(
        user_id=user_id,
        title=spec["title"],
        category=spec["category"],
        description=spec.get("description"),
        status="active",
        priority_weight=spec.get("priority_weight", 5),
        target_date=spec.get("target_date"),
        life_area_id=life_area_id,
    )
    session.add(obj)
    await session.flush()

    krs: list[KeyResult] = []
    for kr_spec in spec.get("krs", []):
        kr = KeyResult(
            objective_id=obj.id,
            user_id=user_id,
            title=kr_spec["title"],
            metric_type=kr_spec.get("metric_type", "number"),
            target_value=kr_spec.get("target_value"),
            unit=kr_spec.get("unit"),
            frequency=kr_spec.get("frequency", "weekly"),
            status="active",
        )
        session.add(kr)
        await session.flush()
        krs.append(kr)
    return obj, krs, True


# ─── Ops ─────────────────────────────────────────────────────────────────────


async def op1_money_business(user_id: int) -> dict:
    async with get_session() as session:
        area_id = await _area_id(session, user_id, "money")
        obj, krs, created = await _create_objective_with_krs(
            session, user_id, MONEY_OBJECTIVE, area_id,
        )
    return {"action": "created" if created else "synced",
            "objective_id": obj.id, "kr_count": len(krs)}


async def op2_consolidate_mental(user_id: int) -> dict:
    """Collapse 8 anti-goals into 'Selbstführung 2026', abandon originals,
    archive their content as a BrainDump."""
    async with get_session() as session:
        area_id = await _area_id(session, user_id, "mental")
        obj, krs, created = await _create_objective_with_krs(
            session, user_id, SELBSTFUEHRUNG_OBJECTIVE, area_id,
        )

        # Find anti-goal objectives still active in mental area
        antis = (await session.execute(
            select(Objective).where(and_(
                Objective.user_id == user_id,
                Objective.title.in_(list(ANTI_GOAL_TITLES)),
                Objective.status == "active",
            ))
        )).scalars().all()

        if antis:
            archive_lines = [
                f"[mental_consolidation_archive] {CONSOL_MARKER}",
                "Folgende 8 Anti-Goals wurden in 'Selbstführung 2026' kollabiert:",
                "",
            ]
            for a in antis:
                a.status = "abandoned"
                a.paused_at = datetime.utcnow()
                a.paused_reason = "v3_audit_consolidation"
                archive_lines.append(f"- #{a.id} {a.title}")
            session.add(BrainDump(
                user_id=user_id,
                raw_input="\n".join(archive_lines),
                processed=True,
                ai_interpretation=(
                    "V3-Audit 2026-05-21: 8 abstrakte Anti-Goals "
                    "im Mental/Emotional-Bereich konsolidiert zu einem "
                    "messbaren Objective 'Selbstführung 2026' mit 4 KRs."
                ),
            ))
            await session.flush()

    return {
        "action": "created" if created else "synced",
        "objective_id": obj.id,
        "kr_count": len(krs),
        "antis_abandoned": len(antis) if antis else 0,
    }


async def op3_bedrock_v2(user_id: int) -> dict:
    """Update bedrock to the V3-audit revision (DE visions, new leitspruch,
    skill-lever priorities, core_line). Auto-archives previous to history."""
    async with get_session() as session:
        profile = await update_bedrock(
            session, user_id, LUKAS_BEDROCK_V2, source="v3_audit_2026_05",
        )
    return {
        "action": "updated",
        "user_id": user_id,
        "history_count": len(profile.bedrock_history or []),
    }


async def run(user_id: int) -> None:
    print(f"\n=== V3 Audit Consolidation for user_id={user_id} ===\n")
    r1 = await op1_money_business(user_id)
    print(f"1. Money/Business: {r1}")
    r2 = await op2_consolidate_mental(user_id)
    print(f"2. Mental consolidation: {r2}")
    r3 = await op3_bedrock_v2(user_id)
    print(f"3. Bedrock v2: {r3}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, default=None,
                        help="Target user id. Default: ALL users.")
    args = parser.parse_args()

    async def go() -> None:
        if args.user_id is not None:
            await run(args.user_id)
            return
        async with get_session() as session:
            targets = list((await session.execute(select(User.id))).scalars().all())
        for uid in targets:
            await run(uid)

    asyncio.run(go())


if __name__ == "__main__":
    main()
