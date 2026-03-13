# Migration Workflow — Personal OS

## Chain structure

Revisions follow a strict linear chain. Every new migration must:
1. Set `down_revision` to the current head revision.
2. Use a unique, sequential `revision` string (e.g. `"021"`).
3. Use `IF NOT EXISTS` / `IF EXISTS` guards in all DDL so migrations are
   safe to re-run or apply on a schema that partially pre-exists.

Current head: **020**

```
001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009
  → 010 → 010b → 010c → 011 → 012 → 013 → 014 → 015
  → 016 → 017 → 018 → 019 → 020
```

## How to create a new migration

```bash
# 1. Write the file manually:
#    bot/database/migrations/versions/NNN_description.py
#    Set revision = "NNN", down_revision = "<current head>"

# 2. Verify the chain is linear (no duplicate heads):
python -m alembic branches   # must return empty
python -m alembic heads      # must show exactly one revision

# 3. Apply locally (optional):
python -m alembic upgrade head

# 4. Deploy to production (see CLAUDE.md):
rsync ... && ssh root@95.111.252.176 "cd /opt/personal-os && source venv/bin/activate && python -m alembic upgrade head"
```

## Naming convention

```
NNN_short_description.py
```

- `NNN` is a zero-padded integer (e.g. `021`, `022`).
- Never reuse a revision ID, even after deleting a file.
- If a migration is split/merged, append a letter suffix: `010b`, `010c`.

## History notes

**2026-03-13 (Epic 3.1 hygiene):** Three files were originally created with the
same revision ID `"010"`:
- `010_autopilot_notifications.py` — kept as canonical `010`
- `010_routine_objective_impacts.py` — renumbered to `010b`
- `010_calendar_task_linkage.py` — renumbered to `010c`

The chain gap (010c was never applied to production) was closed by migration
`020_missing_calendar_task_index.py`.
