# ROADMAP — MacClaw Execution Plan for Personal OS

Status: 2026-03-13
Owner: Lukas + MacClaw
Goal: turn Personal OS into a tighter goal→planner→execution→review system with stronger dependency modeling, better planner quality, and production-safe operations.

## Product truths to build around

- Goals, objectives, key results, tasks, routines, and calendar blocks are **not flat lists**.
- They can:
  - depend on each other
  - unlock each other
  - block each other
  - contribute partial progress upward
  - compete for time/energy
- The planner must eventually reason over this graph, not just priorities + due dates.

---

## Epic 1 — Dependency Graph & Causal Planning (P0)

### 1.1 Data model for dependencies
**Outcome:** tasks/objectives can explicitly block/unlock/contribute to other nodes.

**Prompt for Claude Code:**
Implement a dependency graph foundation in Personal OS.

Scope:
- Add database support for explicit relations between goals/objectives/tasks/key-results.
- Support at least these relation types:
  - blocks
  - depends_on
  - contributes_to
  - unlocks
- Keep schema simple and auditable.
- Add backend read/write API endpoints for these relations.
- Update existing objective/task serializers so relation info can be queried without breaking existing consumers.
- Add migration(s), tests if present, and avoid destructive data changes.
- If relevant, expose lightweight relation summaries to dashboard consumers.

Constraints:
- Keep backwards compatibility.
- No fake AI magic yet; just the graph foundation.
- Commit changes when done.

### 1.2 Unblocked next-action engine
**Outcome:** next action is chosen from graph-aware unblocked nodes, not just naive priority.

**Prompt for Claude Code:**
Build a graph-aware next-action engine for Personal OS.

Scope:
- Extend next-action selection so blocked tasks are excluded.
- Prefer tasks that unlock downstream work or contribute to active objectives/key results.
- Return explainability metadata like:
  - why_selected
  - blocked_by
  - unlocks_count
  - contributes_to
- Integrate this into existing next-action responses without breaking current clients.
- Add deterministic fallback behavior when relation data is missing.

Constraints:
- No broad frontend rewrite.
- Preserve current API contracts as much as possible.
- Commit changes when done.

### 1.3 Dashboard relation graph UI
**Outcome:** user can see why something matters.

**Prompt for Claude Code:**
Add a lightweight dependency/impact view to the dashboard.

Scope:
- On objectives/tasks pages, show relation chips or small graph summaries:
  - blocked by X
  - unlocks Y
  - contributes to objective Z
- Keep UI compact and useful, not a giant graph toy.
- Reuse existing design system.
- No markdown tables in user-facing copy.
- Commit changes when done.

---

## Epic 2 — Planner Upgrade toward the “magical” version (P0)

### 2.1 Unified planner contract
**Outcome:** one stable planner response used by Telegram + dashboard + mobile.

**Prompt for Claude Code:**
Create or tighten a unified planner contract for Personal OS.

Scope:
- Add a stable backend endpoint for the daily plan/autopilot snapshot.
- Compose from:
  - open tasks
  - routines
  - calendar events
  - dependency/unblocked state
  - reminders/nudges
- Return a clean contract with sections like:
  - next_action
  - today_plan
  - blockers
  - suggestions
  - progress_summary
- Refactor existing consumers carefully toward this contract.

Constraints:
- Keep current endpoints working where possible.
- Add typed response helpers if useful.
- Commit changes when done.

### 2.2 Free-slot planning with calendar awareness
**Outcome:** real planning around availability.

**Prompt for Claude Code:**
Improve Personal OS daily planning using real calendar-aware free-slot planning.

Scope:
- Use calendar events and durations to identify free windows.
- Match candidate tasks to realistic slots.
- Prefer high-leverage, unblocked work in larger slots.
- Prefer quick wins near meetings or fragmented time.
- Return explanation metadata for why a task/slot was suggested.
- Keep deterministic fallback when data quality is poor.

Constraints:
- Avoid over-automation; suggestions first, not forced scheduling.
- Keep anti-chaos guardrails.
- Commit changes when done.

### 2.3 Morning brief + evening review upgrade
**Outcome:** planner loop becomes a real operating loop.

**Prompt for Claude Code:**
Upgrade morning brief and evening review so they use the newer planner/autopilot signals.

Scope:
- Morning brief should reflect:
  - top priorities
  - free-slot opportunities
  - blockers
  - stale objectives/projects
- Evening review should reflect:
  - completions
  - missed tasks
  - broken streak risk
  - planner drift / why the day diverged
- Reuse existing Telegram delivery patterns.
- Keep messages concise and useful.

Constraints:
- No spammy messaging.
- Respect quiet hours.
- Commit changes when done.

---

## Epic 3 — Reliability / Ops / Contract Consistency (P0)

### 3.1 Alembic hygiene
**Outcome:** migrations stop being messy.

**Prompt for Claude Code:**
Clean up migration hygiene in Personal OS.

Scope:
- Investigate duplicate Alembic revision heads / duplicate revision IDs.
- Make migration history safe and deterministic going forward.
- Do not destroy production data.
- Add documentation note for future migration workflow.
- Commit changes when done.

### 3.2 Smoke tests for core flows
**Outcome:** we can deploy with confidence.

**Prompt for Claude Code:**
Add smoke/integration tests for the highest-value Personal OS flows.

Target flows:
- auth/token access
- dashboard health fetch
- task completion → next_action response
- proposal draft create/review/execute happy path
- calendar/ical settings endpoint

Constraints:
- Keep tests pragmatic.
- Prefer small deterministic fixtures.
- Commit changes when done.

### 3.3 Safe deploy tooling
**Outcome:** deploy becomes one boring reliable command.

**Prompt for Claude Code:**
Improve deploy tooling and docs for Personal OS.

Scope:
- Keep .env-safe deploy behavior.
- Add a small deploy/rollback doc.
- Add preflight checks where useful.
- Avoid touching secrets in repo.
- Commit changes when done.

---

## Epic 4 — Explainability & Trust (P1)

### 4.1 Why-this card everywhere it matters
**Prompt for Claude Code:**
Expand explainability in Personal OS.

Scope:
- For next actions, suggestions, and planner items, expose short “why this?” reasoning.
- Examples: deadline risk, unlocks other tasks, linked to active objective, best fit for available slot.
- Surface this in dashboard where already appropriate.
- Keep reasoning concise.
- Commit changes when done.

### 4.2 Autopilot confidence / fallback clarity
**Prompt for Claude Code:**
Improve autopilot trust signals in Personal OS.

Scope:
- Show when suggestions are AI-derived vs deterministic fallback.
- Add confidence/fallback indicators where useful.
- Avoid overclaiming certainty.
- Commit changes when done.

---

## Execution order

1. Epic 1.1 — dependency graph foundation
2. Epic 1.2 — graph-aware next action
3. Epic 2.1 — unified planner contract
4. Epic 2.2 — free-slot planner
5. Epic 2.3 — morning/evening loop upgrade
6. Epic 3.1 — alembic hygiene
7. Epic 3.2 — smoke tests
8. Epic 3.3 — deploy docs/tooling
9. Epic 4.1 — explainability expansion
10. Epic 4.2 — confidence/fallback clarity

## Rules for execution

- Small atomic commits
- Push after each completed ticket
- Deploy after each meaningful vertical slice
- Smoke-test after deploy
- Do not break Telegram/dashboard/mobile parity without reason
- Prefer additive changes and clear migrations
