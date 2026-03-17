"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { ArrowRight, ArrowLeft, Sparkles, Check, Zap, Target, Calendar, Link2 } from "lucide-react";

const API_URL = typeof window !== "undefined" ? window.location.origin : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("api_token") || "";
}

async function apiCall(path: string, body: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.detail || j.message || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

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

const GOAL_EXAMPLES = [
  { emoji: "💪", text: "Fitness & Sport" },
  { emoji: "📈", text: "Business & Karriere" },
  { emoji: "🧠", text: "Persönlichkeit" },
  { emoji: "💰", text: "Finanzen" },
  { emoji: "📚", text: "Lernen & Skills" },
  { emoji: "❤️", text: "Beziehungen" },
];

export default function NewGoalPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);

  const [goalText, setGoalText] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loadingQ, setLoadingQ] = useState(false);

  const [plan, setPlan] = useState<Plan | null>(null);
  const [editedPlan, setEditedPlan] = useState<Plan | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const handleGoalSubmit = async () => {
    if (!goalText.trim()) return;
    setLoadingQ(true);
    setError("");
    try {
      const data = await apiCall("/api/goals/clarify", { goal: goalText });
      setQuestions(data.questions ?? [
        { id: "why", label: "Warum ist dir das wichtig?", placeholder: "Deine tiefe Motivation..." },
        { id: "timeframe", label: "Bis wann willst du es erreichen?", placeholder: "z.B. in 3 Monaten..." },
        { id: "current_state", label: "Wo stehst du gerade?", placeholder: "Aktueller Stand..." },
      ]);
    } catch {
      setQuestions([
        { id: "why", label: "Warum ist dir das wichtig?", placeholder: "Deine tiefe Motivation..." },
        { id: "timeframe", label: "Bis wann willst du es erreichen?", placeholder: "z.B. in 3 Monaten..." },
        { id: "current_state", label: "Wo stehst du gerade?", placeholder: "Aktueller Stand..." },
      ]);
    } finally {
      setLoadingQ(false);
      setStep(2);
    }
  };

  const handleGeneratePlan = async () => {
    setLoadingPlan(true);
    setError("");
    try {
      const data = await apiCall("/api/goals/generate", {
        goal: goalText,
        why: answers.why || undefined,
        timeframe: answers.timeframe || undefined,
        current_state: answers.current_state || undefined,
      });
      setPlan(data.plan);
      setEditedPlan(JSON.parse(JSON.stringify(data.plan)));
      setDraftId(data.draft_id);
      setStep(3);
    } catch (e: unknown) {
      setError("Fehler: " + (e instanceof Error ? e.message : "Unbekannt"));
    } finally {
      setLoadingPlan(false);
    }
  };

  const handleExecute = async () => {
    if (!draftId) return;
    setExecuting(true);
    setError("");
    try {
      await apiCall(`/api/objectives/proposal-drafts/${draftId}/review`, { action: "accept" });
      await apiCall(`/api/objectives/proposal-drafts/${draftId}/execute`, {});
      setDone(true);
    } catch {
      setError("Fehler beim Aktivieren. Bitte versuche es erneut.");
    } finally {
      setExecuting(false);
    }
  };

  const updateKR = (i: number, field: keyof KR, value: string) => {
    if (!editedPlan) return;
    const krs = [...editedPlan.key_results];
    krs[i] = { ...krs[i], [field]: value };
    setEditedPlan({ ...editedPlan, key_results: krs });
  };

  const updateTask = (i: number, value: string) => {
    if (!editedPlan) return;
    const tasks = [...editedPlan.tasks];
    tasks[i] = { ...tasks[i], title: value };
    setEditedPlan({ ...editedPlan, tasks });
  };

  if (done) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="text-7xl mb-6 animate-bounce">🚀</div>
        <h1 className="text-2xl font-bold text-white mb-3">Ziel aktiviert!</h1>
        <p className="text-zinc-400 mb-2 max-w-sm">Dein Plan ist live. Tasks wurden erstellt, Erinnerungen gesetzt.</p>
        {editedPlan && (
          <p className="text-zinc-500 text-sm mb-8 max-w-sm italic">"{editedPlan.first_step}"</p>
        )}
        <div className="flex gap-3">
          <button onClick={() => router.push("/objectives")}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors">
            Ziele ansehen →
          </button>
          <button onClick={() => { setStep(1); setGoalText(""); setPlan(null); setEditedPlan(null); setDone(false); setAnswers({}); }}
            className="px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
            Weiteres Ziel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Progress bar */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          {STEP_LABELS.map((label, i) => (
            <React.Fragment key={i}>
              <div className="flex items-center gap-1.5">
                <div className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all",
                  step > i + 1 ? "bg-green-600 text-white" :
                  step === i + 1 ? "bg-blue-600 text-white ring-4 ring-blue-600/20" :
                  "bg-zinc-800 text-zinc-500"
                )}>
                  {step > i + 1 ? <Check size={10} /> : i + 1}
                </div>
                <span className={cn("text-xs hidden sm:block transition-colors",
                  step === i + 1 ? "text-white font-medium" : "text-zinc-600")}>
                  {label}
                </span>
              </div>
              {i < 2 && <div className={cn("flex-1 h-px transition-colors", step > i + 1 ? "bg-green-700" : "bg-zinc-700")} />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-950/50 border border-red-800/40 rounded-xl px-4 py-3 mb-4 text-red-400 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* ── Step 1: Goal Input ── */}
      {step === 1 && (
        <div>
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">🎯</div>
            <h1 className="text-2xl font-bold text-white mb-2">Was willst du erreichen?</h1>
            <p className="text-zinc-400 text-sm">Beschreib dein Ziel in eigenen Worten.<br />Ich mach daraus einen konkreten, messbaren Plan.</p>
          </div>

          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 mb-5">
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
              <span className="text-zinc-600 text-xs hidden sm:block">⌘↵ zum Weiter</span>
              <button onClick={handleGoalSubmit} disabled={!goalText.trim() || loadingQ}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors disabled:opacity-40 ml-auto">
                {loadingQ ? <><span className="animate-spin inline-block">⟳</span> Analysiere...</> : <>Weiter <ArrowRight size={16} /></>}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {GOAL_EXAMPLES.map((item) => (
              <button key={item.text} onClick={() => setGoalText((v) => v || `${item.emoji} `)}
                className="flex items-center gap-2 px-3 py-2.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-xl text-zinc-400 hover:text-white text-sm transition-colors text-left">
                <span>{item.emoji}</span><span>{item.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Step 2: Clarifying Questions ── */}
      {step === 2 && (
        <div>
          <div className="text-center mb-6">
            <div className="text-4xl mb-3">🤔</div>
            <h1 className="text-2xl font-bold text-white mb-2">Kurz präzisieren</h1>
            <p className="text-zinc-400 text-sm">3 kurze Fragen → danach generiere ich deinen personalisierten Plan.</p>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-3 mb-5 flex items-start gap-2">
            <span className="text-zinc-500 shrink-0 text-lg">💬</span>
            <p className="text-zinc-400 text-sm italic">"{goalText}"</p>
          </div>

          <div className="space-y-4 mb-6">
            {questions.map((q) => (
              <div key={q.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <label className="block text-white font-medium text-sm mb-3">{q.label}</label>
                <textarea value={answers[q.id] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                  placeholder={q.placeholder} rows={2}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 resize-none" />
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep(1)} className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
              <ArrowLeft size={16} />
            </button>
            <button onClick={handleGeneratePlan} disabled={loadingPlan}
              className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold transition-all disabled:opacity-40 shadow-lg shadow-blue-900/30">
              {loadingPlan
                ? <><span className="text-lg animate-pulse">✨</span> KI generiert deinen Plan...</>
                : <><Sparkles size={16} /> Plan generieren</>}
            </button>
          </div>
          <p className="text-zinc-600 text-xs text-center mt-3">Fragen sind optional — du kannst sie auch leer lassen</p>
        </div>
      )}

      {/* ── Step 3: Plan Review & Execute ── */}
      {step === 3 && editedPlan && (
        <div className="pb-24">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="text-4xl mb-2">{editedPlan.objective.emoji || "🎯"}</div>
            <h1 className="text-xl font-bold text-white mb-1">{editedPlan.objective.title}</h1>
            <p className="text-zinc-400 text-sm max-w-lg mx-auto">{editedPlan.objective.description}</p>
            <div className="flex items-center justify-center gap-2 mt-2 text-xs text-zinc-600">
              <span className="bg-zinc-800 px-2 py-0.5 rounded-full">{editedPlan.objective.category}</span>
              <span>·</span>
              <span>bis {editedPlan.objective.target_date}</span>
            </div>
          </div>

          {/* Motivation */}
          {editedPlan.motivation_message && (
            <div className="bg-indigo-950/40 border border-indigo-800/30 rounded-xl px-5 py-4 mb-4">
              <p className="text-indigo-200 text-sm leading-relaxed">💬 {editedPlan.motivation_message}</p>
            </div>
          )}

          {/* First step */}
          {editedPlan.first_step && (
            <div className="bg-green-950/40 border border-green-800/30 rounded-xl px-5 py-3 mb-4 flex items-start gap-3">
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
              <span className="text-blue-400 text-xs font-semibold uppercase tracking-wider">Key Results</span>
              <span className="text-zinc-600 text-xs ml-auto">{editedPlan.key_results.length} Metriken</span>
            </div>
            <div className="space-y-3">
              {editedPlan.key_results.map((kr, i) => (
                <div key={i} className="flex items-start gap-3 py-2.5 border-b border-zinc-800 last:border-0">
                  <div className="w-5 h-5 rounded-full bg-blue-900/60 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-blue-400 text-xs font-bold">{i + 1}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <input value={kr.title} onChange={(e) => updateKR(i, "title", e.target.value)}
                      className="w-full bg-transparent text-white text-sm font-medium focus:outline-none hover:bg-zinc-800 focus:bg-zinc-800 px-1 -mx-1 rounded transition-colors" />
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      {kr.target_value != null && (
                        <span className="text-zinc-500 text-xs bg-zinc-800 px-1.5 py-0.5 rounded">
                          Ziel: {kr.target_value}{kr.unit ? ` ${kr.unit}` : ""}
                        </span>
                      )}
                      {kr.why && <span className="text-zinc-600 text-xs italic truncate">{kr.why}</span>}
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
              <span className="text-emerald-400 text-xs font-semibold uppercase tracking-wider">Konkrete Tasks</span>
              <span className="text-zinc-600 text-xs ml-auto">{editedPlan.tasks.length} Aktionen</span>
            </div>
            <div className="space-y-1">
              {editedPlan.tasks.map((task, i) => (
                <div key={i} className="flex items-center gap-3 py-1.5 border-b border-zinc-800/40 last:border-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  <input value={task.title} onChange={(e) => updateTask(i, e.target.value)}
                    className="flex-1 bg-transparent text-zinc-300 text-sm focus:outline-none hover:bg-zinc-800 focus:bg-zinc-800 px-1 -mx-1 rounded transition-colors" />
                  <span className="text-zinc-600 text-xs shrink-0 tabular-nums">+{task.due_days}d</span>
                </div>
              ))}
            </div>
          </div>

          {/* Weekly Schedule */}
          {editedPlan.weekly_schedule?.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
              <div className="flex items-center gap-2 mb-4">
                <Calendar size={14} className="text-orange-400" />
                <span className="text-orange-400 text-xs font-semibold uppercase tracking-wider">Wochenplan</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {editedPlan.weekly_schedule.map((item, i) => (
                  <div key={i} className="flex items-center gap-3 bg-zinc-800 rounded-lg px-3 py-2">
                    <span className="text-zinc-400 text-xs font-medium w-14 shrink-0">{item.day}</span>
                    <span className="text-zinc-300 text-sm flex-1 truncate">{item.activity}</span>
                    <span className="text-zinc-600 text-xs shrink-0">{item.duration_min}min</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Synergies */}
          {editedPlan.synergies?.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
              <div className="flex items-center gap-2 mb-3">
                <Link2 size={14} className="text-purple-400" />
                <span className="text-purple-400 text-xs font-semibold uppercase tracking-wider">Synergien mit deinen Zielen</span>
              </div>
              <div className="space-y-2">
                {editedPlan.synergies.map((s, i) => (
                  <div key={i} className="bg-purple-950/30 border border-purple-800/20 rounded-lg px-3 py-2">
                    <div className="text-purple-300 text-xs font-medium">⚡ {s.existing_goal}</div>
                    <div className="text-zinc-500 text-xs mt-0.5">{s.connection}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-zinc-600 text-xs text-center mb-4">💡 Alle Felder sind editierbar — klick einfach drauf</p>

          {/* Sticky Execute */}
          <div className="fixed bottom-0 left-0 right-0 md:relative md:bottom-auto md:left-auto md:right-auto bg-zinc-950/95 md:bg-transparent backdrop-blur-sm md:backdrop-blur-none px-4 py-4 md:p-0 border-t border-zinc-800 md:border-0">
            <div className="flex gap-3 max-w-2xl mx-auto">
              <button onClick={() => setStep(2)}
                className="flex items-center gap-2 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
                <ArrowLeft size={16} />
              </button>
              <button onClick={handleExecute} disabled={executing}
                className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white rounded-xl font-bold text-base transition-all disabled:opacity-40 shadow-xl shadow-green-900/30">
                {executing ? "Aktiviere alles..." : <><Zap size={18} /> Alles aktivieren 🚀</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
