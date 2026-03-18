"use client";

import { useMemo } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { EmptyState, ErrorState } from "@/components/LoadingSpinner";
import { useWeeklySummary } from "@/hooks/useApi";
import { useTasks, useObjectives, useRoutines, useCalendar } from "@/hooks/useApi";
import { cn, formatDate } from "@/lib/utils";
import type { Task, Objective } from "@/lib/api";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <div className="text-xs text-zinc-500 mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function ProgressRing({ pct }: { pct: number }) {
  const r = 18;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <svg width="44" height="44" className="shrink-0">
      <circle cx="22" cy="22" r={r} fill="none" stroke="#27272a" strokeWidth="4" />
      <circle
        cx="22" cy="22" r={r} fill="none"
        stroke={pct >= 80 ? "#22c55e" : pct >= 50 ? "#eab308" : "#ef4444"}
        strokeWidth="4" strokeDasharray={c} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 22 22)"
      />
      <text x="22" y="26" textAnchor="middle" className="fill-zinc-300 text-[10px] font-medium">
        {pct}%
      </text>
    </svg>
  );
}

export default function WeeklyPage() {
  const { data: summary, error: summaryError, isLoading: summaryLoading } = useWeeklySummary();
  const { data: taskData } = useTasks();
  const { data: objData } = useObjectives();

  const weekTasks = useMemo(() => {
    if (!taskData?.tasks) return { due: [] as Task[], done: [] as Task[] };
    const now = new Date();
    const weekEnd = new Date(now);
    weekEnd.setDate(weekEnd.getDate() + (7 - weekEnd.getDay()));
    const due = taskData.tasks.filter(
      (t: Task) => t.status !== "done" && t.due_date && new Date(t.due_date) <= weekEnd
    );
    return { due };
  }, [taskData]);

  const activeObjectives = useMemo(() => {
    if (!objData?.objectives) return [];
    return objData.objectives.filter((o: Objective) => o.status === "active");
  }, [objData]);

  if (summaryLoading) return <LoadingSpinner />;
  if (summaryError) return <ErrorState message="Wochendaten konnten nicht geladen werden" />;

  const s = summary!;

  return (
    <div className="min-h-screen bg-black text-white">
      <Header title="Wochenziele" />
      <main className="max-w-4xl mx-auto px-4 py-6 space-y-8">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Tasks erledigt" value={s.tasks_done_this_week} sub={`${s.tasks_open} offen`} />
          <StatCard label="Routinen" value={`${s.routine_completion_rate}%`} />
          <StatCard label="Workouts" value={s.workout_days} sub="diese Woche" />
          <StatCard label="Wasser" value={`${s.water_avg_liters}L`} sub="Durchschnitt/Tag" />
        </div>

        {/* Mood */}
        {s.mood_avg !== null && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <h2 className="text-sm font-medium text-zinc-400 mb-2">Stimmung diese Woche</h2>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold">{s.mood_avg}/10</span>
              <div className="flex gap-1">
                {s.mood_scores.map((score, i) => (
                  <div
                    key={i}
                    className={cn(
                      "w-6 h-6 rounded text-xs flex items-center justify-center font-medium",
                      score >= 7 ? "bg-green-900/50 text-green-400" :
                      score >= 5 ? "bg-yellow-900/50 text-yellow-400" :
                      "bg-red-900/50 text-red-400"
                    )}
                  >
                    {score}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Active Objectives */}
        {activeObjectives.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-zinc-400 mb-3">Aktive Ziele</h2>
            <div className="space-y-2">
              {activeObjectives.map((obj: Objective) => {
                const krs = obj.key_results || [];
                const done = krs.filter((kr) => kr.status === "done").length;
                const pct = krs.length > 0 ? Math.round((done / krs.length) * 100) : 0;
                return (
                  <div key={obj.id} className="flex items-center gap-3 bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                    <ProgressRing pct={pct} />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{obj.title}</div>
                      <div className="text-xs text-zinc-500">{done}/{krs.length} Key Results</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tasks due this week */}
        {weekTasks.due.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-zinc-400 mb-3">Diese Woche fällig ({weekTasks.due.length})</h2>
            <div className="space-y-1">
              {weekTasks.due.map((t: Task) => (
                <div key={t.id} className="flex items-center gap-3 bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                  <span className={cn(
                    "w-2 h-2 rounded-full shrink-0",
                    t.priority <= 2 ? "bg-red-500" : t.priority <= 4 ? "bg-yellow-500" : "bg-zinc-500"
                  )} />
                  <span className="flex-1 truncate text-sm">{t.title}</span>
                  {t.due_date && (
                    <span className="text-xs text-zinc-500 shrink-0">{formatDate(t.due_date)}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {weekTasks.due.length === 0 && activeObjectives.length === 0 && (
          <EmptyState emoji="📖" message="Keine Wochenziele vorhanden. Erstelle Objectives und Tasks mit Fälligkeitsdaten." />
        )}
      </main>
    </div>
  );
}
