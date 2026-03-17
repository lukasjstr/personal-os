"""Bootstrap: create week calendar blocks, tasks, documents for all active goals.

Sets up the full "exoskeleton" for OBJ#28/31/32 — every routine gets a calendar
block, every goal gets concrete tasks, all documents are pre-created.

Run: python3 scripts/bootstrap_goals_week.py
"""
import asyncio
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, and_

from bot.database.connection import get_session
from bot.database.models import CalendarEvent, Routine, Task, User, UserDocument

USER_ID = 2
TODAY = date(2026, 3, 17)  # Tuesday

# ── Fitness splits for this week ─────────────────────────────────────────────
SPLITS = {
    date(2026, 3, 17): ("Pull", "Klimmzüge, Rudern, CA Pushups"),
    date(2026, 3, 18): ("Push", "Dips, Brustpresse, Butterfly"),
    date(2026, 3, 19): ("Beine", "Muscle Up Technik, Pike, Front Lever"),
    date(2026, 3, 20): ("Pull", "Klimmzüge, Rudern, CA Pushups"),
    date(2026, 3, 21): ("Push", "Dips, Brustpresse, Butterfly"),
    date(2026, 3, 22): ("Beine", "Muscle Up Technik, Pike, Front Lever"),
}

# training days: Tue/Thu based on cardio routine (Di/Do) + Kraft Mo/Mi/Fr
# But split rotation runs every day. Let's use the routines as defined:
# Kraft: Mo/Mi/Fr → this week: Wed Mar 18, Fri Mar 20 (Mon Mar 16 already past)
# Cardio: Di/Do → Tue Mar 17, Thu Mar 19
KRAFT_DAYS = [date(2026, 3, 18), date(2026, 3, 20)]
CARDIO_DAYS = [date(2026, 3, 17), date(2026, 3, 19)]
ALL_DAYS = [date(2026, 3, 17), date(2026, 3, 18), date(2026, 3, 19),
            date(2026, 3, 20), date(2026, 3, 21), date(2026, 3, 22)]


def dt(d: date, h: int, m: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, m)


async def main() -> None:
    async with get_session() as session:
        # Load routine IDs
        routines = (await session.execute(
            select(Routine).where(Routine.user_id == USER_ID, Routine.status == "active")
        )).scalars().all()
        r_by_title = {r.title: r.id for r in routines}

        def rid(title_fragment: str) -> int | None:
            for t, i in r_by_title.items():
                if title_fragment.lower() in t.lower():
                    return i
            return None

        # ── Section A: Calendar events ────────────────────────────────────────
        events_to_create = []

        for d in ALL_DAYS:
            # Morgen-Journaling 06:30–06:50
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title="📓 Morgen-Journaling (10min)",
                start_time=dt(d, 6, 30),
                end_time=dt(d, 6, 50),
                event_type="routine",
                description="Reflexion: Was will ich heute erreichen? Was lerne ich gerade?",
                linked_routine_id=rid("Morgen-Journal"),
            ))
            # Top-5 priorisieren 06:50–07:00
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title="🎯 Top-5 Tasks priorisieren",
                start_time=dt(d, 6, 50),
                end_time=dt(d, 7, 0),
                event_type="routine",
                description="Autopilot: Top-5 für heute festlegen",
                linked_routine_id=rid("Top-5"),
            ))
            # 8.000 Schritte — Mittagsspaziergang 12:00–12:30
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title="🚶 Mittagsspaziergang (8.000 Schritte Ziel)",
                start_time=dt(d, 12, 0),
                end_time=dt(d, 12, 30),
                event_type="routine",
                description="Täglich 8.000 Schritte — Mittagsrunde nutzen",
                linked_routine_id=rid("8.000 Schritte"),
            ))
            # Abend-Reflexion 21:00–21:15
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title="🌙 Abend-Reflexion (5min)",
                start_time=dt(d, 21, 0),
                end_time=dt(d, 21, 15),
                event_type="routine",
                description="30-Tage-Streak: Was lief heute gut? Was verbesserst du morgen?",
                linked_routine_id=rid("Abend-Reflex"),
            ))
            # Abend-Dankbarkeit 21:15–21:25
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title="🙏 Abend-Dankbarkeit (3 Dinge)",
                start_time=dt(d, 21, 15),
                end_time=dt(d, 21, 25),
                event_type="routine",
                description="3 Dinge für die du heute dankbar bist — direkt in Telegram schreiben",
                linked_routine_id=rid("Abend-Dankb"),
            ))

        # Kraft-Training blocks (Mi, Fr) with exact split name
        for d in KRAFT_DAYS:
            split_name, exercises = SPLITS[d]
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title=f"💪 Kraft: {split_name} — {exercises}",
                start_time=dt(d, 14, 0),
                end_time=dt(d, 15, 0),
                event_type="training",
                description=f"Split: {split_name} | Übungen: {exercises}",
                linked_routine_id=rid("Kraft-Training"),
            ))

        # Cardio blocks (Di, Do)
        for d in CARDIO_DAYS:
            events_to_create.append(CalendarEvent(
                user_id=USER_ID,
                title="🏃 Cardio — 30min Laufen oder Radfahren",
                start_time=dt(d, 7, 0),
                end_time=dt(d, 7, 45),
                event_type="training",
                description="Ziel: 30+ Minuten moderate Intensität. KR: 2x/Woche Cardio",
                linked_routine_id=rid("Cardio"),
            ))

        # Wöchentliches Lernen — Saturday
        events_to_create.append(CalendarEvent(
            user_id=USER_ID,
            title="📚 Wöchentliches Lernen (60min Buch/Kurs/Podcast)",
            start_time=dt(date(2026, 3, 21), 10, 0),
            end_time=dt(date(2026, 3, 21), 11, 0),
            event_type="routine",
            description="Fokuszeit für das Buch/Kurs des Monats. KR: 1 Buch/Kurs pro Monat",
            linked_routine_id=rid("Wöchentliches Lernen"),
        ))

        # Sonntagsplanung — Sunday
        events_to_create.append(CalendarEvent(
            user_id=USER_ID,
            title="📋 Sonntagsplanung — Woche reviewen & planen",
            start_time=dt(date(2026, 3, 22), 18, 0),
            end_time=dt(date(2026, 3, 22), 19, 0),
            event_type="routine",
            description="Wochenreview: OKR-Fortschritt, Top-5 nächste Woche, Freier Abend einplanen",
            linked_routine_id=rid("Sonntagsplan"),
        ))

        # Freier Abend diese Woche — Friday evening
        events_to_create.append(CalendarEvent(
            user_id=USER_ID,
            title="🛋️ Freier Abend — kein Handy, kein Work",
            start_time=dt(date(2026, 3, 20), 19, 0),
            end_time=dt(date(2026, 3, 20), 22, 0),
            event_type="reminder",
            description="KR#18: Freier Abend/Woche. Abschalten. Keine Arbeit nach 19h.",
        ))

        for ev in events_to_create:
            session.add(ev)
        await session.flush()
        print(f"✅ {len(events_to_create)} Kalender-Events erstellt")

        # ── Section B: Documents ──────────────────────────────────────────────
        docs_to_create = [
            {
                "title": "Tagebuch",
                "emoji": "📓",
                "sort_order": 1,
                "content": (
                    "# Tagebuch\n\n"
                    "Tägliche Reflexionen, Gedanken und Einsichten.\n"
                    "Einträge werden automatisch hinzugefügt wenn du deinen Tag reflektierst.\n\n"
                    "---"
                ),
            },
            {
                "title": "Dankbarkeit",
                "emoji": "🙏",
                "sort_order": 2,
                "content": (
                    "# Dankbarkeit\n\n"
                    "Täglich 3 Dinge für die du dankbar bist.\n"
                    "Abends als Routine — verknüpft mit KR#25 Wöchentliche Dankbarkeitspraxis.\n\n"
                    "---"
                ),
            },
            {
                "title": "Wochenreview",
                "emoji": "📋",
                "sort_order": 3,
                "content": (
                    "# Wochenreview-Vorlage\n\n"
                    "## Was lief diese Woche gut?\n\n"
                    "## Was hätte ich besser machen können?\n\n"
                    "## OKR-Fortschritt\n"
                    "- Produktivität & Kontrolle (OBJ#28): \n"
                    "- Körper & Fitness (OBJ#31): \n"
                    "- Geist & Wachstum (OBJ#32): \n\n"
                    "## Top-3 Fokus nächste Woche\n"
                    "1. \n2. \n3. \n\n"
                    "---"
                ),
            },
            {
                "title": "Trainingsplan",
                "emoji": "🏋️",
                "sort_order": 4,
                "content": (
                    "# Trainingsplan\n\n"
                    "## Split-Rotation: Beine → Pull → Push (täglich, kein Ruhetag)\n\n"
                    "### Beine\n"
                    "- Muscle Up – Technik\n- Pike – Technik\n- Front Lever – Technik\n- Beinpresse – Pendulum\n\n"
                    "### Pull\n"
                    "- Klimmzüge (Pull)\n- Rudern\n- CA Pushups / Überzüge\n- Breites Rudern\n\n"
                    "### Push\n"
                    "- Dips\n- Brustpresse\n- Butterfly\n- Seitheben (+ Schulter)\n\n"
                    "## Zielgewichte & Fortschritt\n"
                    "_(hier eigene Gewichte + Wiederholungen eintragen)_\n\n"
                    "---"
                ),
            },
        ]

        created_docs = 0
        for doc_data in docs_to_create:
            existing = (await session.execute(
                select(UserDocument).where(and_(
                    UserDocument.user_id == USER_ID,
                    UserDocument.title == doc_data["title"],
                ))
            )).scalar_one_or_none()
            if not existing:
                session.add(UserDocument(user_id=USER_ID, **doc_data))
                created_docs += 1
        await session.flush()
        print(f"✅ {created_docs} Dokumente erstellt")

        # ── Section C: Tasks — concrete, specific, linked ──────────────────────
        tasks_to_create = [
            # OBJ#28 Produktivität
            dict(title="Reflexions-Template schreiben: 3 Fragen für jeden Abend",
                 objective_id=28, key_result_id=19, priority=1,
                 due_date=date(2026, 3, 17),
                 description="Konkrete 3 Fragen die du jeden Abend beantwortest (z.B.: Was lief gut? Was verbesserst du? Was dankst du?)"),
            dict(title="Sonntagsplanung KW12 durchführen (Wochenreview ausfüllen)",
                 objective_id=28, key_result_id=16, priority=1,
                 due_date=date(2026, 3, 22),
                 description="Wochenreview-Dokument ausfüllen. OKR-Fortschritt eintragen. Top-3 nächste Woche."),
            dict(title="System-Review: alle 12 offenen Tasks prüfen — löschen oder due_date setzen",
                 objective_id=28, key_result_id=17, priority=2,
                 due_date=date(2026, 3, 19),
                 description="Jede offene Task: relevant? Wenn ja → KR verknüpfen + due_date. Sonst → löschen."),
            dict(title="Freien Abend Fr 20.03 schützen — nichts planen, Handy weg um 19h",
                 objective_id=28, key_result_id=18, priority=2,
                 due_date=date(2026, 3, 20)),

            # OBJ#31 Fitness
            dict(title="Heutiges Training absolvieren: Pull Day — Klimmzüge, Rudern, CA Pushups",
                 objective_id=31, key_result_id=20, priority=1,
                 due_date=date(2026, 3, 17),
                 description="Danach: Workout in Telegram loggen → KR#20 +1"),
            dict(title="Gewichte notieren: aktuelles Niveau + Zielgewichte für nächste 4 Wochen",
                 objective_id=31, key_result_id=20, priority=2,
                 due_date=date(2026, 3, 18),
                 description="Im Trainingsplan-Dokument eintragen"),
            dict(title="Schrittzähler einrichten: Apple Health oder App aktivieren + Ziel 8.000/Tag",
                 objective_id=31, key_result_id=22, priority=2,
                 due_date=date(2026, 3, 18)),
            dict(title="Cardio heute Di: 30min Laufen oder Radfahren absolvieren",
                 objective_id=31, key_result_id=21, priority=1,
                 due_date=date(2026, 3, 17),
                 description="Danach loggen: log_workout + KR#21 +1"),
            dict(title="Ernährungsplan: Proteinziel berechnen (Körpergewicht × 1.8g) und täglich tracken",
                 objective_id=31, key_result_id=20, priority=3,
                 due_date=date(2026, 3, 20)),

            # OBJ#32 Geist & Wachstum
            dict(title="Morgen-Journaling heute: Was lerne ich gerade? Was will ich heute erreichen?",
                 objective_id=32, key_result_id=23, priority=1,
                 due_date=date(2026, 3, 17),
                 description="In Telegram schreiben → wird automatisch im Tagebuch gespeichert"),
            dict(title="Buch für März auswählen und erste 20 Seiten lesen",
                 objective_id=32, key_result_id=24, priority=1,
                 due_date=date(2026, 3, 18),
                 description="Empfehlungen: Atomic Habits, Deep Work, Die 1% Methode — oder eigene Wahl"),
            dict(title="Podcast-/Kurs-Liste für wöchentliches Lernen zusammenstellen (3 Optionen)",
                 objective_id=32, key_result_id=24, priority=3,
                 due_date=date(2026, 3, 21)),
            dict(title="Dankbarkeit heute Abend: 3 konkrete Dinge aufschreiben",
                 objective_id=32, key_result_id=25, priority=1,
                 due_date=date(2026, 3, 17),
                 description="Um 21:15 → Telegram öffnen → 3 Sätze tippen → automatisch gespeichert"),
            dict(title="Lernrückblick KW12: Was habe ich diese Woche gelernt? (5 Key-Takeaways)",
                 objective_id=32, key_result_id=24, priority=2,
                 due_date=date(2026, 3, 22)),
        ]

        # Shopping tasks for fitness
        shopping_tasks = [
            dict(title="Proteinpulver kaufen (Whey, mind. 2kg)", category="shopping",
                 objective_id=31, key_result_id=20, priority=2),
            dict(title="Sportflasche (mind. 0.75L für Training)", category="shopping",
                 objective_id=31, key_result_id=20, priority=3),
            dict(title="Foam Roller kaufen (Regeneration nach Krafttraining)", category="shopping",
                 objective_id=31, key_result_id=20, priority=4),
        ]

        created_tasks = 0
        for t in tasks_to_create + shopping_tasks:
            task = Task(
                user_id=USER_ID,
                status="todo",
                category=t.get("category", "personal"),
                **{k: v for k, v in t.items() if k != "category"},
            )
            session.add(task)
            created_tasks += 1
        await session.flush()
        print(f"✅ {created_tasks} Tasks erstellt")

        await session.commit()
        print("\n🚀 Bootstrap abgeschlossen!")
        print(f"   {len(events_to_create)} Kalender-Events")
        print(f"   {created_docs} Dokumente")
        print(f"   {created_tasks} Tasks")


if __name__ == "__main__":
    asyncio.run(main())
