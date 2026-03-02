"use client";

import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useObjectives } from "@/hooks/useApi";
import { CATEGORY_EMOJI, CATEGORY_COLORS, formatDate, cn } from "@/lib/utils";
import type { Objective, ObjectiveTask } from "@/lib/api";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  active: "Aktiv",
  completed: "Abgeschlossen",
  paused: "Pausiert",
  abandoned: "Aufgegeben",
};

const STATUS_STYLE: Record<string, string> = {
  active: "bg-green-900/50 text-green-400 border border-green-800/50",
  completed: "bg-blue-900/50 text-blue-400 border border-blue-800/50",
  paused: "bg-yellow-900/50 text-yellow-400 border border-yellow-800/50",
  abandoned: "bg-red-900/50 text-red-400 border border-red-800/50",
};

const KR_TYPE_LABEL: Record<string, string> = {
  percentage: "%",
  number: "#",
  boolean: "✓",
  streak: "🔥",
  checklist: "☑",
};

function TaskChecklist({ tasks }: { tasks: ObjectiveTask[] }) {
  if (tasks.length === 0) return null;
  const topLevel = tasks.filter((t) => !t.parent_task_id);
  const subTaskMap = tasks.reduce<Record<number, ObjectiveTask[]>>((acc, t) => {
    if (t.parent_task_id) {
      (acc[t.parent_task_id] ??= []).push(t);
    }
    return acc;
  }, {});

  function TaskRow({ task, indent = 0 }: { task: ObjectiveTask; indent?: number }) {
    const isDone = task.status === "done";
    const subs = subTaskMap[task.id] ?? [];
    return (
      <>
        <div
          className={cn(
            "flex items-center gap-2 py-1.5 text-sm",
            indent > 0 && "pl-6 border-l border-zinc-700/50 ml-3",
          )}
        >
          <span className={cn("shrink-0", isDone ? "text-green-400" : "text-zinc-500")}>
            {isDone ? "✅" : "☐"}
          </span>
          <span className={cn("flex-1", isDone ? "text-zinc-500 line-through" : "text-zinc-300")}>
            {task.title}
          </span>
          <span className="text-zinc-600 text-xs font-mono shrink-0">P{task.priority}</span>
        </div>
        {subs.map((sub) => (
          <TaskRow key={sub.id} task={sub} indent={indent + 1} />
        ))}
      </>
    );
  }

  return (
    <div className="px-5 py-3 border-t border-zinc-800 space-y-0.5">
      <div className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">Tasks</div>
      {topLevel.map((t) => (
        <TaskRow key={t.id} task={t} />
      ))}
    </div>
  );
}

function ObjectiveCard({ obj }: { obj: Objective }) {
  const [expanded, setExpanded] = useState(obj.status === "active");
  const isLifeArea = obj.key_results.length === 0 && obj.tasks.length === 0;
  const catColor = CATEGORY_COLORS[obj.category] ?? CATEGORY_COLORS.default;

  // Progress: prefer KR-based, fall back to task completion rate
  const krProgress =
    obj.key_results.length > 0
      ? Math.round(
          obj.key_results.reduce((s, kr) => s + kr.progress_pct, 0) / obj.key_results.length
        )
      : null;

  const taskProgress =
    obj.tasks.length > 0
      ? Math.round((obj.tasks.filter((t) => t.status === "done").length / obj.tasks.length) * 100)
      : null;

  const avgProgress = krProgress ?? taskProgress ?? 0;

  const progressColor =
    avgProgress >= 75 ? "#22c55e" : avgProgress >= 40 ? "#3b82f6" : avgProgress >= 20 ? "#f59e0b" : "#ef4444";

  if (isLifeArea) {
    return (
      <div
        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border text-sm"
        style={{ borderColor: catColor.hex + "40", backgroundColor: catColor.hex + "10" }}
      >
        <span>{CATEGORY_EMOJI[obj.category] ?? "🎯"}</span>
        <span style={{ color: catColor.hex }}>{obj.title}</span>
        <span className="text-zinc-600 text-xs">Life Area</span>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden flex">
      {/* Category color bar */}
      <div className="w-1 shrink-0" style={{ backgroundColor: catColor.hex }} />

      <div className="flex-1 min-w-0">
        {/* Header */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-4 p-5 hover:bg-zinc-800/40 transition-colors text-left"
        >
          <span className="text-2xl shrink-0">{CATEGORY_EMOJI[obj.category] ?? "🎯"}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h3 className="font-semibold text-white">{obj.title}</h3>
              <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", STATUS_STYLE[obj.status] ?? "bg-zinc-800 text-zinc-400")}>
                {STATUS_LABEL[obj.status] ?? obj.status}
              </span>
              <span
                className="text-xs px-2 py-0.5 rounded-full font-medium border"
                style={{ color: catColor.hex, borderColor: catColor.hex + "50", backgroundColor: catColor.hex + "15" }}
              >
                {obj.category}
              </span>
            </div>
            {obj.description && (
              <p className="text-zinc-500 text-xs truncate">{obj.description}</p>
            )}
            {/* Overall progress bar */}
            <div className="flex items-center gap-3 mt-2">
              <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${avgProgress}%`, backgroundColor: progressColor }}
                />
              </div>
              <span className="text-xs font-medium shrink-0" style={{ color: progressColor }}>
                {avgProgress}%
              </span>
            </div>
          </div>
          <div className="text-zinc-500 shrink-0">
            {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </div>
        </button>

        {/* Key Results */}
        {expanded && obj.key_results.length > 0 && (
          <div className="border-t border-zinc-800 divide-y divide-zinc-800/50">
            {obj.key_results.map((kr) => (
              <div key={kr.id} className="px-5 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                      {KR_TYPE_LABEL[kr.metric_type] ?? kr.metric_type}
                    </span>
                    <span className="text-sm text-zinc-300">{kr.title}</span>
                    {kr.status === "completed" && <span className="text-green-400 text-xs">✓ Done</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all duration-500"
                        style={{ width: `${kr.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-zinc-400 shrink-0">{kr.progress_pct}%</span>
                  </div>
                </div>
                <div className="text-right shrink-0 w-28">
                  <div className="text-sm text-white font-medium">
                    {kr.current_value}
                    {kr.unit ? ` ${kr.unit}` : ""}
                    {kr.target_value != null && (
                      <span className="text-zinc-500 font-normal">
                        {" / "}
                        {kr.target_value}
                        {kr.unit ? ` ${kr.unit}` : ""}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Task Checklist */}
        {expanded && obj.tasks.length > 0 && (
          <TaskChecklist tasks={obj.tasks} />
        )}

        {/* Footer */}
        <div className="border-t border-zinc-800 px-5 py-2 flex items-center gap-4 text-xs text-zinc-500">
          <span>{obj.key_results.length} KRs</span>
          {obj.tasks.length > 0 && (
            <span>
              {obj.tasks.filter((t) => t.status === "done").length}/{obj.tasks.length} Tasks
            </span>
          )}
          {obj.target_date && <span>📅 bis {formatDate(obj.target_date)}</span>}
          <span className="ml-auto">erstellt {formatDate(obj.created_at)}</span>
        </div>
      </div>
    </div>
  );
}

const FILTERS = ["all", "active", "completed", "paused", "abandoned"] as const;
const FILTER_LABELS: Record<string, string> = {
  all: "Alle",
  active: "Aktiv",
  completed: "Abgeschlossen",
  paused: "Pausiert",
  abandoned: "Aufgegeben",
};

export default function ObjectivesPage() {
  const { data, error, isLoading } = useObjectives();
  const [filter, setFilter] = useState<string>("all");

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const all = data?.objectives ?? [];
  const lifeAreas = all.filter((o) => o.key_results.length === 0 && o.tasks.length === 0 && o.status === "active");
  const realObjectives = all.filter((o) => o.key_results.length > 0 || o.tasks.length > 0);
  const filtered = filter === "all" ? realObjectives : realObjectives.filter((o) => o.status === filter);

  const counts = {
    all: realObjectives.length,
    active: realObjectives.filter((o) => o.status === "active").length,
    completed: realObjectives.filter((o) => o.status === "completed").length,
    paused: realObjectives.filter((o) => o.status === "paused").length,
    abandoned: realObjectives.filter((o) => o.status === "abandoned").length,
  };

  return (
    <div>
      <Header
        title="🎯 Objectives"
        subtitle={`${counts.active} aktiv · ${counts.completed} abgeschlossen`}
      />

      {/* Life Areas */}
      {lifeAreas.length > 0 && (
        <div className="mb-6">
          <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-3">
            Life Areas
          </div>
          <div className="flex flex-wrap gap-2">
            {lifeAreas.map((obj) => (
              <ObjectiveCard key={obj.id} obj={obj} />
            ))}
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm transition-colors",
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            )}
          >
            {FILTER_LABELS[f]} ({counts[f as keyof typeof counts] ?? 0})
          </button>
        ))}
      </div>

      {/* Objectives List */}
      {filtered.length === 0 ? (
        <EmptyState emoji="🎯" message="Keine Objectives gefunden" />
      ) : (
        <div className="space-y-4">
          {filtered.map((obj) => (
            <ObjectiveCard key={obj.id} obj={obj} />
          ))}
        </div>
      )}
    </div>
  );
}
