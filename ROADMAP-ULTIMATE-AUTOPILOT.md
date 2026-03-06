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

---

## 6) URGENT APP ERRORS (2026-03-05, user-reported)

Process rule: fix as small sequential tickets, each with validate + commit + push.

### ERR-1 Notifications screen load error
- Symptom: `Load error — showing cached data` on Notifications tab
- Check endpoint parity (`/api/notifications`, `/api/autopilot/action-queue`) and response mapping
- Ensure retry path + graceful empty state are both correct

### ERR-2 Fitness tab renders raw HTML/doctype
- Symptom: Fitness screen shows HTML source instead of app UI
- Likely wrong endpoint/content-type handling fallback into web payload
- Add strict JSON/content-type guard + safe parser + robust error UI

### ERR-3 Routines screen hard fail
- Symptom: `Something went wrong. Please try again.`
- Validate routines endpoint contract and mobile mapping
- Add deterministic fallback and typed error handling

### ERR-4 Unknown glyph/placeholder icon (`?`)
- Symptom: question-mark icon appears in FAB/quick-actions context
- Audit icon package and glyph names; replace unsupported glyphs
- Add icon fallback mapping for platform compatibility

### ERR-5 Quick Actions visual polish + IA alignment
- Symptom: quick-actions exist but clarity/discoverability is weak
- Improve labels/descriptions hierarchy and ordering
- Ensure actions map to real backend capabilities

---

## 7) EPIC CORE — Goal → Autopilot Pipeline (P0, STRICT SEQUENCE)

North star: **Goal rein → vollständiger Plan raus → automatische Ausführung → Lernschleife**.

Do not parallelize these tickets; each depends on previous output.

### CORE-1 OKR proposal generator (backend, non-destructive)
- New proposal flow from plain goal text
- Objective + KRs + tasks + routines + milestones + reminder skeleton + suggested slots
- Validation and anti-overgeneration limits

**CORE-1 mini-ticket completion log**
- CORE-1a: `7709f7e` — fallback draft generator models (`bot/core/okr_generator.py`)
- CORE-1b: `2470d55` — read-only draft endpoint (`POST /api/objectives/okr-draft`)
- CORE-1c: `30e4b63` — strict input validation + explicit 400 error mapping

**CORE-1 smoke check (manual quick verify)**
```bash
curl -sS -X POST http://127.0.0.1:8000/api/objectives/okr-draft \
  -H 'Content-Type: application/json' \
  -d '{"source_text":"Improve my fitness consistency","horizon_weeks":4}'
```
Expected: `200` with `{"draft": ...}` payload (fallback-generated structure).

### CORE-2 Review/accept/modify/reject flow (conversation + API)
- Store proposal drafts
- User approval gate before any DB creation
- Accept/modify/reject executors

**CORE-2 progress (mini-tickets)**
- CORE-2a: `8dfc583` — proposal draft persistence scaffold (model + migration)
- CORE-2b: `7e71b42` — draft create/fetch API skeleton
- CORE-2c: `209d2b9` — review status actions (accept/modify/reject)
- CORE-2d: approval-gate guard + execute placeholder (no side-effects)

### CORE-3 Auto calendar generation
- Recurring blocks + milestones + deadlines
- Conflict detection and alternative slot assignment

**CORE-3 progress (mini-tickets)**
- CORE-3a: proposal calendar slot scaffold (model + migration), no auto-scheduling side-effects
- CORE-3b: pure slot candidate generator scaffold (`bot/core/slot_candidates.py`), read-only/no side-effects
- CORE-3c: read-only API preview endpoint for accepted-draft slot candidates (no DB writes/scheduling side-effects)
- CORE-3d: conflict-detection scaffold hooked into slot-candidate preview (read-only, no auto-rescheduling)

### CORE-4 Auto reminder generation
- Reminder factory by KR type/frequency
- Smart conditions + anti-spam constraints in config model

### CORE-5 Reminder engine execution loop
- Due reminder processor, retry, quiet hours, batching
- Personalized template rendering

### CORE-6 Daily plan integration
- Morning brief + evening review fully fed by goal pipeline outputs
- Warning detector + free-slot suggestions

### CORE-7 Next-action completion loop
- Completion hooks update KR/objective progress
- Next unblocked action surfaced immediately

### CORE-8 App integration (mobile + web/PWA)
- Goal proposal/review screens
- Autopilot status/action cards + reminders overview
- Parity across mobile and dashboard

---

## 8) Active execution order now

1. ERR-1
2. ERR-2
3. ERR-3
4. ERR-4
5. ERR-5
6. CORE-1
7. CORE-2
8. CORE-3
9. CORE-4
10. CORE-5
11. CORE-6
12. CORE-7
13. CORE-8
