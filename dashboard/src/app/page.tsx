"use client";

import React, { useState } from "react";
import Link from "next/link";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import XPBar from "@/components/XPBar";
import MissionBoard from "@/components/MissionBoard";
import WeekHeatmap from "@/components/WeekHeatmap";
import CircularProgress from "@/components/CircularProgress";
import AutopilotIntelligenceCards from "@/components/AutopilotIntelligenceCards";
import PatternsCard from "@/components/PatternsCard";
import CorrelationCard from "@/components/CorrelationCard";
import ConfidenceCard from "@/components/ConfidenceCard";
import DailyPlanCard from "@/components/DailyPlanCard";
import {
  useDashboard,
  useTasks,
  useRoutines,
  useLogs,
  useObjectives,
  useWeeklySummary,
  useFitnessSummary,
  useGamificationStats,
  useTodaySuggestions,
  useAutopilotSuggestions,
  useDailyContext,
  useStreakRisks,
} from "@/hooks/useApi";
import { api } from "@/lib/api";
import { useSWRConfig } from "swr";
import { getMoodEmoji, formatTimeAgo, LOG_TYPE_EMOJI, CATEGORY_EMOJI, CATEGORY_COLORS, cn } from "@/lib/utils";
import type { Log, Objective } from "@/lib/api";

// ─── Constants ────────────────────────────────────────────────────────────────

const LOG_TYPE_COLOR: Record<string, string> = {
  workout: "text-green-400",
  water: "text-blue-400",
  mood: "text-yellow-400",
  food: "text-orange-400",
  gratitude: "text-pink-400",
  progress: "text-purple-400",
  note: "text-zinc-400",
  general: "text-zinc-400",
};

const CATEGORY_LABEL_DE: Record<string, string> = {
  health: "Gesundheit",
  fitness: "Fitness",
  business: "Business",
  personal: "Persönlich",
  finance: "Finanzen",
  learning: "Lernen",
  relationships: "Beziehungen",
  default: "Sonstiges",
};

const FOCUS_AREAS = [
  { value: "health", label: "Gesundheit" },
  { value: "fitness", label: "Fitness" },
  { value: "business", label: "Business" },
  { value: "personal", label: "Persönlich" },
  { value: "finance", label: "Finanzen" },
  { value: "learning", label: "Lernen" },
  { value: "relationships", label: "Beziehungen" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatActivityLog(log: Log): string {
  const d = log.data;
  switch (log.log_type) {
    case "workout": {
      const ex = String(d.exercise ?? "?");
      if (d.duration_min != null) return `${ex} · ${d.duration_min} min`;
      if (d.weight != null) return `${ex} · ${d.weight}kg × ${d.reps} × ${d.sets}`;
      return ex;
    }
    case "water": return `${d.amount ?? "?"}L Wasser`;
    case "mood": return `Mood ${d.score}/10`;
    case "food": return String(d.description ?? d.meal ?? d.food ?? "?");
    case "gratitude": return String(d.note ?? "?");
    default: return String(d.text ?? d.content ?? log.raw_input ?? log.log_type);
  }
}

// ─── Daily Intelligence Strip ─────────────────────────────────────────────────

function DailyIntelligenceStrip() {
  const { mutate } = useSWRConfig();
  const { data: context, isLoading } = useDailyContext();

  // Local state for the quick-context form
  const [energy, setEnergy] = useState<number | null>(null);
  const [hours, setHours] = useState<number | null>(null);
  const [focusArea, setFocusArea] = useState("");
  const [generating, setGenerating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const plan = context?.daily_plan;
  const hasPlan = !!plan && plan.top_tasks.length > 0;
  const hasContext = !!context?.energy;

  async function handleGenerate() {
    if (energy === null || hours === null || !focusArea) return;
    setGenerating(true);
    try {
      await api.saveDailyContext({ energy, hours_available: hours, focus_area: focusArea });
      await api.generateDailyPlan();
      await mutate("daily-context");
      setShowForm(false);
    } catch {
      // silently fail
    } finally {
      setGenerating(false);
    }
  }

  async function handleRegenerateOnly() {
    setGenerating(true);
    try {
      await api.generateDailyPlan();
      await mutate("daily-context");
    } catch {
      // silently fail
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="bg-gradient-to-r from-zinc-900 to-zinc-800 border border-zinc-700 rounded-xl p-5 mb-5">
      {isLoading ? (
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-zinc-400 text-sm">Tagesplanung lädt…</span>
        </div>
      ) : hasPlan ? (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold flex items-center gap-2 text-sm">
              <span>🎯</span> Dein Fokus heute
            </h2>
            <button
              onClick={handleRegenerateOnly}
              disabled={generating}
              className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors disabled:opacity-50"
            >
              {generating ? "…" : "↺ Neu"}
            </button>
          </div>
          <DailyPlanCard context={context} onRegenerate={() => mutate("daily-context")} />
        </div>
      ) : hasContext && !hasPlan ? (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold flex items-center gap-2 text-sm">
              <span>🎯</span> Tagesplanung
            </h2>
          </div>
          <p className="text-zinc-400 text-sm mb-3">
            Kontext gespeichert. Generiere jetzt deinen personalisierten Tagesplan.
          </p>
          <button
            onClick={handleRegenerateOnly}
            disabled={generating}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
          >
            {generating ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Generiert…
              </>
            ) : (
              "✨ Tagesplan generieren"
            )}
          </button>
        </div>
      ) : showForm ? (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold flex items-center gap-2 text-sm">
              <span>🌅</span> Wie startest du heute?
            </h2>
            <button
              onClick={() => setShowForm(false)}
              className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors"
            >
              ✕
            </button>
          </div>

          {/* Energy selector */}
          <div className="mb-4">
            <div className="text-zinc-400 text-xs font-medium mb-2">Energie</div>
            <div className="flex gap-2">
              {[
                { val: 3, label: "Niedrig", icon: "😴" },
                { val: 6, label: "Mittel", icon: "⚙️" },
                { val: 9, label: "Hoch", icon: "⚡" },
              ].map((opt) => (
                <button
                  key={opt.val}
                  onClick={() => setEnergy(opt.val)}
                  className={cn(
                    "flex-1 flex flex-col items-center gap-1 py-2 rounded-lg border text-xs font-medium transition-colors",
                    energy === opt.val
                      ? "bg-blue-600/20 border-blue-500 text-blue-300"
                      : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
                  )}
                >
                  <span className="text-lg">{opt.icon}</span>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Hours selector */}
          <div className="mb-4">
            <div className="text-zinc-400 text-xs font-medium mb-2">Verfügbare Zeit</div>
            <div className="flex gap-2">
              {[1, 2, 4, 6].map((h) => (
                <button
                  key={h}
                  onClick={() => setHours(h)}
                  className={cn(
                    "flex-1 py-2 rounded-lg border text-xs font-medium transition-colors",
                    hours === h
                      ? "bg-blue-600/20 border-blue-500 text-blue-300"
                      : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
                  )}
                >
                  {h === 6 ? "6h+" : `${h}h`}
                </button>
              ))}
            </div>
          </div>

          {/* Focus area */}
          <div className="mb-4">
            <div className="text-zinc-400 text-xs font-medium mb-2">Fokus-Bereich</div>
            <select
              value={focusArea}
              onChange={(e) => setFocusArea(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 text-zinc-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
            >
              <option value="">Bereich wählen…</option>
              {FOCUS_AREAS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating || energy === null || hours === null || !focusArea}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-medium py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {generating ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Generiert…
              </>
            ) : (
              "✨ Tagesplanung generieren"
            )}
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-white font-semibold flex items-center gap-2 mb-1 text-sm">
              <span>🌅</span> Tagesplanung starten
            </h2>
            <p className="text-zinc-500 text-xs">
              Sag mir wie du drauf bist — ich plane deinen Tag.
            </p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors whitespace-nowrap ml-4"
          >
            Starten →
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Life Areas Grid ──────────────────────────────────────────────────────────

function groupByCategory(objectives: Objective[]): Record<string, Objective[]> {
  const map: Record<string, Objective[]> = {};
  for (const obj of objectives) {
    const cat = obj.category || "default";
    if (!map[cat]) map[cat] = [];
    map[cat].push(obj);
  }
  return map;
}

function calcAreaProgress(objs: Objective[]): number {
  const allKRs = objs.flatMap((o) => o.key_results);
  if (allKRs.length === 0) return 0;
  return Math.round(allKRs.reduce((s, kr) => s + kr.progress_pct, 0) / allKRs.length);
}

function getMomentumLevel(objs: Objective[]): "high" | "medium" | "low" {
  // A simple heuristic: use average progress pct
  const avg = calcAreaProgress(objs);
  if (avg >= 60) return "high";
  if (avg >= 30) return "medium";
  return "low";
}

const MOMENTUM_DOT: Record<string, string> = {
  high: "bg-emerald-400",
  medium: "bg-yellow-400",
  low: "bg-red-400",
};

const MOMENTUM_LABEL: Record<string, string> = {
  high: "⚡ Momentum stark",
  medium: "⚙️ Momentum mittel",
  low: "💤 Braucht Aufmerksamkeit",
};

function LifeAreasGrid({ objectives }: { objectives: Objective[] }) {
  const active = objectives.filter((o) => o.status === "active");
  const grouped = groupByCategory(active);
  const categories = Object.keys(grouped).sort();

  if (categories.length === 0) return null;

  return (
    <div className="mb-5">
      <h2 className="text-white font-semibold text-sm mb-3 flex items-center justify-between">
        <span>🗺️ Lebensbereiche</span>
        <Link href="/objectives" className="text-blue-400 hover:text-blue-300 text-xs transition-colors">
          Alle Ziele →
        </Link>
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {categories.map((cat) => {
          const objs = grouped[cat];
          const progress = calcAreaProgress(objs);
          const momentum = getMomentumLevel(objs);
          const colors = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.default;
          const emoji = CATEGORY_EMOJI[cat] ?? CATEGORY_EMOJI.default;
          const label = CATEGORY_LABEL_DE[cat] ?? cat;

          return (
            <Link key={cat} href="/objectives" className="block hover:opacity-90 transition-opacity">
              <div
                className={cn(
                  "rounded-xl p-3.5 border",
                  colors.bg,
                  "border-zinc-800"
                )}
              >
                {/* Header */}
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="text-lg">{emoji}</span>
                  <span className="text-white font-semibold text-sm truncate">{label}</span>
                </div>

                {/* Progress bar */}
                <div className="mb-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className={cn("text-xs font-medium", colors.text)}>
                      {progress}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${progress}%`, backgroundColor: colors.hex }}
                    />
                  </div>
                </div>

                {/* Meta */}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 text-xs">
                    {objs.length} {objs.length === 1 ? "Ziel" : "Ziele"}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <div className={cn("w-2 h-2 rounded-full", MOMENTUM_DOT[momentum])} />
                  </div>
                </div>

                {/* Momentum label */}
                <div className="text-zinc-500 text-xs mt-1.5">{MOMENTUM_LABEL[momentum]}</div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ─── Streak Risks ─────────────────────────────────────────────────────────────

function StreakRisksSection() {
  const { data } = useStreakRisks();
  const risks = data?.risks ?? [];
  const filtered = risks.filter((r) => r.days_since >= 3);

  if (filtered.length === 0) return null;

  return (
    <div className="bg-amber-900/20 border border-amber-800/40 rounded-xl p-4 mb-5">
      <h2 className="text-amber-400 font-semibold text-sm mb-3 flex items-center gap-2">
        <span>⚠️</span> Aufmerksamkeit nötig
      </h2>
      <div className="space-y-2.5">
        {filtered.map((risk) => {
          const colors = CATEGORY_COLORS[risk.category] ?? CATEGORY_COLORS.default;
          return (
            <div key={risk.objective_id} className="flex items-start gap-3">
              <div className="shrink-0 mt-0.5">
                <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full", colors.bg, colors.text)}>
                  {risk.days_since}T
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-zinc-200 text-sm font-medium truncate">{risk.title}</div>
                {risk.suggested_action && (
                  <div className="text-amber-400/70 text-xs mt-0.5 line-clamp-1">
                    → {risk.suggested_action}
                  </div>
                )}
                {risk.open_task_count > 0 && (
                  <div className="text-zinc-600 text-xs mt-0.5">
                    {risk.open_task_count} offene Tasks
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Quick Actions ────────────────────────────────────────────────────────────

function QuickActions() {
  return (
    <div className="grid grid-cols-4 gap-2 mb-5">
      {[
        { href: "/brain-dumps", icon: "📝", label: "Brain Dump" },
        { href: "/objectives", icon: "🎯", label: "Neues Ziel" },
        { href: "/tasks", icon: "📋", label: "Tasks" },
        { href: "/objectives/analysis", icon: "📊", label: "Analyse" },
      ].map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="flex flex-col items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-xl py-3 px-2 transition-colors"
        >
          <span className="text-xl">{item.icon}</span>
          <span className="text-zinc-400 text-xs text-center leading-tight">{item.label}</span>
        </Link>
      ))}
    </div>
  );
}

// ─── Evening Check-in ─────────────────────────────────────────────────────────

function EveningCheckinBanner() {
  const { data: checkin } = useStreakRisks(); // we just piggyback the existing load; the banner is always shown for now
  const [dismissed, setDismissed] = useState(false);
  const hour = new Date().getHours();

  // Show after 17:00 or always show for now (as per spec)
  if (dismissed) return null;

  return (
    <div className="bg-indigo-950/30 border border-indigo-800/30 rounded-xl p-4 mb-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-indigo-300 font-semibold text-sm flex items-center gap-2">
            <span>🌙</span> Wie war dein Tag?
          </h2>
          <p className="text-zinc-500 text-xs mt-0.5">
            {hour >= 17 ? "Zeit für deinen Abend-Check-in." : "Check-in (jederzeit verfügbar)"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/reflections"
            className="bg-indigo-700 hover:bg-indigo-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap"
          >
            Check-in starten →
          </Link>
          <button
            onClick={() => setDismissed(true)}
            className="text-zinc-600 hover:text-zinc-400 text-xs transition-colors"
            aria-label="Schließen"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: dash, error: dashError, isLoading: dashLoading } = useDashboard();
  const { data: taskData } = useTasks();
  const { data: routineData } = useRoutines();
  const { data: logsData } = useLogs(undefined, 7);
  const { data: objectivesData } = useObjectives();
  const { data: weeklySummary } = useWeeklySummary();
  const { data: fitnessSummary } = useFitnessSummary();
  const { data: gamification } = useGamificationStats();
  const { data: autopilotSuggestions } = useAutopilotSuggestions();

  if (dashLoading) return <LoadingSpinner />;
  if (dashError) {
    if (dashError.message === "UNAUTHORIZED") {
      return <ErrorState message="Ungültiger API Token. Bitte in den Einstellungen aktualisieren." />;
    }
    return <ErrorState message={dashError.message} />;
  }
  if (!dash) return <LoadingSpinner />;

  const stats = dash?.stats;
  const user = dash?.user;
  const tasks = taskData?.tasks ?? [];
  const routines = routineData?.routines ?? [];
  const allLogs = logsData?.logs ?? [];
  const recentLogs = allLogs.slice(0, 8);

  const objectives = objectivesData?.objectives ?? [];
  const activeObjectives = objectives.filter((o) => o.status === "active");

  // Goal progress — average of all active objectives' key result progress
  let goalProgress = 0;
  if (activeObjectives.length > 0) {
    const allKRs = activeObjectives.flatMap((o) => o.key_results);
    if (allKRs.length > 0) {
      goalProgress = Math.round(
        allKRs.reduce((sum, kr) => sum + kr.progress_pct, 0) / allKRs.length
      );
    }
  }

  // Weekly task stats
  const tasksDoneThisWeek = weeklySummary?.tasks_done_this_week ?? 0;
  const tasksOpenCount = weeklySummary?.tasks_open ?? 0;
  const totalWeeklyTasks = tasksDoneThisWeek + tasksOpenCount;
  const weeklyTasksPct =
    totalWeeklyTasks > 0 ? Math.round((tasksDoneThisWeek / totalWeeklyTasks) * 100) : 0;

  // Fitness shortcut data
  const lastSession = fitnessSummary?.last_sessions?.[0];
  const lastWorkoutLabel = lastSession
    ? `Zuletzt: ${new Date(lastSession.date + "T00:00:00").toLocaleDateString("de-DE", {
        weekday: "short",
        day: "numeric",
        month: "short",
      })}`
    : "Noch kein Training";
  const workoutsThisWeek = stats?.workouts_this_week ?? 0;

  // Other quick values
  const streakDays = stats?.streak_days ?? 0;
  const latestMood = stats?.latest_mood ?? null;
  const waterToday = stats?.water_today_liters ?? 0;
  const routinesDone = stats?.routines_done_today ?? 0;
  const routinesTotal = stats?.routines_total ?? 0;
  const shoppingItems = stats?.shopping_items ?? 0;

  const today = new Date();
  const greeting =
    today.getHours() < 12 ? "Guten Morgen" : today.getHours() < 18 ? "Guten Tag" : "Guten Abend";
  const dayStr = today.toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const streakFlames =
    streakDays >= 30 ? "🔥🔥🔥" : streakDays >= 14 ? "🔥🔥" : "🔥";

  return (
    <div>
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="mb-5">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold text-white">
                {greeting}{user?.first_name ? `, ${user.first_name}` : ""} 👋
              </h1>
              {stats && stats.level != null && (
                <span className="text-xs font-bold bg-gradient-to-br from-yellow-500 to-orange-600 text-white px-2 py-0.5 rounded-full">
                  Lv.{stats.level}
                </span>
              )}
            </div>
            <p className="text-zinc-500 text-sm mt-0.5">{dayStr}</p>
          </div>
          {streakDays > 0 && (
            <div className="bg-orange-950/60 border border-orange-800/40 rounded-xl px-3 py-2 flex items-center gap-2">
              <span className="text-xl">{streakFlames}</span>
              <div>
                <div className="text-orange-400 font-bold text-lg leading-none">{streakDays}</div>
                <div className="text-orange-600 text-xs">Tage</div>
              </div>
            </div>
          )}
        </div>
        {stats && stats.total_xp !== undefined && (
          <XPBar
            level={stats.level}
            levelTitle={stats.level_title}
            totalXp={stats.total_xp}
            xpProgress={stats.xp_progress}
            xpToNext={stats.xp_to_next}
          />
        )}
      </div>

      {/* ── B. Daily Intelligence Strip (hero element) ───────────────────── */}
      <DailyIntelligenceStrip />

      {/* ── C. Life Areas ────────────────────────────────────────────────── */}
      <LifeAreasGrid objectives={objectives} />

      {/* ── D. Streak Risks ──────────────────────────────────────────────── */}
      <StreakRisksSection />

      {/* ── Quick Stats row ──────────────────────────────────────────────── */}
      <div className="overflow-x-auto -mx-4 sm:mx-0 mb-5">
        <div className="flex sm:grid sm:grid-cols-5 gap-3 px-4 sm:px-0 min-w-max sm:min-w-0 pb-2 sm:pb-0">

          {/* Ziel-Fortschritt */}
          <Link href="/objectives" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-2">
              <CircularProgress value={goalProgress} size={52} strokeWidth={5} color="#3b82f6" label={`${goalProgress}%`} />
              <div>
                <div className="text-zinc-300 text-xs font-medium">Ziel-Fortschritt</div>
                <div className="text-zinc-600 text-xs mt-0.5">{activeObjectives.length} aktiv</div>
              </div>
            </div>
          </Link>

          {/* Streak */}
          <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-1">
            <div className="text-3xl">🔥</div>
            <div className={cn("text-2xl font-bold leading-none", streakDays > 0 ? "text-orange-400" : "text-zinc-500")}>
              {streakDays}
            </div>
            <div className="text-zinc-500 text-xs">Tage Streak</div>
          </div>

          {/* Mood */}
          <Link href="/logs?type=mood" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-1">
              <div className="text-3xl">{latestMood != null ? getMoodEmoji(latestMood) : "⚡"}</div>
              {latestMood != null ? (
                <>
                  <div className="text-2xl font-bold text-yellow-400 leading-none">{latestMood}/10</div>
                  <div className="text-zinc-500 text-xs">Letzte Stimmung</div>
                </>
              ) : (
                <>
                  <div className="text-sm font-medium text-zinc-400">–</div>
                  <div className="text-blue-500 text-xs">Jetzt tracken →</div>
                </>
              )}
            </div>
          </Link>

          {/* Tasks diese Woche */}
          <Link href="/tasks" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-2">
              <CircularProgress value={weeklyTasksPct} size={52} strokeWidth={5} color="#22c55e" label={`${tasksDoneThisWeek}/${totalWeeklyTasks}`} />
              <div>
                <div className="text-zinc-300 text-xs font-medium">Tasks diese Woche</div>
                <div className="text-zinc-600 text-xs mt-0.5">erledigt</div>
              </div>
            </div>
          </Link>

          {/* Wasser */}
          <Link href="/logs?type=water" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-2">
              <CircularProgress value={Math.min(100, (waterToday / 3) * 100)} size={52} strokeWidth={5} color="#38bdf8" label={`${waterToday}L`} />
              <div>
                <div className="text-zinc-300 text-xs font-medium">Wasser heute</div>
                <div className="text-zinc-600 text-xs mt-0.5">Ziel: 3L</div>
              </div>
            </div>
          </Link>
        </div>
      </div>

      {/* ── F. Quick Actions ─────────────────────────────────────────────── */}
      <QuickActions />

      {/* ── G. Evening Check-in banner ───────────────────────────────────── */}
      <EveningCheckinBanner />

      {/* ── E. Autopilot Intelligence Cards ─────────────────────────────── */}
      <AutopilotIntelligenceCards />

      {/* Autopilot Confidence */}
      <ConfidenceCard />

      {/* Behavioral Patterns */}
      <PatternsCard />

      {/* Health Correlations */}
      <CorrelationCard />

      {/* P2.3 — Proaktive Vorschläge */}
      {autopilotSuggestions && autopilotSuggestions.suggestions.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <h3 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
            <span>💡</span> Proaktive Vorschläge
          </h3>
          <div className="space-y-2">
            {autopilotSuggestions.suggestions.slice(0, 3).map((item, i) => (
              <div key={i} className="flex items-start gap-3 py-1.5">
                <span className="text-indigo-400 shrink-0 mt-0.5">›</span>
                <div>
                  <p className="text-zinc-200 text-sm">{item.message}</p>
                  {item.action_hint && (
                    <p className="text-zinc-500 text-xs mt-0.5">{item.action_hint}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Quick Access Cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">

        {/* Fitness */}
        <Link href="/fitness" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">💪</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Dein Fitnessplan</div>
              <div className="text-zinc-500 text-xs mt-0.5 truncate">{lastWorkoutLabel}</div>
              <div className="text-zinc-600 text-xs">{workoutsThisWeek}× diese Woche</div>
            </div>
            <div className="text-zinc-600 shrink-0">›</div>
          </div>
        </Link>

        {/* Routinen */}
        <Link href="/routines" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">🌅</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Deine Routine</div>
              <div className={cn("text-xs mt-0.5", routinesDone === routinesTotal && routinesTotal > 0 ? "text-green-400" : "text-zinc-500")}>
                {routinesDone} von {routinesTotal} erledigt
              </div>
              <div className="text-zinc-600 text-xs">Daily Quests</div>
            </div>
            <div className="text-zinc-600 shrink-0">›</div>
          </div>
        </Link>

        {/* AI Coach */}
        <a href="https://t.me" target="_blank" rel="noopener noreferrer" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">🧠</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">AI Coach</div>
              <div className="text-zinc-500 text-xs mt-0.5">Telegram Bot öffnen</div>
              <div className="text-zinc-600 text-xs">Dein persönlicher COO</div>
            </div>
            <div className="text-zinc-600 shrink-0">›</div>
          </div>
        </a>

        {/* Brain Dump */}
        <Link href="/brain-dumps" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">📥</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Brain Dump</div>
              <div className="text-zinc-500 text-xs mt-0.5">Gedanken abladen</div>
              <div className="text-zinc-600 text-xs">AI verarbeitet automatisch</div>
            </div>
            <div className="text-zinc-600 shrink-0">›</div>
          </div>
        </Link>

        {/* Einkaufsliste */}
        <Link href="/shopping" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">🛒</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Einkaufsliste</div>
              <div className={cn("text-xs mt-0.5", shoppingItems > 0 ? "text-yellow-400" : "text-zinc-500")}>
                {shoppingItems > 0 ? `${shoppingItems} Items offen` : "Liste ist leer"}
              </div>
              <div className="text-zinc-600 text-xs">Per Telegram hinzufügen</div>
            </div>
            <div className="text-zinc-600 shrink-0">›</div>
          </div>
        </Link>
      </div>

      {/* Recent Achievements */}
      {gamification && gamification.recent_achievements.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <span>🏆</span> Letzte Erfolge
            <Link href="/achievements" className="text-xs text-blue-400 hover:text-blue-300 ml-auto transition-colors">
              Alle anzeigen →
            </Link>
          </h2>
          <div className="space-y-2">
            {gamification.recent_achievements.map((a) => (
              <div key={a.id} className="flex items-center gap-3 py-2 border-b border-zinc-800 last:border-0">
                <span className="text-xl w-8 text-center shrink-0">{a.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-medium truncate">{a.title}</div>
                  <div className="text-zinc-500 text-xs">
                    {new Date(a.unlocked_at).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}
                  </div>
                </div>
                <span className="text-yellow-500 text-xs font-medium shrink-0">+{a.xp_reward} XP</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mission Board */}
      <div className="mb-6">
        <MissionBoard routines={routines} tasks={tasks} />
      </div>

      {/* Activity Timeline */}
      {recentLogs.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <span>📋</span> Letzte Aktivitäten
            <Link href="/logs" className="text-xs text-blue-400 hover:text-blue-300 ml-auto transition-colors">
              Alle →
            </Link>
          </h2>
          <div className="space-y-0">
            {recentLogs.map((log, i) => {
              const emoji =
                log.log_type === "mood"
                  ? getMoodEmoji(Number(log.data.score) || 0)
                  : LOG_TYPE_EMOJI[log.log_type] ?? LOG_TYPE_EMOJI.default;
              const color = LOG_TYPE_COLOR[log.log_type] ?? "text-zinc-400";
              return (
                <div key={log.id} className="flex items-start gap-3 py-2.5 border-b border-zinc-800 last:border-0">
                  <div className="flex flex-col items-center shrink-0">
                    <span className="text-base">{emoji}</span>
                    {i < recentLogs.length - 1 && (
                      <div className="w-px h-full min-h-[12px] bg-zinc-700 mt-1" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 pb-1">
                    <span className={cn("text-sm", color)}>{formatActivityLog(log)}</span>
                    <div className="text-zinc-500 text-xs mt-0.5">{formatTimeAgo(log.logged_at)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Week Heatmap */}
      <WeekHeatmap logs={allLogs} />
    </div>
  );
}
