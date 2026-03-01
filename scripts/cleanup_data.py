"""One-time data cleanup after CloudBrain migration."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.database.connection import AsyncSessionLocal
from bot.database.models import Log, Objective, Task
from sqlalchemy import select


async def cleanup():
    async with AsyncSessionLocal() as s:
        # === 1. Fix Log Types ===
        r = await s.execute(select(Log).where(Log.log_type == "general"))
        logs = r.scalars().all()
        for l in logs:
            activity = (l.data.get("activity") or "").lower()
            if activity in ("krafttraining", "kraft"):
                l.log_type = "workout"
                val = l.data.get("value", "?")
                unit = l.data.get("unit", "")
                l.data = {
                    "exercise": "Krafttraining",
                    "duration_min": l.data.get("value"),
                }
                if l.raw_input:
                    l.data["note"] = l.raw_input
                print(f"  Log #{l.id} -> workout (Krafttraining {val}{unit})")
            elif activity == "laufen":
                l.log_type = "workout"
                val = l.data.get("value", "?")
                l.data = {
                    "exercise": "Laufen",
                    "duration_min": l.data.get("value"),
                }
                print(f"  Log #{l.id} -> workout (Laufen {val}min)")
            elif activity == "dankbarkeit":
                l.log_type = "gratitude"
                l.data = {"note": l.raw_input or "Dankbarkeitsübung"}
                print(f"  Log #{l.id} -> gratitude")

        # === 2. Remove Duplicate Logs ===
        dupes = await s.execute(select(Log).where(Log.id.in_([3, 4])))
        for d in dupes.scalars().all():
            await s.delete(d)
            print(f"  Deleted dupe Log #{d.id}")

        # Fix Log #5 to have proper workout data
        log5 = await s.get(Log, 5)
        if log5:
            log5.log_type = "workout"
            log5.data = {"exercise": "Bankdrücken", "weight": 80, "reps": 10, "sets": 3}
            print("  Log #5 -> workout (Bankdrücken 80kg 3x10)")

        # === 3. Fix Objective Categories ===
        cat_map = {
            "Mentales & Emotionales Wohlbefinden": "health",
            "Körper, Fitness & Aussehen": "fitness",
            "Charakter, Bildung & Interessen": "learning",
            "Familie & Freunde": "personal",
            "Romantik & Beziehungen": "personal",
            "Geld, Finanzen & Business": "finance",
            "Lifestyle & Abenteuer": "personal",
            "Wohltätigkeit & Zurückgeben": "personal",
            "Spiritualität & Sinnhaftigkeit": "health",
            "Bildung/Beruf": "learning",
            "Besserer Dozent werden": "learning",
            "Täglich 5 Minuten meditieren": "health",
        }
        r = await s.execute(select(Objective))
        for o in r.scalars().all():
            if o.title in cat_map:
                old = o.category
                o.category = cat_map[o.title]
                print(f'  Objective #{o.id} "{o.title}" {old} -> {o.category}')

        # === 4. Link Tasks to Objectives ===
        r = await s.execute(
            select(Objective).where(Objective.title == "Besserer Dozent werden")
        )
        dozent = r.scalar_one_or_none()
        if dozent:
            teaching_tasks = [
                "Slides vorbereiten", "Unterricht 23.03", "Unterricht 20.04",
                "Unterricht 4.05", "Unterricht 18.05", "Unterricht 1.06",
            ]
            r = await s.execute(select(Task).where(Task.title.in_(teaching_tasks)))
            for t in r.scalars().all():
                t.category = "learning"
                print(f'  Task #{t.id} "{t.title}" -> category=learning')

        # Website tasks
        website_tasks = [
            "Wireframes erstellen", "Farbpalette festlegen", "Logo finalisieren",
            "Texte schreiben", "Bilder auswählen", "Backend fertig", "Frontend fertig",
        ]
        r = await s.execute(select(Task).where(Task.title.in_(website_tasks)))
        for t in r.scalars().all():
            t.category = "business"
            print(f'  Task #{t.id} "{t.title}" -> category=business')

        await s.commit()
        print("\n✅ Cleanup done!")


if __name__ == "__main__":
    asyncio.run(cleanup())
