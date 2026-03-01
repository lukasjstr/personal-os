"use client";

import Header from "@/components/Header";
import StatCard from "@/components/StatCard";
import ProgressBar from "@/components/ProgressBar";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import Badge from "@/components/Badge";
import { useDashboard, useObjectives, useTasks, useRoutines } from "@/hooks/useApi";
import { CATEGORY_EMOJI, STATUS_COLOR, getMoodEmoji, formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const { data: dash, error: dashError, isLoading: dashLoading } = useDashboard();
  const { data: objData } = useObjectives();
  const { data: taskData } = useTasks();
  const { data: routineData } = useRoutines();

  if (dashLoading) return <LoadingSpinner />;
  if (dashError) {
    if (dashError.message === "UNAUTHORIZED") {
      return <ErrorState message="Ungültiger API Token. Bitte in den Einstellungen aktualisieren." />;
    }
    return <ErrorState message={dashError.message} />;
  }

  const stats = dash?.stats;
  const user = dash?.user;
  const objectives = objData?.objectives?.filter((o) => o.status === "active") ?? [];
  const tasks = taskData?.tasks?.slice(0, 8) ?? [];
  const routines = routineData?.routines ?? [];

  const today = new Date();
  const greeting =
    today.getHours() < 12 ? "Guten Morgen" : today.getHours() < 18 ? "Guten Tag" : "Guten Abend";

  return (
    <div>
      <Header
        title={`${greeting}${user?.first_name ? `, ${user.first_name}` : ""} 👋`}
        subtitle={`${today.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })}`}
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          emoji="🎯"
          label="Aktive Ziele"
          value={stats?.active_objectives ?? 0}
          color="blue"
        />
        <StatCard
          emoji="✅"
          label="Offene Tasks"
          value={stats?.open_tasks ?? 0}
          color={stats?.open_tasks && stats.open_tasks > 10 ? "yellow" : "default"}
        />
        <StatCard
          emoji="💧"
          label="Wasser heute"
          value={`${stats?.water_today_liters ?? 0}L`}
          sub="Ziel: 3L"
          color={stats?.water_today_liters && stats.water_today_liters >= 3 ? "green" : "default"}
        />
        <StatCard
          emoji="💪"
          label="Workouts/Woche"
          value={stats?.workouts_this_week ?? 0}
          color={stats?.workouts_this_week && stats.workouts_this_week >= 4 ? "green" : "default"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Active Objectives */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <span>🎯</span> Aktive Objectives
          </h2>
          {objectives.length === 0 ? (
            <p className="text-zinc-500 text-sm">Keine aktiven Objectives</p>
          ) : (
            <div className="space-y-4">
              {objectives.slice(0, 5).map((obj) => {
                const avgProgress =
                  obj.key_results.length > 0
                    ? Math.round(
                        obj.key_results.reduce((s, kr) => s + kr.progress_pct, 0) /
                          obj.key_results.length
                      )
                    : 0;
                return (
                  <div key={obj.id}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span>{CATEGORY_EMOJI[obj.category] ?? "🎯"}</span>
                      <span className="text-white text-sm font-medium">{obj.title}</span>
                      <Badge variant="blue">{avgProgress}%</Badge>
                    </div>
                    <ProgressBar value={avgProgress} showValue={false} size="sm" />
                    <div className="text-zinc-500 text-xs mt-1">
                      {obj.key_results.length} Key Result{obj.key_results.length !== 1 ? "s" : ""}
                      {obj.target_date ? ` · bis ${formatDate(obj.target_date)}` : ""}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Open Tasks */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <span>✅</span> Top Tasks
          </h2>
          {tasks.length === 0 ? (
            <p className="text-zinc-500 text-sm">Keine offenen Tasks — alles erledigt! 🎉</p>
          ) : (
            <div className="space-y-2">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-start gap-3 py-2 border-b border-zinc-800 last:border-0"
                >
                  <div
                    className={cn(
                      "mt-0.5 w-2 h-2 rounded-full shrink-0",
                      task.priority === 1 ? "bg-red-400" :
                      task.priority === 2 ? "bg-orange-400" :
                      task.priority === 3 ? "bg-yellow-400" : "bg-zinc-500"
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{task.title}</div>
                    {task.due_date && (
                      <div className="text-xs text-zinc-500 mt-0.5">
                        📅 {formatDate(task.due_date)}
                      </div>
                    )}
                  </div>
                  <Badge
                    variant={
                      task.status === "in_progress" ? "blue" : "outline"
                    }
                  >
                    {task.status === "in_progress" ? "In Arbeit" : "Offen"}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Routines Today */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <span>🔄</span> Routinen heute
            {stats && (
              <span className="text-xs text-zinc-400 ml-auto">
                {stats.routines_done_today}/{stats.routines_total} erledigt
              </span>
            )}
          </h2>
          {routines.length === 0 ? (
            <p className="text-zinc-500 text-sm">Keine aktiven Routinen</p>
          ) : (
            <div className="space-y-2">
              {routines.map((r) => (
                <div key={r.id} className="flex items-center gap-3">
                  <span className="text-lg">{r.completed_today ? "✅" : "☐"}</span>
                  <div>
                    <div
                      className={cn(
                        "text-sm",
                        r.completed_today ? "text-zinc-500 line-through" : "text-white"
                      )}
                    >
                      {r.title}
                    </div>
                    {r.frequency_human && (
                      <div className="text-xs text-zinc-500">{r.frequency_human}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Stats */}
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
              <ProgressBar
                value={((stats?.water_today_liters ?? 0) / 3) * 100}
                showValue={false}
                color="blue"
                size="sm"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-zinc-400 text-sm">Routinen heute</span>
                <span className="text-sm text-white">
                  {stats?.routines_done_today ?? 0}/{stats?.routines_total ?? 0}
                </span>
              </div>
              <ProgressBar
                value={
                  stats?.routines_total
                    ? ((stats.routines_done_today ?? 0) / stats.routines_total) * 100
                    : 0
                }
                showValue={false}
                color="green"
                size="sm"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400 text-sm">Einkaufsliste</span>
              <span className="text-sm text-white">{stats?.shopping_items ?? 0} Items</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
