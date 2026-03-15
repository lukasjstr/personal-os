"use client";

import React from "react";
import Link from "next/link";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import XPBar from "@/components/XPBar";
import MissionBoard from "@/components/MissionBoard";
import WeekHeatmap from "@/components/WeekHeatmap";
import CircularProgress from "@/components/CircularProgress";
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
} from "@/hooks/useApi";
import AutopilotIntelligenceCards from "@/components/AutopilotIntelligenceCards";
import PatternsCard from "@/components/PatternsCard";
import ConfidenceCard from "@/components/ConfidenceCard";
import HealthCard from "@/components/HealthCard";
import { getMoodEmoji, formatTimeAgo, LOG_TYPE_EMOJI, cn } from "@/lib/utils";
import type { DailySuggestionsResponse, Log } from "@/lib/api";

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

function AiCoachSection({ suggestionsData }: { suggestionsData: DailySuggestionsResponse | undefined }) {
  const [open, setOpen] = React.useState(true);
  const s = suggestionsData?.suggestions;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl mb-6 overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/50 transition-colors"
      >
        <h2 className="text-white font-semibold flex items-center gap-2">
          <span>💡</span> Dein AI-Coach sagt heute:
        </h2>
        <span className="text-zinc-500 text-sm">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4">
          {!suggestionsData ? (
            <p className="text-zinc-500 text-sm">Lädt…</p>
          ) : !s ? (
            <p className="text-zinc-500 text-sm italic">
              Empfehlungen werden morgen früh um 06:30 generiert.
            </p>
          ) : (
            <>
              {/* Fokus-Tasks */}
              {s.fokus_heute && s.fokus_heute.filter((f) => f.task && f.task !== "—").length > 0 && (
                <div>
                  <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-2">
                    Fokus heute
                  </div>
                  <ul className="space-y-2">
                    {s.fokus_heute.filter((f) => f.task && f.task !== "—").map((f, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-blue-400 font-bold shrink-0 mt-0.5">{i + 1}.</span>
                        <div>
                          <div className="text-white text-sm font-medium">{f.task}</div>
                          {f.begruendung && (
                            <div className="text-zinc-500 text-xs mt-0.5">{f.begruendung}</div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Tipp */}
              {s.tipp && (
                <div className="bg-emerald-950/50 border border-emerald-800/40 rounded-lg px-4 py-3">
                  <div className="text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1">
                    Tipp des Tages
                  </div>
                  <p className="text-emerald-200 text-sm">{s.tipp}</p>
                </div>
              )}

              {/* Streak-Warnung */}
              {s.streak_warnung && (
                <div className="bg-orange-950/50 border border-orange-800/40 rounded-lg px-4 py-3">
                  <div className="text-orange-400 text-xs font-semibold uppercase tracking-wider mb-1">
                    ⚠️ Streak-Alarm
                  </div>
                  <p className="text-orange-200 text-sm">{s.streak_warnung}</p>
                </div>
              )}

              {/* Dimension Check */}
              {s.dimension_check && (
                <div className="bg-purple-950/50 border border-purple-800/40 rounded-lg px-4 py-3">
                  <div className="text-purple-400 text-xs font-semibold uppercase tracking-wider mb-1">
                    Dimensionen-Check
                  </div>
                  <p className="text-purple-200 text-sm">{s.dimension_check}</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { data: dash, error: dashError, isLoading: dashLoading } = useDashboard();
  const { data: taskData } = useTasks();
  const { data: routineData } = useRoutines();
  const { data: logsData } = useLogs(undefined, 7);
  const { data: objectivesData } = useObjectives();
  const { data: weeklySummary } = useWeeklySummary();
  const { data: fitnessSummary } = useFitnessSummary();
  const { data: gamification } = useGamificationStats();
  const { data: suggestionsData } = useTodaySuggestions();
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

  // Goal progress — average of all active objectives' key result progress
  const objectives = objectivesData?.objectives ?? [];
  const activeObjectives = objectives.filter((o) => o.status === "active");
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
      {/* Hero */}
      <div className="mb-6">
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

      {/* Quick Stats — horizontal scroll on mobile, 5-col grid on sm+ */}
      <div className="overflow-x-auto -mx-4 sm:mx-0 mb-6">
        <div className="flex sm:grid sm:grid-cols-5 gap-3 px-4 sm:px-0 min-w-max sm:min-w-0 pb-2 sm:pb-0">

          {/* 🎯 Ziel-Fortschritt */}
          <Link href="/objectives" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-2">
              <CircularProgress
                value={goalProgress}
                size={52}
                strokeWidth={5}
                color="#3b82f6"
                label={`${goalProgress}%`}
              />
              <div>
                <div className="text-zinc-300 text-xs font-medium">Ziel-Fortschritt</div>
                <div className="text-zinc-600 text-xs mt-0.5">{activeObjectives.length} aktiv</div>
              </div>
            </div>
          </Link>

          {/* 🔥 Streak */}
          <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-1">
            <div className="text-3xl">🔥</div>
            <div
              className={cn(
                "text-2xl font-bold leading-none",
                streakDays > 0 ? "text-orange-400" : "text-zinc-500"
              )}
            >
              {streakDays}
            </div>
            <div className="text-zinc-500 text-xs">Tage Streak</div>
            {streakDays > 0 && (
              <div className="text-zinc-700 text-xs">am Laufen</div>
            )}
          </div>

          {/* ⚡ Mood */}
          <Link href="/logs?type=mood" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-1">
              <div className="text-3xl">
                {latestMood != null ? getMoodEmoji(latestMood) : "⚡"}
              </div>
              {latestMood != null ? (
                <>
                  <div className="text-2xl font-bold text-yellow-400 leading-none">
                    {latestMood}/10
                  </div>
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

          {/* 📊 Woche Tasks */}
          <Link href="/tasks" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-2">
              <CircularProgress
                value={weeklyTasksPct}
                size={52}
                strokeWidth={5}
                color="#22c55e"
                label={`${tasksDoneThisWeek}/${totalWeeklyTasks}`}
              />
              <div>
                <div className="text-zinc-300 text-xs font-medium">Tasks diese Woche</div>
                <div className="text-zinc-600 text-xs mt-0.5">erledigt</div>
              </div>
            </div>
          </Link>

          {/* 💧 Wasser */}
          <Link href="/logs?type=water" className="block hover:opacity-90 transition-opacity">
            <div className="w-[148px] sm:w-auto bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col items-center text-center gap-2">
              <CircularProgress
                value={Math.min(100, (waterToday / 3) * 100)}
                size={52}
                strokeWidth={5}
                color="#38bdf8"
                label={`${waterToday}L`}
              />
              <div>
                <div className="text-zinc-300 text-xs font-medium">Wasser heute</div>
                <div className="text-zinc-600 text-xs mt-0.5">Ziel: 3L</div>
              </div>
            </div>
          </Link>
        </div>
      </div>

      {/* AI Coach Daily Suggestions */}
      <AiCoachSection suggestionsData={suggestionsData} />

      {/* P2.3 — Autopilot Suggestions Widget */}
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

      {/* Autopilot Confidence (E5) */}
      <ConfidenceCard />

      {/* Behavioral Patterns (E3) */}
      <PatternsCard />

      {/* Autopilot Intelligence Cards (D1) */}
      <AutopilotIntelligenceCards />

      {/* Health Card — Fitness Split + Supplements + Macros */}
      <HealthCard />

      {/* Quick Access Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">

        {/* 💪 Fitness */}
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

        {/* 🌅 Routinen */}
        <Link href="/routines" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">🌅</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Deine Routine</div>
              <div
                className={cn(
                  "text-xs mt-0.5",
                  routinesDone === routinesTotal && routinesTotal > 0
                    ? "text-green-400"
                    : "text-zinc-500"
                )}
              >
                {routinesDone} von {routinesTotal} erledigt
              </div>
              <div className="text-zinc-600 text-xs">Daily Quests</div>
            </div>
            <div className="text-zinc-600 shrink-0">›</div>
          </div>
        </Link>

        {/* 🧠 AI Coach */}
        <a
          href="https://t.me"
          target="_blank"
          rel="noopener noreferrer"
          className="block hover:opacity-90 transition-opacity"
        >
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

        {/* 📥 Brain Dump */}
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

        {/* 🛒 Einkaufsliste */}
        <Link href="/shopping" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-4 min-h-[72px]">
            <div className="text-3xl shrink-0">🛒</div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm">Einkaufsliste</div>
              <div
                className={cn(
                  "text-xs mt-0.5",
                  shoppingItems > 0 ? "text-yellow-400" : "text-zinc-500"
                )}
              >
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
            <Link
              href="/achievements"
              className="text-xs text-blue-400 hover:text-blue-300 ml-auto transition-colors"
            >
              Alle anzeigen →
            </Link>
          </h2>
          <div className="space-y-2">
            {gamification.recent_achievements.map((a) => (
              <div
                key={a.id}
                className="flex items-center gap-3 py-2 border-b border-zinc-800 last:border-0"
              >
                <span className="text-xl w-8 text-center shrink-0">{a.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-medium truncate">{a.title}</div>
                  <div className="text-zinc-500 text-xs">
                    {new Date(a.unlocked_at).toLocaleDateString("de-DE", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                    })}
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
            <Link
              href="/logs"
              className="text-xs text-blue-400 hover:text-blue-300 ml-auto transition-colors"
            >
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
                <div
                  key={log.id}
                  className="flex items-start gap-3 py-2.5 border-b border-zinc-800 last:border-0"
                >
                  <div className="flex flex-col items-center shrink-0">
                    <span className="text-base">{emoji}</span>
                    {i < recentLogs.length - 1 && (
                      <div className="w-px h-full min-h-[12px] bg-zinc-700 mt-1" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 pb-1">
                    <span className={cn("text-sm", color)}>{formatActivityLog(log)}</span>
                    <div className="text-zinc-500 text-xs mt-0.5">
                      {formatTimeAgo(log.logged_at)}
                    </div>
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
