"""Bootstrap: Gesundheit objective, supplement routine, and full RoutineObjectiveImpact map.

Creates the missing health/energy objective and wires all routines to ALL objectives
they actually influence — the "everything affects everything" principle.

Run: python3 scripts/bootstrap_health_connections.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, and_

from bot.database.connection import get_session
from bot.database.models import (
    CalendarEvent, KeyResult, Objective, Routine,
    RoutineObjectiveImpact, Task, User,
)
from datetime import date, datetime, timedelta

USER_ID = 2


def dt(d: date, h: int, m: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, m)


async def main() -> None:
    async with get_session() as session:

        # ── 1. Gesundheit & Energie Objective ────────────────────────────────
        existing_health = (await session.execute(
            select(Objective).where(and_(
                Objective.user_id == USER_ID,
                Objective.category == "health",
                Objective.status == "active",
            ))
        )).scalar_one_or_none()

        if existing_health:
            health_obj = existing_health
            print(f"ℹ️  Gesundheits-Objective existiert bereits: OBJ#{health_obj.id}")
        else:
            health_obj = Objective(
                user_id=USER_ID,
                title="Gesundheit & Energie",
                description="Körper täglich pflegen: Supplemente, Wasser, Schlaf, Bewegung.",
                category="health",
                status="active",
                target_date=date(2026, 6, 15),
            )
            session.add(health_obj)
            await session.flush()
            print(f"✅ Objective erstellt: OBJ#{health_obj.id} Gesundheit & Energie")

        # ── 2. KRs for health objective ───────────────────────────────────────
        existing_krs = (await session.execute(
            select(KeyResult).where(and_(
                KeyResult.user_id == USER_ID,
                KeyResult.objective_id == health_obj.id,
            ))
        )).scalars().all()
        existing_kr_titles = {kr.title for kr in existing_krs}

        health_krs_spec = [
            dict(title="Tägliche Supplement-Einnahme (Streak)",
                 metric_type="streak", target_value=60, unit="Tage", frequency="daily"),
            dict(title="3L Wasser täglich (Streak)",
                 metric_type="streak", target_value=30, unit="Tage", frequency="daily"),
            dict(title="Schlaf ≥7h täglich (Streak)",
                 metric_type="streak", target_value=30, unit="Tage", frequency="daily"),
        ]

        health_kr_map = {}  # title → kr object
        for spec in health_krs_spec:
            if spec["title"] not in existing_kr_titles:
                kr = KeyResult(
                    user_id=USER_ID,
                    objective_id=health_obj.id,
                    status="active",
                    current_value=0.0,
                    **spec,
                )
                session.add(kr)
                await session.flush()
                health_kr_map[spec["title"]] = kr
                print(f"  ✅ KR#{kr.id}: {kr.title}")
            else:
                existing = next(k for k in existing_krs if k.title == spec["title"])
                health_kr_map[spec["title"]] = existing
                print(f"  ℹ️  KR#{existing.id} bereits vorhanden: {existing.title}")

        supplement_kr = health_kr_map.get("Tägliche Supplement-Einnahme (Streak)")
        water_kr = health_kr_map.get("3L Wasser täglich (Streak)")

        # ── 3. Supplement Routine ─────────────────────────────────────────────
        existing_supp = (await session.execute(
            select(Routine).where(and_(
                Routine.user_id == USER_ID,
                Routine.title.ilike("%supplement%"),
                Routine.status == "active",
            ))
        )).scalar_one_or_none()

        if existing_supp:
            supp_routine = existing_supp
            print(f"ℹ️  Supplement-Routine existiert: Routine#{supp_routine.id}")
        else:
            supp_routine = Routine(
                user_id=USER_ID,
                title="Supplemente nehmen (morgens)",
                frequency_human="täglich",
                linked_key_result_id=supplement_kr.id if supplement_kr else None,
                status="active",
                time_of_day="morning",
                description="Morgen-Stack: Omega-3, Vitamin D3, Magnesium, Kreatin, Zink + weitere laut Protokoll",
            )
            session.add(supp_routine)
            await session.flush()
            print(f"✅ Routine#{supp_routine.id}: Supplemente nehmen")

        # Calendar event for supplement routine this week
        today = date(2026, 3, 17)
        for i in range(6):
            d = today + timedelta(days=i)
            event = CalendarEvent(
                user_id=USER_ID,
                title="💊 Supplemente nehmen (Morgen-Stack)",
                start_time=dt(d, 6, 15),
                end_time=dt(d, 6, 25),
                event_type="routine",
                description="Omega-3, Vitamin D3, Magnesium, Kreatin, Zink laut Protokoll",
                linked_routine_id=supp_routine.id,
            )
            session.add(event)
        print(f"✅ 6 Supplement-Kalender-Events erstellt")

        # ── 4. Load all routines for impact mapping ───────────────────────────
        all_routines = (await session.execute(
            select(Routine).where(Routine.user_id == USER_ID, Routine.status == "active")
        )).scalars().all()
        r_map = {r.title: r.id for r in all_routines}

        def rid(fragment: str) -> int | None:
            for t, i in r_map.items():
                if fragment.lower() in t.lower():
                    return i
            return None

        # ── 5. RoutineObjectiveImpact — the universal connection map ──────────
        # Format: (routine_id, objective_id, impact_score 1-5)
        # "impact_score" shows HOW MUCH this routine affects this objective
        # Higher = more direct impact
        OBJ_PROD = 28   # Produktivität & Kontrolle
        OBJ_FIT = 31    # Körper & Fitness
        OBJ_MIND = 32   # Geist & Wachstum
        OBJ_HEALTH = health_obj.id

        impact_map = [
            # Kraft-Training → Fitness (5), Gesundheit (4)
            (rid("Kraft-Training"), OBJ_FIT, 5),
            (rid("Kraft-Training"), OBJ_HEALTH, 4),
            # Cardio → Fitness (5), Gesundheit (5)
            (rid("Cardio"), OBJ_FIT, 5),
            (rid("Cardio"), OBJ_HEALTH, 5),
            # 8.000 Schritte → Fitness (3), Gesundheit (4)
            (rid("8.000"), OBJ_FIT, 3),
            (rid("8.000"), OBJ_HEALTH, 4),
            # Morgen-Journaling → Geist (5), Produktivität (4)
            (rid("Morgen-Journal"), OBJ_MIND, 5),
            (rid("Morgen-Journal"), OBJ_PROD, 4),
            # Abend-Reflexion → Produktivität (5), Geist (4)
            (rid("Abend-Reflex"), OBJ_PROD, 5),
            (rid("Abend-Reflex"), OBJ_MIND, 4),
            # Abend-Dankbarkeit → Geist (5), Gesundheit (3, mentale Gesundheit)
            (rid("Abend-Dankb"), OBJ_MIND, 5),
            (rid("Abend-Dankb"), OBJ_HEALTH, 3),
            # Sonntagsplanung → Produktivität (5), alle anderen (2)
            (rid("Sonntagsplan"), OBJ_PROD, 5),
            (rid("Sonntagsplan"), OBJ_FIT, 2),
            (rid("Sonntagsplan"), OBJ_MIND, 2),
            # Wöchentliches Lernen → Geist (5)
            (rid("Wöchentliches Lernen"), OBJ_MIND, 5),
            # Top-5 priorisieren → Produktivität (5)
            (rid("Top-5"), OBJ_PROD, 5),
            # Supplemente → Gesundheit (5), Fitness (3)
            (supp_routine.id, OBJ_HEALTH, 5),
            (supp_routine.id, OBJ_FIT, 3),
        ]

        # Clear existing entries first
        existing_impacts = (await session.execute(
            select(RoutineObjectiveImpact).where(RoutineObjectiveImpact.user_id == USER_ID)
        )).scalars().all()
        for e in existing_impacts:
            await session.delete(e)
        await session.flush()

        created_impacts = 0
        for routine_id, objective_id, score in impact_map:
            if routine_id is None or objective_id is None:
                continue
            impact = RoutineObjectiveImpact(
                user_id=USER_ID,
                routine_id=routine_id,
                objective_id=objective_id,
                impact_score=score,
            )
            session.add(impact)
            created_impacts += 1
        await session.flush()
        print(f"✅ {created_impacts} RoutineObjectiveImpact Verknüpfungen erstellt")

        # ── 6. Shopping tasks for supplement objective ────────────────────────
        shopping = [
            dict(title="Omega-3 (Fischöl, 1g/Tag) kaufen",
                 category="shopping", objective_id=health_obj.id,
                 key_result_id=supplement_kr.id if supplement_kr else None, priority=2),
            dict(title="Vitamin D3 (2000 IE/Tag) kaufen",
                 category="shopping", objective_id=health_obj.id,
                 key_result_id=supplement_kr.id if supplement_kr else None, priority=2),
            dict(title="Magnesium (Glycinat, abends) kaufen",
                 category="shopping", objective_id=health_obj.id,
                 key_result_id=supplement_kr.id if supplement_kr else None, priority=2),
            dict(title="Wassertracker-App einrichten oder 2L-Flasche kaufen",
                 category="shopping", objective_id=health_obj.id,
                 key_result_id=water_kr.id if water_kr else None, priority=3),
        ]
        for t in shopping:
            task = Task(user_id=USER_ID, status="todo", **t)
            session.add(task)
        print(f"✅ {len(shopping)} Shopping-Tasks für Gesundheit erstellt")

        await session.commit()

        print(f"\n🚀 Health Bootstrap abgeschlossen!")
        print(f"   OBJ#{health_obj.id}: Gesundheit & Energie")
        print(f"   {len(health_krs_spec)} KRs")
        print(f"   Routine#{supp_routine.id}: Supplemente nehmen")
        print(f"   {created_impacts} Routine↔Objective Verknüpfungen")
        print(f"   {len(shopping)} Shopping-Tasks")


if __name__ == "__main__":
    asyncio.run(main())
