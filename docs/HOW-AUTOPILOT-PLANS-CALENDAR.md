# How the Autopilot Plans your Calendar

**Audience:** Lukas + future-Lukas debugging why a goal didn't land on the calendar.
**Source of truth:** code (this doc is a high-level map, not a spec).
**Last updated:** V3 P04 — 2026-05-21.

---

## TL;DR — what happens when you accept a proposal

```
Goal text (Telegram or Dashboard)
        │
        ▼
OKRProposalDraft (status: draft)
        │  /api/objectives/proposal-drafts/{id}/review (status: accepted)
        ▼
OKRProposalDraft (status: accepted)
        │  /api/objectives/proposal-drafts/{id}/execute
        ▼
execute_accepted_proposal()  ◄── bot/core/proposal_execute.py
        │
        ├─► Objective + KeyResults + Tasks  (DB)
        │
        ├─► Task.due_date set?  ──► CalendarEvent (event_type="deadline",
        │                              linked_task_id=task.id,
        │                              ical_uid="task-deadline-{id}@personal-os")
        │
        ├─► slot_candidates ─► CalendarEvent (event_type="reminder")
        │           │
        │           └─► conflict?  ──► AutopilotNotification
        │                              (type="calendar_conflict")
        │
        ├─► ScheduledReminders
        │
        └─► life_planner.derive_life_artifacts()  ◄── bot/core/life_planner.py
                │
                ├─► Routines  ──► expand_routine_to_calendar()  ◄── bot/core/calendar.py
                │                  │
                │                  └─► 4 weeks ahead × matching weekdays
                │                       (Mo/Mi/Fr × 4 = 12 events)
                │                       CalendarEvent (event_type="routine",
                │                                      linked_routine_id=routine.id,
                │                                      ical_uid="routine-{id}-{date}@personal-os")
                │
                ├─► Shopping items ─► Task (category="shopping")
                │
                └─► Tasks with due_days ─► CalendarEvent (event_type="deadline",
                                                          ical_uid="milestone-...@personal-os")
```

## Which payload fields trigger what

| Field in draft_payload | Side-effect |
|---|---|
| `objective.title` | Objective row |
| `key_results[]` | KeyResult rows |
| `tasks[].title` | Task row |
| `tasks[].due_days` | Task.due_date + deadline CalendarEvent |
| `tasks[].kr_title` | Task.key_result_id (best-match) |
| `routines[].title` + `routines[].frequency` | Routine row + 4-week calendar expansion |
| `weekly_schedule[]` (legacy) | Routine rows |
| `reminders[]` | ScheduledReminder rows |
| `shopping_items[]` | Task rows (category="shopping") |

## Frequency parsing (`parse_frequency_human`)

| Input | Output (weekdays, Mon=0..Sun=6) |
|---|---|
| `Täglich` / `Daily` / `Jeden Tag` | {0,1,2,3,4,5,6} |
| `Mo/Mi/Fr` | {0, 2, 4} |
| `Di, Do` | {1, 3} |
| `Jeden Dienstag` | {1} |
| `wöchentlich` / `weekly` | {0} (defaults Monday) |
| `3x pro Woche` | {0, 2, 4} (heuristic Mo/Mi/Fr) |
| `2x pro Woche` | {1, 3} (heuristic Di/Do) |
| `5x pro Woche` | {0,1,2,3,4} (Mo–Fr) |
| empty / garbage | {0} (safe default) |

See `bot/core/calendar.py:parse_frequency_human`.

## Idempotency

Every CalendarEvent that the executor creates has a deterministic `ical_uid`:

- Task deadlines: `task-deadline-{task_id}@personal-os`
- Routine expansions: `routine-{routine_id}-{YYYY-MM-DD}@personal-os`
- Life-planner milestones: `milestone-obj{obj_id}-{title}-{YYYY-MM-DD}@personal-os`

Re-executing the same draft (or re-expanding the same routine) is safe:
duplicate `ical_uid` inserts hit the unique index and are silently skipped.

## How conflicts are resolved

When a slot_candidate overlaps an existing CalendarEvent for the user:

1. The slot is **not** created.
2. An `AutopilotNotification` row is inserted with:
   - `notification_type = "calendar_conflict"`
   - `title = "Slot-Konflikt: {slot title}"`
   - `body` containing the conflicting event's title + times
   - `source = "proposal_execute"`
3. The notification is visible in the dashboard under autopilot notifications and can be acted on manually.

The executor never overwrites an existing event.

## Manual override

If the autopilot put something in the wrong slot:

- **Single event:** Delete via the dashboard calendar view, or POST a new event manually.
- **Whole routine:** Pause the routine (status="paused"). Already-expanded calendar events stay.
- **Whole goal:** Set Objective.status = "paused" or "abandoned" — does NOT auto-delete calendar events. Run a cleanup query if needed.

## How to debug "my goal didn't land on the calendar"

1. `GET /api/objectives/proposal-drafts/{id}` — was the draft accepted?
2. Check `OKRProposalDraft.executed_at` — was execute() actually called?
3. Check `Task.due_date` for the resulting tasks — populated?
4. Check `CalendarEvent.linked_task_id` and `linked_routine_id` — does anything point to your objective?
5. Check `AutopilotNotification` for `type="calendar_conflict"` — were slots silently dropped due to conflicts?
6. iCal feed: `GET /api/ical/{user_token}` should include the events.

## Tests

- `tests/test_routine_expansion.py` — pure unit tests for `parse_frequency_human`.
- `tests/test_proposal_execute_calendar.py` — integration (requires `PERSONAL_OS_DB_AVAILABLE=1`):
  - `test_execute_creates_calendar_events_for_tasks_with_due_date`
  - `test_execute_creates_calendar_events_for_routines`
  - `test_e2e_payload_to_calendar_events_total`
