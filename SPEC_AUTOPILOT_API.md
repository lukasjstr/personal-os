# SPEC — Autopilot API (contract-first)

Status: draft (2026-03-06)

Goal: Keep mobile + dashboard + Telegram rendering aligned by converging on a small set of stable JSON contracts.

## Proposal Drafts (CORE-2)

### List proposal drafts
`GET /api/objectives/proposal-drafts`

Response: `ProposalDraft[]`

### Create proposal draft
`POST /api/objectives/proposal-drafts`

### Review proposal draft
`POST /api/objectives/proposal-drafts/{draft_id}/review`

### Execute accepted proposal draft (CORE-2 → CORE-3/4 side effects)
`POST /api/objectives/proposal-drafts/{draft_id}/execute`

Response (proposed):
```json
{
  "ok": true,
  "draft_id": 123,
  "status": "executed",
  "created": {
    "objective_id": 1,
    "key_result_ids": [10, 11],
    "task_ids": [100, 101, 102],
    "routine_ids": [],
    "calendar_event_ids": [200, 201],
    "scheduled_reminder_ids": [300, 301]
  }
}
```

## Autopilot Today Snapshot (planned)
`GET /api/autopilot/today`

Response (proposed):
```json
{
  "date": "2026-03-06",
  "next_action": { "type": "task", "id": 123, "title": "...", "reason": "..." },
  "plan": { "generated_by": "ai", "sections": [] },
  "counts": {
    "pending_nudges": 0,
    "pending_reminders": 0,
    "open_tasks": 12
  },
  "progress": {
    "active_objectives": 2,
    "completed_today": 3
  }
}
```

## Completion response (CORE-7)
Task/routine completion endpoints should return:
- `next_action`
- optional `kr_progress` + `objective_completed`

