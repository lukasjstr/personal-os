"use client";

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
} from "@/hooks/useApi";
import { getMoodEmoji, formatTimeAgo, LOG_TYPE_EMOJI, cn } from "@/lib/utils";
import type { Log } from "@/lib/api";

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

export default function DashboardPage() {
  const { data: dash, error: dashError, isLoading: dashLoading } = useDashboard();
  const { data: taskData } = useTasks();
  const { data: routineData } = useRoutines();
  const { data: logsData } = useLogs(undefined, 7);
  const { data: objectivesData } = useObjectives();
  const { data: weeklySummary } = useWeeklySummary();
  const { data: fitnessSummary } = useFitnessSummary();

  if (dashLoading) return <LoadingSpinner />;
  if (dashError) {
    if (dashError.message === "UNAUTHORIZED") {
      return <ErrorState message="Ungültiger API Token. Bitte in den Einstellungen aktualisieren." />;
    }
    return <ErrorState message={dashError.message} />;
  }

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

  return (
    <div>
      {/* Hero */}
      <div className="mb-6">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-2xl font-bold text-white">
              {greeting}{user?.first_name ? `, ${user.first_name}` : ""} 👋
            </h1>
            <p className="text-zinc-500 text-sm mt-0.5">{dayStr}</p>
          </div>
          {streakDays > 0 && (
            <div className="bg-orange-950/60 border border-orange-800/40 rounded-xl px-3 py-2 flex items-center gap-2">
              <span className="text-xl">🔥</span>
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
