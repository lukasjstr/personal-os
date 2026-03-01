"use client";

import Link from "next/link";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import XPBar from "@/components/XPBar";
import MissionBoard from "@/components/MissionBoard";
import WeekHeatmap from "@/components/WeekHeatmap";
import CircularProgress from "@/components/CircularProgress";
import { useDashboard, useTasks, useRoutines, useLogs } from "@/hooks/useApi";
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

  const today = new Date();
  const greeting =
    today.getHours() < 12 ? "Guten Morgen" : today.getHours() < 18 ? "Guten Tag" : "Guten Abend";
  const dayStr = today.toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const openTasksCount = stats?.open_tasks ?? 0;
  const taskCardColor =
    openTasksCount > 15 ? "red" : openTasksCount > 10 ? "yellow" : "default";

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
          {(stats?.streak_days ?? 0) > 0 && (
            <div className="bg-orange-950/60 border border-orange-800/40 rounded-xl px-3 py-2 flex items-center gap-2">
              <span className="text-xl">🔥</span>
              <div>
                <div className="text-orange-400 font-bold text-lg leading-none">
                  {stats?.streak_days}
                </div>
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

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Link href="/objectives" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 h-full">
            <div className="text-2xl mb-1">🎯</div>
            <div
              className={cn(
                "text-2xl font-bold",
                (stats?.active_objectives ?? 0) > 0 ? "text-blue-400" : "text-zinc-500"
              )}
            >
              {stats?.active_objectives ?? 0}
            </div>
            <div className="text-zinc-500 text-xs mt-0.5">Aktive Ziele</div>
          </div>
        </Link>

        <Link href="/tasks" className="block hover:opacity-90 transition-opacity">
          <div
            className={cn(
              "bg-zinc-900 border rounded-xl p-4 h-full",
              taskCardColor === "red"
                ? "border-red-800/60"
                : taskCardColor === "yellow"
                ? "border-yellow-800/60"
                : "border-zinc-800"
            )}
          >
            <div className="text-2xl mb-1">✅</div>
            <div
              className={cn(
                "text-2xl font-bold",
                taskCardColor === "red"
                  ? "text-red-400"
                  : taskCardColor === "yellow"
                  ? "text-yellow-400"
                  : "text-white"
              )}
            >
              {openTasksCount}
            </div>
            <div className="text-zinc-500 text-xs mt-0.5">Offene Tasks</div>
          </div>
        </Link>

        <Link href="/logs?type=water" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-3 h-full">
            <CircularProgress
              value={Math.min(100, ((stats?.water_today_liters ?? 0) / 3) * 100)}
              size={52}
              strokeWidth={5}
              color="#3b82f6"
              label={`${stats?.water_today_liters ?? 0}L`}
            />
            <div>
              <div className="text-zinc-400 text-xs">Wasser heute</div>
              <div className="text-zinc-500 text-xs mt-0.5">Ziel: 3L</div>
            </div>
          </div>
        </Link>

        <Link href="/routines" className="block hover:opacity-90 transition-opacity">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-3 h-full">
            <CircularProgress
              value={
                stats?.routines_total
                  ? Math.round(((stats.routines_done_today ?? 0) / stats.routines_total) * 100)
                  : 0
              }
              size={52}
              strokeWidth={5}
              color="#22c55e"
              label={`${stats?.routines_done_today ?? 0}/${stats?.routines_total ?? 0}`}
            />
            <div>
              <div className="text-zinc-400 text-xs">Routinen heute</div>
              <div className="text-zinc-500 text-xs mt-0.5">
                {stats?.routines_done_today === stats?.routines_total &&
                (stats?.routines_total ?? 0) > 0
                  ? "✅ Alle done"
                  : "Daily Quests"}
              </div>
            </div>
          </div>
        </Link>
      </div>

      {/* Mission Board + Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <MissionBoard routines={routines} tasks={tasks} />

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <span>📊</span> Schnellübersicht
          </h2>
          <div className="space-y-4">
            {stats?.latest_mood !== null && stats?.latest_mood !== undefined && (
              <div className="flex items-center justify-between">
                <span className="text-zinc-400 text-sm">Letzte Stimmung</span>
                <span className="flex items-center gap-1.5 text-sm text-white">
                  {getMoodEmoji(stats.latest_mood)} {stats.latest_mood}/10
                </span>
              </div>
            )}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-zinc-400 text-sm">Wasser heute</span>
                <span className="text-sm text-white">{stats?.water_today_liters ?? 0}/3L</span>
              </div>
              <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, ((stats?.water_today_liters ?? 0) / 3) * 100)}%`,
                  }}
                />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-zinc-400 text-sm">Routinen heute</span>
                <span className="text-sm text-white">
                  {stats?.routines_done_today ?? 0}/{stats?.routines_total ?? 0}
                </span>
              </div>
              <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 rounded-full transition-all"
                  style={{
                    width: `${
                      stats?.routines_total
                        ? ((stats.routines_done_today ?? 0) / stats.routines_total) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400 text-sm">Workouts diese Woche</span>
              <Link
                href="/fitness"
                className="text-sm text-white hover:text-blue-400 transition-colors"
              >
                💪 {stats?.workouts_this_week ?? 0}x
              </Link>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400 text-sm">Einkaufsliste</span>
              <Link
                href="/shopping"
                className="text-sm text-white hover:text-blue-400 transition-colors"
              >
                🛒 {stats?.shopping_items ?? 0} Items
              </Link>
            </div>
          </div>
        </div>
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
