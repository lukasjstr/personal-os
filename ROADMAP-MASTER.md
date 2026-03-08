# ROADMAP — Personal OS Autopilot (Master)

Status: living document
Owner: Lukas + MacClaw
Principle: One closed loop: **Goal → Plan → Act → Review → Learn**

This roadmap merges:
- `ROADMAP-ULTIMATE-AUTOPILOT.md` (authoritative ticket queue)
- `ROADMAP.md` (legacy prompts)
- current repo reality (commits shipped)

---

## 0) Shipped (CORE pipeline)

- CORE-6: daily plan integration — `898c93c`
- CORE-7: next-action completion loop — `adb822e`
- CORE-8: app integration skeleton (proposals + cards) — `9c656df`
- CORE-2 Execute: accepted draft → DB side-effects (objective/KRs/tasks + calendar + reminders) — `a8f1355`
- T2: `GET /api/autopilot/today` unified snapshot — `4581b39`
- P0.1: Notification pipeline + enqueue helper (quiet-hours/anti-spam) + ERR-1/ERR-3 fixes — `509d8b1`
- P0.2: Action Queue completion wiring + POST create endpoint — `1a5ed85`
- P0.3: HomeScreen migrated to `/api/autopilot/today` snapshot — `393140b`
- P0.4: CORE-2 execute hardening (idempotency + conflict detection + reminder kinds) — `8f69589`
- P1.2: CRUD everywhere Dashboard (KR inline, reflection, calendar, proposals) — `70eb5e0`

---

## 1) North Star: Closed System Definition

The system is "closed" when these are true:
1. You can input a goal → get a proposal → review/accept → execute → the system schedules work.
2. Every day, the system produces one **Autopilot Today Snapshot** (plan + next action + inbox).
3. Completing an action immediately updates progress and returns the next best action.
4. The system nudges reliably (quiet hours + anti-spam) and is reversible/auditable.
5. Weekly reflection feeds weights back into planning.

---

## 2) Canonical contracts (must not drift)

Single source: `SPEC_AUTOPILOT_API.md`

- ProposalDraft
- ExecuteResponse
- AutopilotTodaySnapshot
- CompletionResponse

Rule: Mobile + Dashboard + Telegram render from the snapshot, not their own bespoke computations.

---

## 3) Execution protocol

For every ticket:
- scoped changes only
- `python3 -m py_compile` on touched backend files
- commit + push
- report hash + next

---

## 4) Roadmap (step-by-step)

### P0 — Make the loop actually run daily (no missing glue)

**P0.1 Autopilot Inbox / Notification pipeline (A1/C3)**
- Ensure `AutopilotNotification` is the single inbox across mobile + dashboard
- Ensure endpoints: list, ack, snooze, counts
- Quiet hours + anti-spam applied before enqueue
- Mobile Notifications tab uses inbox (fix ERR-1)

**P0.2 Action Queue states (A3)**
- Persisted queue items + transitions are correct
- Completion hooks can mark queue items completed

**P0.3 Autopilot Today snapshot parity**
- Make `/api/autopilot/today` the canonical aggregator
- Migrate mobile Home to rely on it (reduces multiple API calls)
- Migrate dashboard cards to rely on it

**P0.4 CORE-2 execute hardening**
- Better idempotency (store `executed_at` + `executed_objective_id` on draft)
- Conflict detection when materializing calendar events
- More accurate reminder typing (map kinds)

### P1 — Deep relations (graph) + control + UX

**P1.1 B1 Task↔Objective relations + migrations (if missing fields / improve)**
- objective_id, parent_task_id, blocked_by_task_id
- objective progress surfaces in UI

**P1.2 CRUD everywhere (Dashboard)**
- edit/delete objectives/tasks/routines/logs/brain dumps

**P1.3 Settings + export**
- profile edit, toggles UI, data export

### P2 — Smarter coaching loop

**P2.1 Reflection feedback injection (A4 / 8.1 subset)**
- weekly priorities affect planner weights

**P2.2 Explainability panel (A5)**
- show "why" for next_action + plan items

**P2.3 Daily suggestions pipeline (8.2)**

### P3 — Reliability & release

**P3.1 E2E smoke tests expanded (G1)**
**P3.2 Monitoring + rollback (G3)**
**P3.3 Incident playbook + kill switches (G4)**

---

## 5) Next tickets (current queue)

All P0 + P1.2 tickets shipped (2026-03-08). Remaining:

1) P1.1 Task↔Objective deep relations (objective_id, parent_task_id, blocked_by_task_id on Task)
2) P1.3 Settings + export (profile edit, toggles UI, data export)
3) P2.1 Reflection feedback injection (weekly priorities → planner weights)
4) P2.2 Explainability panel ("why" for next_action + plan items)
5) P2.3 Daily suggestions pipeline

