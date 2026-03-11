# BUILD: Goal Coach — Autopilot Goal-Setting Wizard

## Vision
The user types a goal. An AI coach asks 3 clarifying questions.
Based on the answers, it generates a full plan: Objective, measurable Key Results, concrete Tasks,
Calendar blocks, Reminders, and detects Synergies with existing goals.
One click → everything is activated. This is the core autopilot loop.

## Git config (ALWAYS use this for all commits)
git config user.name lukasjstr
git config user.email lukasjstr@gmail.com

---

## PART 1 — Favicon (5 min)

### File: `dashboard/public/favicon.svg`
Create this file:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <text y="26" font-size="26">🎯</text>
</svg>
```

### File: `dashboard/src/app/layout.tsx`
Add after the existing `<link rel="manifest"...>` line:
```tsx
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="icon" href="/icon-192.png" type="image/png" />
```

---

## PART 2 — Backend: Real GPT-powered Goal Generation

### File: `bot/api/routes.py` — add these endpoints

#### 2a. POST /api/goals/generate
This is the core endpoint. It receives the user's goal + their clarifying answers,
loads existing objectives for synergy detection, calls GPT-4o-mini with a rich prompt,
saves an OKRProposalDraft, and returns it.

```python
class GoalGenerateBody(BaseModel):
    goal: str                          # "Ich will 5kg Muskelmasse aufbauen"
    why: Optional[str] = None          # "Weil ich mehr Energie will"
    timeframe: Optional[str] = None    # "In 3 Monaten"
    current_state: Optional[str] = None  # "Ich trainiere 1x pro Woche"

@router.post("/goals/generate")
async def generate_goal_plan(
    body: GoalGenerateBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a full OKR plan using GPT, save as ProposalDraft, return it."""
    import json as _json
    import os
    from openai import AsyncOpenAI
    from datetime import date as _date, timedelta

    # Load existing objectives for synergy detection
    existing_result = await session.execute(
        select(Objective).where(Objective.user_id == user.id, Objective.status == "active")
    )
    existing_objs = existing_result.scalars().all()
    existing_titles = [o.title for o in existing_objs]

    today = _date.today().isoformat()
    
    system_prompt = """Du bist ein strategischer Life-Coach und OKR-Experte.
Du hilfst dem Nutzer, ein konkretes, messbares Ziel zu definieren.
Antworte immer auf Deutsch. Sei präzise und actionable.
Generiere ECHTE, spezifische Metriken — keine vagen Aussagen."""

    user_prompt = f"""Heute ist: {today}
Bestehendes Ziel-Portfolio des Nutzers: {', '.join(existing_titles) if existing_titles else 'Noch keine Ziele'}

Neues Ziel des Nutzers:
- Was: {body.goal}
- Warum: {body.why or 'Nicht angegeben'}
- Zeitrahmen: {body.timeframe or 'Nicht angegeben (verwende 90 Tage)'}
- Aktueller Stand: {body.current_state or 'Nicht angegeben'}

Generiere einen vollständigen OKR-Plan als JSON. Antworte NUR mit diesem JSON:
{{
  "objective": {{
    "title": "Klarer, inspirierender Ziel-Titel (max 80 Zeichen)",
    "description": "1-2 Sätze warum das wichtig ist",
    "category": "health|fitness|business|personal|finance|learning|relationships",
    "target_date": "YYYY-MM-DD",
    "emoji": "passendes Emoji"
  }},
  "key_results": [
    {{
      "title": "Messbares Key Result mit konkretem Zielwert",
      "metric_type": "number|percentage|boolean|streak",
      "target_value": 10,
      "current_value": 0,
      "unit": "kg|mal|%|Stunden|etc",
      "why": "Warum dieses KR wichtig ist"
    }}
  ],
  "tasks": [
    {{
      "title": "Konkreter, actionable Task",
      "priority": 1,
      "due_days": 7,
      "category": "Passende Kategorie"
    }}
  ],
  "weekly_schedule": [
    {{
      "day": "Montag",
      "activity": "Was konkret zu tun ist",
      "duration_min": 60
    }}
  ],
  "synergies": [
    {{
      "existing_goal": "Titel des bestehenden Ziels",
      "connection": "Wie hängen sie zusammen"
    }}
  ],
  "motivation_message": "Persönliche, motivierende Nachricht an den Nutzer (2-3 Sätze)",
  "first_step": "Der allerste konkrete Schritt, den der Nutzer HEUTE tun kann"
}}

Regeln:
- 3-5 Key Results (messbar, spezifisch)
- 5-8 Tasks (konkret, mit Deadline in Tagen)
- Wöchentlicher Zeitplan wenn es ein Habit/Training-Ziel ist
- Synergien nur wenn wirklich relevant (nicht erzwingen)
- target_date basierend auf dem angegebenen Zeitrahmen (default: heute + 90 Tage)"""

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key nicht konfiguriert")

    client = AsyncOpenAI(api_key=openai_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    
    plan = _json.loads(response.choices[0].message.content)
    
    # Save as OKRProposalDraft
    draft = OKRProposalDraft(
        user_id=user.id,
        source_text=body.goal,
        draft_payload=plan,
        status="pending",
    )
    session.add(draft)
    await session.flush()
    
    return {
        "draft_id": draft.id,
        "plan": plan,
    }
```

#### 2b. POST /api/goals/clarify
Returns AI-generated clarifying questions for a given goal (used in Step 2 of the wizard):

```python
class GoalClarifyBody(BaseModel):
    goal: str

@router.post("/goals/clarify")
async def get_clarifying_questions(
    body: GoalClarifyBody,
    user: User = Depends(get_current_user),
) -> dict:
    """Return 3 clarifying questions for the given goal."""
    import os
    from openai import AsyncOpenAI

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        # Fallback questions
        return {"questions": [
            {"id": "why", "label": "Warum ist dir das wichtig?", "placeholder": "Motivation, tiefer Grund..."},
            {"id": "timeframe", "label": "Bis wann willst du es erreichen?", "placeholder": "z.B. in 3 Monaten, bis Ende Jahr..."},
            {"id": "current_state", "label": "Wo stehst du gerade?", "placeholder": "Dein aktueller Stand, was hast du schon versucht..."},
        ]}

    client = AsyncOpenAI(api_key=openai_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""Ziel des Nutzers: "{body.goal}"

Generiere 3 kurze, präzise Rückfragen auf Deutsch, die helfen dieses Ziel besser zu verstehen.
Antworte NUR mit JSON:
{{"questions": [
  {{"id": "why", "label": "Frage 1 (max 60 Zeichen)", "placeholder": "Beispielantwort"}},
  {{"id": "timeframe", "label": "Frage 2 (Zeitbezug)", "placeholder": "Beispielantwort"}},
  {{"id": "current_state", "label": "Frage 3 (aktueller Stand)", "placeholder": "Beispielantwort"}}
]}}"""
        }],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    import json as _json
    return _json.loads(response.choices[0].message.content)
```

**After adding both endpoints:** run `python3 -m py_compile bot/api/routes.py` — must pass.

---

## PART 3 — Frontend: Goal Coach Wizard

### File: `dashboard/src/app/goals/new/page.tsx` (NEW FILE)

This is a beautiful 3-step wizard. Full implementation:

```tsx
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ArrowRight, ArrowLeft, Sparkles, Check, Zap, Target, Calendar, Link2 } from "lucide-react";

// Types
interface Question { id: string; label: string; placeholder: string; }
interface KR { title: string; metric_type: string; target_value: number | null; current_value?: number; unit: string | null; why?: string; }
interface Task { title: string; priority: number; due_days: number; category?: string; }
interface WeekDay { day: string; activity: string; duration_min: number; }
interface Synergy { existing_goal: string; connection: string; }
interface Plan {
  objective: { title: string; description: string; category: string; target_date: string; emoji: string; };
  key_results: KR[];
  tasks: Task[];
  weekly_schedule: WeekDay[];
  synergies: Synergy[];
  motivation_message: string;
  first_step: string;
}

const STEP_LABELS = ["Dein Ziel", "Verfeinern", "Dein Plan"];

export default function NewGoalPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);

  // Step 1
  const [goalText, setGoalText] = useState("");

  // Step 2
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loadingQuestions, setLoadingQuestions] = useState(false);

  // Step 3
  const [plan, setPlan] = useState<Plan | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [editedPlan, setEditedPlan] = useState<Plan | null>(null);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [done, setDone] = useState(false);

  // Step 1 → 2: get clarifying questions
  const handleGoalSubmit = async () => {
    if (!goalText.trim()) return;
    setLoadingQuestions(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || window.location.origin}/api/goals/clarify`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("api_token") || ""}` },
        body: JSON.stringify({ goal: goalText }),
      });
      const data = await res.json();
      setQuestions(data.questions ?? [
        { id: "why", label: "Warum ist dir das wichtig?", placeholder: "Deine Motivation..." },
        { id: "timeframe", label: "Bis wann willst du es erreichen?", placeholder: "z.B. in 3 Monaten..." },
        { id: "current_state", label: "Wo stehst du gerade?", placeholder: "Dein aktueller Stand..." },
      ]);
      setStep(2);
    } catch {
      // fallback questions
      setQuestions([
        { id: "why", label: "Warum ist dir das wichtig?", placeholder: "Deine Motivation..." },
        { id: "timeframe", label: "Bis wann willst du es erreichen?", placeholder: "z.B. in 3 Monaten..." },
        { id: "current_state", label: "Wo stehst du gerade?", placeholder: "Dein aktueller Stand..." },
      ]);
      setStep(2);
    } finally {
      setLoadingQuestions(false);
    }
  };

  // Step 2 → 3: generate plan
  const handleGeneratePlan = async () => {
    setLoadingPlan(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || window.location.origin}/api/goals/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("api_token") || ""}` },
        body: JSON.stringify({ goal: goalText, ...answers }),
      });
      const data = await res.json();
      setPlan(data.plan);
      setEditedPlan(data.plan);
      setDraftId(data.draft_id);
      setStep(3);
    } finally {
      setLoadingPlan(false);
    }
  };

  // Step 3: execute plan
  const handleExecute = async () => {
    if (!draftId) return;
    setExecuting(true);
    try {
      // First accept, then execute
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || window.location.origin}/api/objectives/proposal-drafts/${draftId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("api_token") || ""}` },
        body: JSON.stringify({ action: "accept" }),
      });
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || window.location.origin}/api/objectives/proposal-drafts/${draftId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("api_token") || ""}` },
        body: "{}",
      });
      setDone(true);
    } finally {
      setExecuting(false);
    }
  };

  if (done) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="text-6xl mb-6">🚀</div>
        <h1 className="text-2xl font-bold text-white mb-3">Ziel aktiviert!</h1>
        <p className="text-zinc-400 mb-8 max-w-sm">Dein Plan ist live. Tasks wurden erstellt, Erinnerungen gesetzt. Leg los!</p>
        <div className="flex gap-3">
          <button onClick={() => router.push("/objectives")} className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors">
            Ziele ansehen →
          </button>
          <button onClick={() => { setStep(1); setGoalText(""); setDone(false); setPlan(null); }} className="px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
            Weiteres Ziel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Progress */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          {STEP_LABELS.map((label, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors",
                step > i + 1 ? "bg-green-600 text-white" : step === i + 1 ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-500"
              )}>
                {step > i + 1 ? <Check size={12} /> : i + 1}
              </div>
              <span className={cn("text-sm hidden sm:block", step === i + 1 ? "text-white font-medium" : "text-zinc-500")}>
                {label}
              </span>
              {i < 2 && <div className="w-12 h-px bg-zinc-700 ml-2" />}
            </div>
          ))}
        </div>
      </div>

      {/* Step 1: Goal Input */}
      {step === 1 && (
        <div>
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">🎯</div>
            <h1 className="text-2xl font-bold text-white mb-2">Was willst du erreichen?</h1>
            <p className="text-zinc-400 text-sm">Beschreib dein Ziel in eigenen Worten — ich mach daraus einen konkreten Plan.</p>
          </div>
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6">
            <textarea
              value={goalText}
              onChange={(e) => setGoalText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && e.metaKey && goalText.trim()) handleGoalSubmit(); }}
              placeholder="z.B. Ich will in 3 Monaten 5kg Muskelmasse aufbauen und mich fitter fühlen..."
              rows={4}
              autoFocus
              className="w-full bg-transparent text-white text-lg placeholder:text-zinc-600 focus:outline-none resize-none leading-relaxed"
            />
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-zinc-800">
              <span className="text-zinc-600 text-xs">⌘↵ zum Weiter</span>
              <button
                onClick={handleGoalSubmit}
                disabled={!goalText.trim() || loadingQuestions}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors disabled:opacity-40"
              >
                {loadingQuestions ? (
                  <><span className="animate-spin text-base">⟳</span> Analysiere...</>
                ) : (
                  <>Weiter <ArrowRight size={16} /></>
                )}
              </button>
            </div>
          </div>
          <div className="mt-6 grid grid-cols-3 gap-3">
            {[
              { emoji: "💪", text: "Fitness & Sport" },
              { emoji: "📈", text: "Business & Karriere" },
              { emoji: "🧠", text: "Persönlichkeit" },
              { emoji: "💰", text: "Finanzen" },
              { emoji: "📚", text: "Lernen & Skills" },
              { emoji: "❤️", text: "Beziehungen" },
            ].map((item) => (
              <button
                key={item.text}
                onClick={() => setGoalText((v) => v ? v : `${item.emoji} `)}
                className="flex items-center gap-2 px-3 py-2.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-xl text-zinc-400 hover:text-white text-sm transition-colors text-left"
              >
                <span>{item.emoji}</span>
                <span>{item.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 2: Clarifying Questions */}
      {step === 2 && (
        <div>
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">🤔</div>
            <h1 className="text-2xl font-bold text-white mb-2">Kurz präzisieren</h1>
            <p className="text-zinc-400 text-sm">3 kurze Fragen, damit ich dir einen wirklich guten Plan machen kann.</p>
          </div>
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl px-3 py-1 mb-4">
            <div className="px-3 py-3 text-zinc-400 text-sm flex items-start gap-2">
              <span className="text-lg shrink-0">💬</span>
              <span className="italic">"{goalText}"</span>
            </div>
          </div>
          <div className="space-y-4">
            {questions.map((q) => (
              <div key={q.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <label className="block text-white font-medium mb-3">{q.label}</label>
                <textarea
                  value={answers[q.id] ?? ""}
                  onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                  placeholder={q.placeholder}
                  rows={2}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3 mt-6">
            <button onClick={() => setStep(1)} className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
              <ArrowLeft size={16} /> Zurück
            </button>
            <button
              onClick={handleGeneratePlan}
              disabled={loadingPlan}
              className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-medium transition-all disabled:opacity-40"
            >
              {loadingPlan ? (
                <><span className="animate-pulse">✨</span> KI generiert deinen Plan...</>
              ) : (
                <><Sparkles size={16} /> Plan generieren</>
              )}
            </button>
          </div>
          <p className="text-zinc-600 text-xs text-center mt-3">Fragen sind optional — du kannst sie auch leer lassen</p>
        </div>
      )}

      {/* Step 3: Plan Review */}
      {step === 3 && editedPlan && (
        <div>
          <div className="text-center mb-6">
            <div className="text-4xl mb-2">{editedPlan.objective.emoji || "🎯"}</div>
            <h1 className="text-xl font-bold text-white mb-1">{editedPlan.objective.title}</h1>
            <p className="text-zinc-400 text-sm max-w-lg mx-auto">{editedPlan.objective.description}</p>
          </div>

          {/* Motivation message */}
          {editedPlan.motivation_message && (
            <div className="bg-indigo-950/40 border border-indigo-800/40 rounded-xl px-5 py-4 mb-5">
              <p className="text-indigo-200 text-sm leading-relaxed">💬 {editedPlan.motivation_message}</p>
            </div>
          )}

          {/* First step */}
          {editedPlan.first_step && (
            <div className="bg-green-950/40 border border-green-800/40 rounded-xl px-5 py-3 mb-5 flex items-start gap-3">
              <Zap size={16} className="text-green-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-green-400 text-xs font-semibold uppercase tracking-wider mb-0.5">Erster Schritt — heute</div>
                <p className="text-green-200 text-sm">{editedPlan.first_step}</p>
              </div>
            </div>
          )}

          {/* Key Results */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <Target size={14} className="text-blue-400" />
              <span className="text-blue-400 text-xs font-semibold uppercase tracking-wider">Key Results ({editedPlan.key_results.length})</span>
            </div>
            <div className="space-y-3">
              {editedPlan.key_results.map((kr, i) => (
                <div key={i} className="flex items-start gap-3 py-2 border-b border-zinc-800 last:border-0">
                  <div className="w-6 h-6 rounded-full bg-blue-900/50 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-blue-400 text-xs font-bold">{i + 1}</span>
                  </div>
                  <div className="flex-1">
                    <input
                      value={kr.title}
                      onChange={(e) => {
                        const krs = [...editedPlan.key_results];
                        krs[i] = { ...krs[i], title: e.target.value };
                        setEditedPlan({ ...editedPlan, key_results: krs });
                      }}
                      className="w-full bg-transparent text-white text-sm font-medium focus:outline-none focus:bg-zinc-800 focus:px-2 focus:rounded transition-all"
                    />
                    <div className="flex items-center gap-3 mt-1">
                      {kr.target_value != null && (
                        <span className="text-zinc-500 text-xs">Ziel: {kr.target_value} {kr.unit || ""}</span>
                      )}
                      {kr.why && <span className="text-zinc-600 text-xs italic">{kr.why}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Tasks */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <Check size={14} className="text-emerald-400" />
              <span className="text-emerald-400 text-xs font-semibold uppercase tracking-wider">Konkrete Tasks ({editedPlan.tasks.length})</span>
            </div>
            <div className="space-y-2">
              {editedPlan.tasks.map((task, i) => (
                <div key={i} className="flex items-center gap-3 py-1.5 border-b border-zinc-800/50 last:border-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  <input
                    value={task.title}
                    onChange={(e) => {
                      const tasks = [...editedPlan.tasks];
                      tasks[i] = { ...tasks[i], title: e.target.value };
                      setEditedPlan({ ...editedPlan, tasks });
                    }}
                    className="flex-1 bg-transparent text-zinc-300 text-sm focus:outline-none focus:bg-zinc-800 focus:px-2 focus:rounded transition-all"
                  />
                  <span className="text-zinc-600 text-xs shrink-0">in {task.due_days}d</span>
                </div>
              ))}
            </div>
          </div>

          {/* Weekly Schedule */}
          {editedPlan.weekly_schedule && editedPlan.weekly_schedule.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
              <div className="flex items-center gap-2 mb-4">
                <Calendar size={14} className="text-orange-400" />
                <span className="text-orange-400 text-xs font-semibold uppercase tracking-wider">Wochenplan</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {editedPlan.weekly_schedule.map((item, i) => (
                  <div key={i} className="flex items-center gap-3 bg-zinc-800 rounded-lg px-3 py-2">
                    <span className="text-zinc-400 text-xs font-medium w-16 shrink-0">{item.day}</span>
                    <span className="text-zinc-300 text-sm flex-1 truncate">{item.activity}</span>
                    <span className="text-zinc-600 text-xs shrink-0">{item.duration_min}min</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Synergies */}
          {editedPlan.synergies && editedPlan.synergies.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
              <div className="flex items-center gap-2 mb-3">
                <Link2 size={14} className="text-purple-400" />
                <span className="text-purple-400 text-xs font-semibold uppercase tracking-wider">Synergien mit deinen Zielen</span>
              </div>
              <div className="space-y-2">
                {editedPlan.synergies.map((s, i) => (
                  <div key={i} className="flex items-start gap-3 bg-purple-950/30 border border-purple-800/20 rounded-lg px-3 py-2">
                    <span className="text-purple-400 shrink-0 mt-0.5">⚡</span>
                    <div>
                      <div className="text-purple-300 text-xs font-medium">{s.existing_goal}</div>
                      <div className="text-zinc-500 text-xs mt-0.5">{s.connection}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Execute */}
          <div className="flex gap-3 mt-6 sticky bottom-4">
            <button onClick={() => setStep(2)} className="flex items-center gap-2 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
              <ArrowLeft size={16} />
            </button>
            <button
              onClick={handleExecute}
              disabled={executing}
              className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white rounded-xl font-bold text-base transition-all disabled:opacity-40 shadow-lg shadow-green-900/30"
            >
              {executing ? (
                "Aktiviere alles..."
              ) : (
                <><Zap size={18} /> Alles aktivieren 🚀</>
              )}
            </button>
          </div>
          <p className="text-zinc-600 text-xs text-center mt-3">Alle Felder sind editierbar — klick einfach drauf</p>
        </div>
      )}
    </div>
  );
}
```

### File: `dashboard/src/lib/api.ts`
Add to the `api` object:
```typescript
goalClarify: (goal: string) => apiPost<{ questions: Array<{ id: string; label: string; placeholder: string }> }>("/api/goals/clarify", { goal }),
goalGenerate: (body: { goal: string; why?: string; timeframe?: string; current_state?: string }) =>
  apiPost<{ draft_id: number; plan: unknown }>("/api/goals/generate", body),
```

---

## PART 4 — Sidebar Navigation Update

### File: `dashboard/src/components/Sidebar.tsx`
Find the navigation items array and add "Neues Ziel" near the top, after Dashboard:
```tsx
{ href: "/goals/new", icon: "✨", label: "Neues Ziel" },
```
(Use the same pattern as other nav items in that file)

---

## PART 5 — Deploy

1. `python3 -m py_compile bot/api/routes.py` — must pass
2. `cd dashboard && npm run build` — must compile cleanly
3. `scp` changed files to server:
   ```bash
   scp bot/api/routes.py root@95.111.252.176:/opt/personal-os/bot/api/routes.py
   scp dashboard/src/app/goals/new/page.tsx root@95.111.252.176:/opt/personal-os/dashboard/src/app/goals/new/page.tsx
   scp dashboard/src/components/Sidebar.tsx root@95.111.252.176:/opt/personal-os/dashboard/src/components/Sidebar.tsx
   scp dashboard/src/app/layout.tsx root@95.111.252.176:/opt/personal-os/dashboard/src/app/layout.tsx
   scp dashboard/public/favicon.svg root@95.111.252.176:/opt/personal-os/dashboard/public/favicon.svg
   scp dashboard/src/lib/api.ts root@95.111.252.176:/opt/personal-os/dashboard/src/lib/api.ts
   ```
4. SSH: `systemctl restart personal-os && cd dashboard && npm run build && systemctl restart personal-os-dashboard`
5. Commit: `git add -A && git commit -m "feat(goals): goal coach wizard with GPT OKR generation + favicon" && git push`

## Completion signal
When done: `openclaw system event --text "Done: Goal coach wizard live — GPT-powered OKR generation, 3-step wizard, favicon" --mode now`
