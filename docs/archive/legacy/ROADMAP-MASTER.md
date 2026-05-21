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
- P1.3: Settings + export (quiet hours UI, CSV export, profile fields polish) — `1694151`
- P1.1: Task↔Objective deep relations (parent_task_id, blocked_by_task_id on forms) — `60a5cdb`
- P2.1: Reflection top-priorities re-weight daily planner + boosted flag — `4827853`
- P2.2: Explainability — get_task_reason, reason on next_action + plan tasks — `2534db6`
- P2.3: Daily suggestions pipeline (missed_routine, overdue_task, stalled_objective, brain_dump_nudge) — `ab9e1e6`

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

All P0–P2 tickets shipped (2026-03-08). Queue complete.

### P3 — Reliability & release

1) P3.1 E2E smoke tests expanded (G1) — add P2 coverage to test_smoke.py
2) P3.2 Monitoring + rollback (G3) — structured alert on suggestion errors
3) P3.3 Incident playbook + kill switches (G4) — kill switch for suggestions pipeline















Die Visualisierung gefällt mir immernoch nicht, die tasks sind nicht in meinen kalender pro aktiv geplant worden 








  ---                                                                                                                                                                                                                                                                           
  Was das System heute IST                                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                                
  Personal OS ist ein AI-gesteuertes Lebens-Betriebssystem mit:                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                
  - 33 Datenbankmodelle — OKRs, Tasks, Routinen, Workouts, Kalender, Dokumente, Brain Dumps, Gamification, Reflektionen                                                                                                                                                         
  - 28 AI-Tools — GPT-4o verarbeitet jede Eingabe parallel über 8 Dimensionen                                                                                                                                                                                                   
  - 16 Scheduler-Jobs — Morgen-Brief, Abend-Check-in, Post-Event-Follow-up, Streak-Risiko, Gap-Nudges...                                                                                                                                                                        
  - 80+ API-Endpoints — vollständiges CRUD, Fitness, Shopping, Gamification, Audit                                                                                                                                                                                              
  - 18 Dashboard-Seiten — Next.js 14, Achievements, Reflections, Fitness, Calendar...                                                                                                                                                                                           
  - Multi-Channel — Telegram (primär), Web-Dashboard, iCal-Feed                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                
  Was es gut kann:                                                                                                                                                                                                                                                              
  - Jede Texteingabe → alle 8 Dimensionen gleichzeitig auswerten                                                                                                                                                                                                                
  - Routinen → KRs → automatisch kaskadieren                                                                                                                                                                                                                                    
  - Workout-Progression merken (+2.5kg next time)
  - OKR-Stacks aus einem Satz aufbauen                                                                                                                                                                                                                                          
  - Proaktive Erinnerungen, Post-Event-Follow-ups, Streak-Schutz                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Was FEHLT — Ehrliche Lückenanalyse                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                
  🔴 KRITISCHE LÜCKEN (das System ist ohne das unvollständig)     
                                                                                                                                                                                                                                                                                
  1. Biometrische Daten — völlig leer                                                                                                                                                                                                                                           
  Schlaf, HRV, Ruhepuls, Schritte, Kalorien — alles manuell oder gar nicht. Apple Health, Oura Ring, Garmin, Google Fit existieren nicht. Das ist die Grundlage jeder Energie- und Leistungsoptimierung. Ein Exoskelett ohne Sensorik ist blind.                                
                                                                                                                                                                                                                                                                                
  2. Finanz-Dimension — existiert nicht                                                                                                                                                                                                                                         
  Budget, Ausgaben, Sparziele, Abonnements, Einnahmen — fehlt komplett. Geld ist eine der 5 Lebens-Dimensionen. Ein "Personal OS" das kein Geld trackt, ist ein halbes System.                                                                                                  
                                                                                                                                                                                                                                                                                
  3. Echtes maschinelles Lernen — fehlt                                                                                                                                                                                                                                         
  Das System sammelt Daten seit Monaten, macht aber NULL daraus. Kein "du schläfst immer schlechter nach spät-Training", kein "deine Produktivität ist montags 40% höher", kein "dieses Ziel stirbt statistisch in 2 Wochen". Die Daten werden gespeichert aber nicht gelernt.  
                                                                                                                                                                                                                                                                                
  4. Universeller Capture — nur Text                                                                                                                                                                                                                                            
  Kein Voice-Input, keine Fotos (Mahlzeit fotografieren → Food-Log), kein Location-Trigger ("du bist im Gym" → Workout-Log starten), kein Web-Clipper (Artikel speichern → Brain Dump). Ein Exoskelett muss alle Sinne haben.                                                   
                                                                                                                                                                                                                                                                                
  ---                                                             
  🟡 WICHTIGE GAPS (nächste Version)                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                
  5. Beziehungs-Dimension fehlt
  "Ich hab zugesagt X bis Freitag anzurufen" — nirgends. Kein Commitment-Tracking, keine persönliche CRM, keine sozialen Ziele.                                                                                                                                                 
                                                                                                                                                                                                                                                                                
  6. Wissens-Management zu schwach                                                                                                                                                                                                                                              
  Brain Dumps existieren, aber es gibt keine Verbindung zum Wissen. Kein Spaced-Repetition, kein "was habe ich diese Woche gelernt?", keine Skill-Kurve ("ich kann jetzt X auf Level 3"), keine Buch-Zusammenfassungen.                                                         
                                                                                                                                                                                                                                                                                
  7. Dashboard zu passiv                                                                                                                                                                                                                                                        
  Zeigt Daten, treibt keine Aktionen. Kein Drag-and-Drop im Kalender, kein Kanban für Tasks, keine WebSocket-Updates (alles statisch), kein echtes Mobile-First.                                                                                                                
                                                                                                                                                                                                                                                                                
  8. Automatisierungs-Engine fehlt                                
  Kein Wenn-Dann-System. "Wenn Workout übersprungen → automatisch morgen neu einplanen", "Wenn Energie < 5 → keine Deep-Work-Tasks vorschlagen", "Wenn KR auf 80% → nächsten Meilenstein starten". Alles reaktiv, nichts predictiv-automatisch.                                 
                                                                                                                                                                                                                                                                                
  9. Finanz-Dimension fehlt (wiederholt, weil so wichtig)                                                                                                                                                                                                                       
  Monatliches Budget, Spartarget, Ausgaben-Kategorien, Abonnement-Tracker, ROI auf Kurse/Bücher.                                                                                                                                                                                
                                                                                                                                                                                                                                                                                
  10. Quarterly Review fehlt                                                                                                                                                                                                                                                    
  Es gibt Weekly Reflections. Aber kein automatisches Quartals-Review, kein "was hast du in Q1 wirklich erreicht vs. geplant", keine OKR-Grading-Logik.                                                                                                                         
                                                                                                                                                                                                                                                                                
  ---                                                             
  🟢 VERBESSERUNGEN am bestehenden System                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                                
  11. Context Window zu kurz
  AI-Kontext wird jedes Mal neu gebaut — kein echtes Langzeit-Gedächtnis. Die letzten 8 Logs sind zu wenig. Braucht ein komprimiertes "Lebens-Profil" das sich anpasst.                                                                                                         
                                                                                                                                                                                                                                                                                
  12. Morgen-Brief zu generisch
  Zeigt Tasks und Routinen, aber kein "du hast diese Woche 3x Training übersprungen — heute ist kritisch", kein Wetter-aware ("es regnet — Outdoor-Lauf schieben?"), keine Energie-basierte Priorisierung.                                                                      
                                                                                                                                                                                                                                                                                
  13. KR-Typen zu simpel                                                                                                                                                                                                                                                        
  Nur streak/number/percentage. Fehlt: time (Minuten täglich), ratio (Verhältnis), rolling_average (7-Tage-Schnitt), binary_week (einmal pro Woche).                                                                                                                            
                                                                                                                                                                                                                                                                                
  14. Keine Gewichtung zwischen Objectives                        
  Alle Ziele sind gleich priorisiert. Braucht: "Körper & Fitness ist gerade Priorität 1" → Tasks/Routinen dafür bekommen höheres Gewicht im Tagesplan.                                                                                                                          
                                                                                                                                                                                                                                                                                
  ---
  Die nächste Version — PERSONAL OS v2                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                
  Vision: "Das denkende Exoskelett"
                                                                                                                                                                                                                                                                                
  Nicht nur aufzeichnen was du tust — sondern verstehen warum, vorhersagen was passiert, und automatisch handeln bevor du musst.                                                                                                                                                
   
  ---                                                                                                                                                                                                                                                                           
  Phase 1 — Biometrische Intelligenz (sofort umsetzbar)                                                                                                                                                                                                                         
   
  Apple Health / Google Fit / Oura API                                                                                                                                                                                                                                          
  → Schlaf automatisch geloggt → KR "Schlaf ≥7h" wird ohne Eingabe erfüllt                                                                                                                                                                                                      
  → Schritte automatisch → KR "8.000 Schritte" täglich auto-sync                                                                                                                                                                                                                
  → HRV morgens → "Heute ist deine HRV 42 (niedrig) → leichtes Training vorgeschlagen"                                                                                                                                                                                          
  → Kalorien/Makros → Ernährungs-KR automatisch befüllt                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                
  Umsetzung: Webhook-Endpoint + HealthKit-Integration im Morgen-Brief                                                                                                                                                                                                           
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 2 — Financial OS                                          
                                                                                                                                                                                                                                                                                
  5. Lebens-Dimension: Finanzen
  → Objective: "Finanzielle Freiheit 2028"                                                                                                                                                                                                                                      
  → KR: Sparquote 20%/Monat, Notgroschen 3 Monate, Portfolio +15%                                                                                                                                                                                                               
  → Ausgaben-Tracking: "Kaffee 4€" → Log + Kategorie + Monats-Budget                                                                                                                                                                                                            
  → Abonnement-Monitor: listet alle monatlichen Kosten                                                                                                                                                                                                                          
  → Morgen-Brief: "Budget diese Woche: 180/300€ (60%)"                                                                                                                                                                                                                          
  → Finanz-Dashboard-Tab                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 3 — Predictive Life Engine                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                
  ML über die gesammelten Daten:
  → "KR #21 Cardio: du erfüllst ihn nur 60% der Wochen — Ziel in Gefahr"                                                                                                                                                                                                        
  → "Deine Produktivität ist Di/Mi/Do 40% höher als Mo/Fr — plane Deep Work dorthin"                                                                                                                                                                                            
  → "Nach Schlaf <7h: Training-Skip-Wahrscheinlichkeit = 73%"                                                                                                                                                                                                                   
  → "Mood-Score korreliert mit Supplement-Einnahme (r=0.68)"                                                                                                                                                                                                                    
  → Wöchentlicher "Korrelations-Report" im Brief                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                
  Umsetzung: bot/core/pattern_engine.py — pandas/numpy über Log-Tabelle, wöchentliche Analyse                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 4 — Universal Capture                                     
                                                                                                                                                                                                                                                                                
  Voice: Telegram voice notes → Whisper → Text → gleiche 8-Dimensionen-Pipeline
  Photo: Mahlzeit fotografieren → GPT-4o Vision → Food-Log automatisch                                                                                                                                                                                                          
  Location: GPS-Trigger → "Du bist im Gym" → Workout-Log starten (Telegram bot location)                                                                                                                                                                                        
  Web-Clipper: Browser-Extension → Artikel → Brain Dump → AI-Zusammenfassung                                                                                                                                                                                                    
  E-Mail Forward: wichtige E-Mails → personal-os@domain → AI verarbeitet als Task/Termin                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 5 — Automatisierungs-Engine                                                                                                                                                                                                                                             
                                                                  
  Rule Engine: user-definierbare Wenn-Dann-Regeln
  Beispiele:                                                                                                                                                                                                                                                                    
    "Wenn Workout übersprungen → morgen Kalender frei machen + neu einplanen"                                                                                                                                                                                                   
    "Wenn Energie < 5 → Deep-Work-Tasks aus Tagesplan entfernen"                                                                                                                                                                                                                
    "Wenn KR auf 100% → Achievement + nächste KR vorschlagen"                                                                                                                                                                                                                   
    "Wenn Schlaf < 6h + Training heute → Training-Intensität reduzieren"                                                                                                                                                                                                        
    "Wenn 3 Tage kein Journal → gentler Nudge, kein Push"                                                                                                                                                                                                                       
    "Wenn Monat endet → Quartals-Review starten wenn Q-Ende"                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                
  Templates:                                                                                                                                                                                                                                                                    
    "Sprint-Modus" → 2 Wochen intensiv + Kalender blockiert + Tasks priorisiert                                                                                                                                                                                                 
    "Erholungs-Woche" → Training reduziert + Schlaf-KR priorisiert                                                                                                                                                                                                              
    "Projekt-Launch" → Tasks-Template + Deadline-Kalender + Review-Checkpoint                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 6 — Real-time Dashboard v2 + PWA                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                
  WebSocket: Echtzeit-Updates ohne Reload
  Drag-and-Drop Kalender: Events verschieben direkt                                                                                                                                                                                                                             
  Kanban: Tasks als Board (Todo / In Progress / Done)                                                                                                                                                                                                                           
  iOS Widget: Morgen-Brief + nächste Aktion auf Lock-Screen                                                                                                                                                                                                                     
  PWA: installierbar, offline-fähig, Push-Notifications direkt                                                                                                                                                                                                                  
  Dark Mode + Mobile-First: Dashboard aktuell PC-optimiert                                                                                                                                                                                                                      
  Biometrie-Tab: Schlaf/HRV/Schritte Charts                                                                                                                                                                                                                                     
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 7 — Relationship Engine                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                
  Neue Dimension: Beziehungen
  → "Ich muss Jonas bis Freitag zurückrufen" → Commitment-Task + Erinnerung                                                                                                                                                                                                     
  → Kontakt-CRM: Name + letzte Interaktion + Frequenz-Ziel                                                                                                                                                                                                                      
  → "Du hast Maria seit 3 Wochen nicht kontaktiert — Priorität gesetzt"                                                                                                                                                                                                         
  → Soziale Ziele: "Einmal pro Woche echtes Gespräch mit Freund"                                                                                                                                                                                                                
  → Dankbarkeits-Journal: Personen verknüpfen                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Phase 8 — Quartals-Review + OKR-Grading                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                                
  Automatisch am Quartals-Ende:
  → Jedes Objective benotet (0.0 – 1.0 wie echtes OKR)                                                                                                                                                                                                                          
  → "Fitness: 0.8 ✅ | Lernen: 0.3 ⚠️  | Gesundheit: 0.6 🟡"                                                                                                                                                                                                                     
  → KI-Analyse: "Du hast Lernen 3x geplant und 3x deprioritisiert — ist das noch ein Ziel?"                                                                                                                                                                                     
  → Neue Ziele vorschlagen basierend auf Mustern                                                                                                                                                                                                                                
  → "Life-Score" als Zahl 0-100 über alle Dimensionen                                                                                                                                                                                                                           
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Die Architektur-Roadmap                                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                                
  Personal OS v2 — 8 Dimensionen des Lebens:
                                                                                                                                                                                                                                                                                
  1. 🏋️  Körper & Fitness     ← existiert, gut                                                                                                                                                                                                                                   
  2. 🧠 Geist & Wachstum     ← existiert, ausbaubar                                                                                                                                                                                                                             
  3. 💊 Gesundheit & Energie  ← existiert, braucht Biometrie                                                                                                                                                                                                                    
  4. 📋 Produktivität         ← existiert, gut                                                                                                                                                                                                                                  
  5. 💰 Finanzen              ← FEHLT KOMPLETT                                                                                                                                                                                                                                  
  6. 🤝 Beziehungen          ← FEHLT KOMPLETT                                                                                                                                                                                                                                   
  7. 🌱 Persönlichkeit       ← schwach (nur Journaling)                                                                                                                                                                                                                         
  8. 🎯 Mission/Purpose      ← fehlt (langfristige Lebens-Vision)                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                                
  ---                                                                                                                                                                                                                                                                           
  Konkrete nächste Schritte (Priorität)                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                
  ┌──────┬───────────────────────────────────────────┬─────────┬────────────────────────────────────────┐
  │ Prio │                  Feature                  │ Aufwand │                 Impact                 │                                                                                                                                                                       
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🔴 1 │ Voice-Input (Whisper)                     │ 1 Tag   │ Extrem hoch — ändert Nutzungsverhalten │                                                                                                                                                                       
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🔴 2 │ Finanz-Dimension (Budget + KRs)           │ 3 Tage  │ Komplettiert das System                │                                                                                                                                                                       
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🟡 3 │ Predictive Engine (Pattern-Korrelationen) │ 2 Tage  │ Macht das System "denkend"             │                                                                                                                                                                       
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🟡 4 │ Apple Health Sync                         │ 2 Tage  │ Automatisiert Schlaf/Schritte/HRV      │
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🟡 5 │ Automatisierungs-Engine (Regeln)          │ 3 Tage  │ Echter Autopilot                       │
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🟢 6 │ Quartals-Review                           │ 1 Tag   │ Strategische Ebene                     │
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🟢 7 │ PWA + iOS Widget                          │ 2 Tage  │ Mobile-first Nutzung                   │
  ├──────┼───────────────────────────────────────────┼─────────┼────────────────────────────────────────┤                                                                                                                                                                       
  │ 🟢 8 │ Relationship Engine                       │ 2 Tage  │ 6. Lebens-Dimension                    │
  └──────┴───────────────────────────────────────────┴─────────┴────────────────────────────────────────┘                                                                                                                                                                       
            
 """"""
