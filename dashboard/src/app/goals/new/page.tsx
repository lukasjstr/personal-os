"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  ArrowRight, ArrowLeft, Sparkles, Check, Zap, Target,
  Calendar, Link2, Plus, Pencil, X,
} from "lucide-react";

const API_URL =
  typeof window !== "undefined"
    ? window.location.origin
    : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

// ─── Types ─────────────────────────────────────────────────────────────────

interface Question {
  id: string;
  label: string;
  placeholder: string;
  hint?: string;
  type: "text" | "number" | "date" | "choice";
  options?: string[];
}

interface KROption {
  id: string;
  title: string;
  metric_type: string;
  target_value: number | null;
  current_value?: number;
  unit: string | null;
  why?: string;
  recommended: boolean;
  difficulty: "easy" | "medium" | "hard";
}

interface ObjectiveDraft {
  title: string;
  description: string;
  category: string;
  target_date: string;
  emoji: string;
}

interface Task { title: string; priority: number; due_days: number; category?: string; }
interface WeekDay { day: string; activity: string; duration_min: number; }
interface Synergy { existing_goal: string; connection: string; }

interface Plan {
  objective: ObjectiveDraft;
  key_results: KROption[];
  tasks: Task[];
  weekly_schedule: WeekDay[];
  synergies: Synergy[];
  motivation_message: string;
  first_step: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────

const STEP_LABELS = ["Dein Ziel", "Fragen", "Key Results", "Dein Plan"];

const GOAL_EXAMPLES = [
  { emoji: "💪", text: "Fitness & Sport" },
  { emoji: "📈", text: "Business & Karriere" },
  { emoji: "🧠", text: "Persönlichkeit" },
  { emoji: "💰", text: "Finanzen" },
  { emoji: "📚", text: "Lernen & Skills" },
  { emoji: "❤️", text: "Beziehungen" },
];

const DIFFICULTY_LABEL: Record<string, string> = { easy: "Leicht", medium: "Mittel", hard: "Schwer" };
const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "bg-green-900/50 text-green-400 border-green-700/50",
  medium: "bg-yellow-900/50 text-yellow-400 border-yellow-700/50",
  hard: "bg-orange-900/50 text-orange-400 border-orange-700/50",
};

// ─── Sub-components ─────────────────────────────────────────────────────────

function ProgressBar({ step }: { step: number }) {
  return (
    <div className="mb-8">
      <div className="flex items-center gap-2">
        {STEP_LABELS.map((label, i) => (
          <React.Fragment key={i}>
            <div className="flex items-center gap-1.5 shrink-0">
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
            {i < 3 && <div className={cn("flex-1 h-px transition-colors", step > i + 1 ? "bg-green-700" : "bg-zinc-700")} />}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function KRCard({
  kr,
  selected,
  onToggle,
  editedKr,
  onEdit,
}: {
  kr: KROption;
  selected: boolean;
  onToggle: () => void;
  editedKr?: Partial<KROption>;
  onEdit: (fields: Partial<KROption>) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [localTitle, setLocalTitle] = useState(editedKr?.title ?? kr.title);
  const [localTarget, setLocalTarget] = useState(String(editedKr?.target_value ?? kr.target_value ?? ""));
  const [localUnit, setLocalUnit] = useState(editedKr?.unit ?? kr.unit ?? "");

  const displayTitle = editedKr?.title ?? kr.title;
  const displayTarget = editedKr?.target_value ?? kr.target_value;
  const displayUnit = editedKr?.unit ?? kr.unit;

  const saveEdit = () => {
    onEdit({
      title: localTitle,
      target_value: localTarget !== "" ? parseFloat(localTarget) : kr.target_value,
      unit: localUnit || kr.unit,
    });
    setEditing(false);
  };

  return (
    <div
      onClick={!editing ? onToggle : undefined}
      className={cn(
        "relative rounded-xl border-2 p-4 transition-all cursor-pointer",
        selected
          ? "border-blue-500 bg-blue-950/20"
          : "border-zinc-700 bg-zinc-900 hover:border-zinc-500"
      )}
    >
      {/* Badges row */}
      <div className="flex items-center gap-1.5 mb-2.5 flex-wrap">
        {kr.recommended && (
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-green-900/60 text-green-400 border border-green-700/50">
            ⭐ Empfohlen
          </span>
        )}
        <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full border", DIFFICULTY_COLOR[kr.difficulty])}>
          {DIFFICULTY_LABEL[kr.difficulty]}
        </span>
        {selected && (
          <span className="ml-auto text-blue-400">
            <Check size={14} />
          </span>
        )}
      </div>

      {/* Content */}
      {editing ? (
        <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
          <input
            value={localTitle}
            onChange={(e) => setLocalTitle(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
            placeholder="Key Result Titel"
          />
          <div className="flex gap-2">
            <input
              value={localTarget}
              onChange={(e) => setLocalTarget(e.target.value)}
              type="number"
              className="w-24 bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
              placeholder="Ziel"
            />
            <input
              value={localUnit}
              onChange={(e) => setLocalUnit(e.target.value)}
              className="flex-1 bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
              placeholder="Einheit"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={saveEdit}
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
            >
              <Check size={12} /> Speichern
            </button>
            <button
              onClick={() => setEditing(false)}
              className="flex items-center gap-1 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs rounded-lg transition-colors"
            >
              <X size={12} /> Abbrechen
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="text-white text-sm font-medium leading-snug mb-1">{displayTitle}</div>
          {displayTarget != null && (
            <div className="text-zinc-400 text-xs">
              Ziel: <span className="text-zinc-200 font-medium">{displayTarget}{displayUnit ? ` ${displayUnit}` : ""}</span>
            </div>
          )}
          {kr.why && <div className="text-zinc-500 text-xs mt-1 italic">{kr.why}</div>}
          {selected && (
            <button
              onClick={(e) => { e.stopPropagation(); setEditing(true); }}
              className="mt-2 flex items-center gap-1 text-xs text-zinc-500 hover:text-blue-400 transition-colors"
            >
              <Pencil size={10} /> Anpassen
            </button>
          )}
        </>
      )}
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function NewGoalPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");

  // Step 1
  const [goalText, setGoalText] = useState("");

  // Step 2
  const [category, setCategory] = useState("personal");
  const [categoryEmoji, setCategoryEmoji] = useState("🎯");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loadingQ, setLoadingQ] = useState(false);

  // Step 3 — KR selection
  const [krOptions, setKrOptions] = useState<KROption[]>([]);
  const [selectedKrIds, setSelectedKrIds] = useState<Set<string>>(new Set());
  const [editedKrs, setEditedKrs] = useState<Record<string, Partial<KROption>>>({});
  const [customKrs, setCustomKrs] = useState<KROption[]>([]);
  const [objectiveDraft, setObjectiveDraft] = useState<ObjectiveDraft | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);
  // refine
  const [showRefine, setShowRefine] = useState(false);
  const [refineFeedback, setRefineFeedback] = useState("");
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineError, setRefineError] = useState("");
  // add custom kr form
  const [showAddKr, setShowAddKr] = useState(false);
  const [newKrTitle, setNewKrTitle] = useState("");
  const [newKrTarget, setNewKrTarget] = useState("");
  const [newKrUnit, setNewKrUnit] = useState("");

  // Step 4 — Plan
  const [plan, setPlan] = useState<Plan | null>(null);
  const [editedPlan, setEditedPlan] = useState<Plan | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [done, setDone] = useState(false);

  // ── Step handlers ─────────────────────────────────────────────────────────

  const handleGoalSubmit = async () => {
    if (!goalText.trim()) return;
    setLoadingQ(true);
    setError("");
    try {
      const data = await apiCall("/api/goals/clarify", { goal: goalText });
      setCategory(data.category || "personal");
      setCategoryEmoji(data.category_emoji || "🎯");
      setQuestions(data.questions ?? [
        { id: "why", label: "Warum ist dir das wichtig?", placeholder: "Deine tiefe Motivation...", hint: "", type: "text" },
        { id: "timeframe", label: "Zeitrahmen?", placeholder: "3 Monate...", hint: "", type: "choice", options: ["4 Wochen", "8 Wochen", "3 Monate", "6 Monate", "1 Jahr"] },
        { id: "current_state", label: "Aktueller Stand?", placeholder: "...", hint: "", type: "text" },
      ]);
    } catch {
      setQuestions([
        { id: "why", label: "Warum ist dir das wichtig?", placeholder: "Deine tiefe Motivation...", hint: "", type: "text" },
        { id: "timeframe", label: "Bis wann?", placeholder: "z.B. in 3 Monaten", hint: "Ein Zeitrahmen macht das Ziel planbar.", type: "choice", options: ["4 Wochen", "8 Wochen", "3 Monate", "6 Monate", "1 Jahr"] },
        { id: "current_state", label: "Wo stehst du gerade?", placeholder: "Aktueller Stand...", hint: "", type: "text" },
      ]);
    } finally {
      setLoadingQ(false);
      setStep(2);
    }
  };

  const handleFetchOptions = async () => {
    setLoadingOptions(true);
    setError("");
    try {
      const data = await apiCall("/api/goals/generate-options", { goal: goalText, category, answers });
      setKrOptions(data.kr_options ?? []);
      setObjectiveDraft(data.objective_draft ?? null);
      // Pre-select recommended KRs
      const rec = new Set<string>((data.kr_options ?? []).filter((k: KROption) => k.recommended).map((k: KROption) => k.id));
      setSelectedKrIds(rec);
      setStep(3);
    } catch (e: unknown) {
      setError("Fehler: " + (e instanceof Error ? e.message : "Unbekannt"));
    } finally {
      setLoadingOptions(false);
    }
  };

  const handleRefine = async () => {
    if (!refineFeedback.trim()) return;
    setRefineLoading(true);
    setRefineError("");
    try {
      const data = await apiCall("/api/goals/refine-options", {
        goal: goalText,
        category,
        answers,
        current_kr_options: krOptions,
        feedback: refineFeedback,
      });
      setKrOptions(data.kr_options ?? []);
      const rec = new Set<string>((data.kr_options ?? []).filter((k: KROption) => k.recommended).map((k: KROption) => k.id));
      setSelectedKrIds(rec);
      setRefineFeedback("");
      setShowRefine(false);
    } catch (e: unknown) {
      setRefineError("Fehler: " + (e instanceof Error ? e.message : "Unbekannt"));
    } finally {
      setRefineLoading(false);
    }
  };

  const handleAddCustomKr = () => {
    if (!newKrTitle.trim()) return;
    const custom: KROption = {
      id: `custom_${Date.now()}`,
      title: newKrTitle.trim(),
      metric_type: "number",
      target_value: newKrTarget !== "" ? parseFloat(newKrTarget) : null,
      current_value: 0,
      unit: newKrUnit.trim() || null,
      why: "Eigenes Key Result",
      recommended: false,
      difficulty: "medium",
    };
    setCustomKrs((prev) => [...prev, custom]);
    setSelectedKrIds((prev) => new Set([...prev, custom.id]));
    setNewKrTitle(""); setNewKrTarget(""); setNewKrUnit("");
    setShowAddKr(false);
  };

  const handleGeneratePlan = async () => {
    setLoadingPlan(true);
    setError("");
    try {
      // Build final KR list: selected from krOptions + all customKrs
      const selected = [...krOptions, ...customKrs].filter((kr) => selectedKrIds.has(kr.id));
      const finalKrs = selected.map((kr) => ({ ...kr, ...(editedKrs[kr.id] || {}) }));

      const data = await apiCall("/api/goals/generate", {
        goal: goalText,
        category,
        answers,
        selected_krs: finalKrs,
      });
      setPlan(data.plan);
      setEditedPlan(JSON.parse(JSON.stringify(data.plan)));
      setDraftId(data.draft_id);
      setStep(4);
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

  const updateTask = (i: number, value: string) => {
    if (!editedPlan) return;
    const tasks = [...editedPlan.tasks];
    tasks[i] = { ...tasks[i], title: value };
    setEditedPlan({ ...editedPlan, tasks });
  };

  const selectedCount = selectedKrIds.size;

  // ── Done screen ───────────────────────────────────────────────────────────

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
          <button onClick={() => {
            setStep(1); setGoalText(""); setPlan(null); setEditedPlan(null);
            setDone(false); setAnswers({}); setKrOptions([]); setSelectedKrIds(new Set());
            setCustomKrs([]); setEditedKrs({});
          }}
            className="px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
            Weiteres Ziel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <ProgressBar step={step} />

      {error && (
        <div className="bg-red-950/50 border border-red-800/40 rounded-xl px-4 py-3 mb-4 text-red-400 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* ── Step 1: Ziel eingeben ─────────────────────────────────────────── */}
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
                {loadingQ
                  ? <><span className="animate-spin inline-block">⟳</span> Analysiere...</>
                  : <>Weiter <ArrowRight size={16} /></>}
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

      {/* ── Step 2: Fragen ───────────────────────────────────────────────── */}
      {step === 2 && (
        <div>
          <div className="text-center mb-6">
            <div className="text-4xl mb-3">{categoryEmoji}</div>
            <h1 className="text-2xl font-bold text-white mb-2">Kurz präzisieren</h1>
            <p className="text-zinc-400 text-sm">
              {questions.length} Fragen → dann generiere ich deine Key Result Optionen.
            </p>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-3 mb-5 flex items-start gap-2">
            <span className="text-zinc-500 shrink-0 text-lg">💬</span>
            <p className="text-zinc-400 text-sm italic">"{goalText}"</p>
          </div>

          <div className="space-y-4 mb-6">
            {questions.map((q) => (
              <div key={q.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <label className="block text-white font-medium text-sm mb-2">{q.label}</label>
                {q.hint && <p className="text-zinc-500 text-xs italic mb-3">{q.hint}</p>}

                {q.type === "choice" && q.options ? (
                  <div className="flex flex-wrap gap-2">
                    {q.options.map((opt) => (
                      <button key={opt}
                        onClick={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                        className={cn(
                          "px-3 py-1.5 rounded-full text-sm border transition-colors",
                          answers[q.id] === opt
                            ? "bg-blue-600 border-blue-500 text-white"
                            : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-500"
                        )}>
                        {opt}
                      </button>
                    ))}
                  </div>
                ) : (
                  <textarea
                    value={answers[q.id] ?? ""}
                    onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                    placeholder={q.placeholder}
                    rows={2}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 resize-none"
                  />
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep(1)}
              className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
              <ArrowLeft size={16} />
            </button>
            <button onClick={handleFetchOptions} disabled={loadingOptions}
              className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold transition-all disabled:opacity-40 shadow-lg shadow-blue-900/30">
              {loadingOptions
                ? <><Sparkles size={16} className="animate-pulse" /> Generiere Key Result Optionen...</>
                : <><Sparkles size={16} /> Key Results generieren</>}
            </button>
          </div>
          <p className="text-zinc-600 text-xs text-center mt-3">Fragen sind optional — du kannst sie auch leer lassen</p>
        </div>
      )}

      {/* ── Step 3: KR-Auswahl ──────────────────────────────────────────── */}
      {step === 3 && (
        <div className="pb-4">
          <div className="text-center mb-5">
            <div className="text-4xl mb-2">🎯</div>
            <h1 className="text-xl font-bold text-white mb-1">Wähle deine Key Results</h1>
            <p className="text-zinc-400 text-sm">Empfohlene sind bereits ausgewählt. Wähle 2–4 die zu dir passen.</p>
          </div>

          {/* Objective preview */}
          {objectiveDraft && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-3 mb-5 flex items-center gap-3">
              <span className="text-2xl">{objectiveDraft.emoji}</span>
              <div className="flex-1 min-w-0">
                <div className="text-white font-semibold text-sm truncate">{objectiveDraft.title}</div>
                <div className="text-zinc-500 text-xs">{objectiveDraft.target_date} · {objectiveDraft.category}</div>
              </div>
            </div>
          )}

          {/* KR grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {krOptions.map((kr) => (
              <KRCard
                key={kr.id}
                kr={kr}
                selected={selectedKrIds.has(kr.id)}
                onToggle={() => setSelectedKrIds((prev) => {
                  const next = new Set(prev);
                  next.has(kr.id) ? next.delete(kr.id) : next.add(kr.id);
                  return next;
                })}
                editedKr={editedKrs[kr.id]}
                onEdit={(fields) => setEditedKrs((prev) => ({ ...prev, [kr.id]: { ...(prev[kr.id] || {}), ...fields } }))}
              />
            ))}

            {/* Custom KRs */}
            {customKrs.map((kr) => (
              <div key={kr.id} className="relative rounded-xl border-2 border-blue-500 bg-blue-950/20 p-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                    Eigenes KR
                  </span>
                  <button
                    onClick={() => {
                      setCustomKrs((prev) => prev.filter((c) => c.id !== kr.id));
                      setSelectedKrIds((prev) => { const n = new Set(prev); n.delete(kr.id); return n; });
                    }}
                    className="text-zinc-500 hover:text-red-400 transition-colors"
                  >
                    <X size={12} />
                  </button>
                </div>
                <div className="text-white text-sm font-medium">{kr.title}</div>
                {kr.target_value != null && (
                  <div className="text-zinc-400 text-xs mt-0.5">
                    Ziel: <span className="text-zinc-200">{kr.target_value}{kr.unit ? ` ${kr.unit}` : ""}</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Add custom KR */}
          {showAddKr ? (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 mb-4 space-y-3">
              <div className="text-white text-sm font-medium">Eigenes Key Result</div>
              <input
                value={newKrTitle}
                onChange={(e) => setNewKrTitle(e.target.value)}
                placeholder="Was willst du messen?"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                autoFocus
              />
              <div className="flex gap-2">
                <input
                  value={newKrTarget}
                  onChange={(e) => setNewKrTarget(e.target.value)}
                  type="number"
                  placeholder="Zielwert"
                  className="w-28 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                />
                <input
                  value={newKrUnit}
                  onChange={(e) => setNewKrUnit(e.target.value)}
                  placeholder="Einheit (z.B. kg)"
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="flex gap-2">
                <button onClick={handleAddCustomKr} disabled={!newKrTitle.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm rounded-lg transition-colors">
                  <Plus size={14} /> Hinzufügen
                </button>
                <button onClick={() => setShowAddKr(false)}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded-lg transition-colors">
                  Abbrechen
                </button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowAddKr(true)}
              className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed border-zinc-700 rounded-xl text-zinc-500 hover:text-white hover:border-zinc-500 transition-colors text-sm mb-4">
              <Plus size={16} /> Eigenes Key Result hinzufügen
            </button>
          )}

          {/* Refine section */}
          <div className="mb-5">
            <button onClick={() => setShowRefine((v) => !v)}
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1.5">
              🔄 {showRefine ? "Schließen" : "KI-Vorschläge anpassen"}
            </button>
            {showRefine && (
              <div className="mt-3 space-y-2">
                <textarea
                  value={refineFeedback}
                  onChange={(e) => setRefineFeedback(e.target.value)}
                  placeholder="Was soll anders sein? z.B. 'mehr finanzielle KRs', 'einfachere Zielwerte', 'fokus auf Qualität statt Quantität'..."
                  rows={3}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 resize-none"
                />
                {refineError && <p className="text-red-400 text-xs">{refineError}</p>}
                <button onClick={handleRefine} disabled={!refineFeedback.trim() || refineLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 text-white text-sm rounded-xl transition-colors">
                  {refineLoading
                    ? <><span className="animate-spin">⟳</span> Neu generieren...</>
                    : <><Sparkles size={14} /> Neu generieren</>}
                </button>
              </div>
            )}
          </div>

          {/* Navigation */}
          <div className="flex gap-3">
            <button onClick={() => setStep(2)}
              className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl transition-colors">
              <ArrowLeft size={16} />
            </button>
            <button
              onClick={handleGeneratePlan}
              disabled={selectedCount === 0 || loadingPlan}
              className="flex-1 flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold transition-all disabled:opacity-40 shadow-lg shadow-blue-900/30"
            >
              {loadingPlan
                ? <><Sparkles size={16} className="animate-pulse" /> Erstelle vollständigen Plan...</>
                : <><Zap size={16} /> Plan generieren mit {selectedCount} Key Result{selectedCount !== 1 ? "s" : ""} →</>}
            </button>
          </div>
          {selectedCount === 0 && (
            <p className="text-zinc-600 text-xs text-center mt-2">Wähle mindestens 1 Key Result aus</p>
          )}
        </div>
      )}

      {/* ── Step 4: Plan Review & Execute ─────────────────────────────── */}
      {step === 4 && editedPlan && (
        <div className="pb-24">
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

          {editedPlan.motivation_message && (
            <div className="bg-indigo-950/40 border border-indigo-800/30 rounded-xl px-5 py-4 mb-4">
              <p className="text-indigo-200 text-sm leading-relaxed">💬 {editedPlan.motivation_message}</p>
            </div>
          )}

          {editedPlan.first_step && (
            <div className="bg-green-950/40 border border-green-800/30 rounded-xl px-5 py-3 mb-4 flex items-start gap-3">
              <Zap size={16} className="text-green-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-green-400 text-xs font-semibold uppercase tracking-wider mb-0.5">Erster Schritt — heute</div>
                <p className="text-green-200 text-sm">{editedPlan.first_step}</p>
              </div>
            </div>
          )}

          {/* Key Results — read-only (already chosen in step 3) */}
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
                    <div className="text-white text-sm font-medium">{kr.title}</div>
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

          {/* Tasks — editable */}
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

          <p className="text-zinc-600 text-xs text-center mb-4">💡 Tasks sind editierbar — klick einfach drauf</p>

          {/* Sticky Execute */}
          <div className="fixed bottom-0 left-0 right-0 md:relative md:bottom-auto md:left-auto md:right-auto bg-zinc-950/95 md:bg-transparent backdrop-blur-sm md:backdrop-blur-none px-4 py-4 md:p-0 border-t border-zinc-800 md:border-0">
            <div className="flex gap-3 max-w-2xl mx-auto">
              <button onClick={() => setStep(3)}
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
