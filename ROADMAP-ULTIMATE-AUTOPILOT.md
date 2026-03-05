# ROADMAP — Personal OS Autopilot (Ultimate Build)

Status: 2026-03-05
Owner: Lukas + MacClaw
Execution model: **small Claude Code tickets**, each ticket = typecheck + lint + commit + push.

---

## 0) Already done (do not rebuild)

### Mobile foundation done
- Phase 1 complete (scaffold, auth, API shell, tabs)
- Phase 2 complete (Home/Tasks/Calendar/Routines/Fitness/Shopping MVP)
- Phase 3.1–3.3 complete (next-action polish, weekly focus, free-slots planning)
- Extra Home execution improvements already done (task/plan handoff)

> Rule: build on this, no duplicate rewrites.

---

## 1) Product North Star ("Automate your life")

Build one system that can:
1. Understand your goals and constraints
2. Plan your day/week automatically
3. Execute via reminders/automation
4. Learn from behavior and adapt
5. Stay reliable, transparent, and controllable

---

## 2) Master roadmap (small-ticket order)

## EPIC A — Autopilot Core Loop (P0)
**Goal:** plan → act → review loop that runs daily without chaos.

### A1. Notification Pipeline (official old 3.4)
- Trigger Telegram nudges from autopilot outputs
- Mobile surfaces pending nudges/state
- Quiet hours + anti-spam guardrails

### A2. Daily Plan Orchestrator API
- Single endpoint that composes: tasks + routines + calendar + priorities
- Deterministic fallback when AI unavailable

### A3. Action Queue + Execution States
- Planned / suggested / accepted / completed / snoozed
- Persisted across app + backend

### A4. Reflection Feedback Injection
- Weekly reflection priorities directly re-weight daily planner

### A5. Explainability Panel
- "Why this suggestion?" (deadline, priority, streak risk, energy)

---

## EPIC B — Data Model Deep Relations (P0)
**Goal:** true graph of life objects (Goals ↔ Objectives ↔ Tasks ↔ Calendar ↔ Routines).

### B1. Task↔Objective relations + migrations (old 5.1 core)
### B2. Subtasks + blockers + dependency graph API
### B3. Objective auto-task generation with review gate
### B4. Calendar block ↔ Task linkage
### B5. Routine impact scoring (which routines drive which objectives)

---

## EPIC C — Mobile App Becomes Control Center (P0)
**Goal:** mobile-first command cockpit.

### C1. Pull-to-refresh + loading polish across core screens
### C2. Unified error/retry UX + offline-safe cache
### C3. Notification Inbox screen (autopilot decisions + required approvals)
### C4. Day timeline editor (drag blocks / quick reschedule)
### C5. Command palette (fast actions: plan day, dump brain, focus mode)
### C6. In-app review flow (morning check-in, evening review)

---

## EPIC D — Dashboard & CRUD Completion (P1)
**Goal:** full manageability for power use.

### D1. Dashboard quick intelligence cards (old 6.1)
### D2. Full CRUD everywhere (old 6.2)
### D3. Settings expansion + profile + exports (old 6.3)
### D4. Audit log page (every autopilot action + source + timestamp)

---

## EPIC E — Smart Coaching & Automation (P1)
**Goal:** system gets smarter over time.

### E1. Enhanced reflection flow (old 8.1)
### E2. Daily AI suggestions pipeline (old 8.2)
### E3. Behavioral pattern detector (missed routines, context drift)
### E4. Adaptive suggestion timing (when nudges actually work)
### E5. "Autopilot confidence" scoring + escalation rules

---

## EPIC F — Gamification That Actually Helps (P2)
**Goal:** motivation without cringe.

### F1. Achievement engine + unlock logic (old 7.1)
### F2. XP/Level + streak surfaces (old 7.2)
### F3. Goal momentum score (consistency over vanity)

---

## EPIC G — Reliability, Release, Ops (P0)
**Goal:** production-safe.

### G1. E2E smoke tests (old 4.1)
### G2. Android release pipeline (old 4.2)
### G3. Monitoring + error logging + rollback (old 4.3)
### G4. Incident playbook + kill switches for automations
### G5. Data backup/restore drill + migration safety checks

---

## 3) Execution protocol (strict)

For every ticket:
1. Implement only scoped changes
2. `npm run typecheck` + `npm run lint` (and backend tests if touched)
3. Commit (small, atomic)
4. Push
5. Post update: done / next / risks
6. Immediately start next ticket

---

## 4) Suggested next 10 tickets (ready queue)

1. A1 Notification Pipeline (Telegram + mobile state)
2. C1 Pull-to-refresh/loading polish (finish/verify)
3. C2 Unified error/retry/offline UX
4. A2 Daily Plan Orchestrator endpoint + fallback
5. A3 Action queue persistence + statuses
6. B1 Task↔Objective relation migration/API
7. B2 Dependency graph read API + UI indicators
8. D1 Dashboard intelligence cards refresh
9. G1 E2E smoke tests (critical flows)
10. G3 Monitoring + rollback script baseline

---

## 5) Scope guardrails

- Keep monorepo
- Mobile-first UX decisions
- Telegram token auth remains primary
- No breaking backend changes without migration + rollback path
- Every automation must be reversible and auditable
