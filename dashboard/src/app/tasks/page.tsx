"use client";

import { useState } from "react";
import Header from "@/components/Header";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useAllTasks } from "@/hooks/useApi";
import {
  PRIORITY_LABEL,
  PRIORITY_COLOR,
  formatDate,
  formatTimeAgo,
  truncate,
  cn,
} from "@/lib/utils";
import type { Task } from "@/lib/api";

const STATUS_FILTERS = [
  { key: "all", label: "Alle" },
  { key: "todo", label: "Offen" },
  { key: "in_progress", label: "In Arbeit" },
  { key: "done", label: "Erledigt" },
  { key: "cancelled", label: "Abgebrochen" },
];

const STATUS_BADGE: Record<string, "outline" | "blue" | "green" | "red"> = {
  todo: "outline",
  in_progress: "blue",
  done: "green",
  cancelled: "red",
};

const STATUS_LABEL: Record<string, string> = {
  todo: "Offen",
  in_progress: "In Arbeit",
  done: "Erledigt",
  cancelled: "Abgebrochen",
};

const CATEGORY_BADGE: Record<string, "green" | "blue" | "yellow" | "purple" | "outline" | "orange"> = {
  health: "green",
  fitness: "blue",
  finance: "yellow",
  learning: "purple",
  personal: "outline",
  business: "orange",
  shopping: "yellow",
};

const PRIORITY_BADGE_COLOR: Record<number, string> = {
  1: "bg-red-900/60 text-red-400 border border-red-800",
  2: "bg-orange-900/60 text-orange-400 border border-orange-800",
  3: "bg-yellow-900/60 text-yellow-400 border border-yellow-800",
  4: "bg-blue-900/60 text-blue-400 border border-blue-800",
  5: "bg-zinc-800 text-zinc-500 border border-zinc-700",
};

function TaskRow({ task }: { task: Task }) {
  const isOverdue =
    task.due_date &&
    task.status !== "done" &&
    task.status !== "cancelled" &&
    new Date(task.due_date) < new Date();

  return (
    <div
      className={cn(
        "flex items-start gap-4 py-3 border-b border-zinc-800 last:border-0",
        task.status === "done" && "opacity-60"
      )}
    >
      {/* Priority indicator */}
      <div className="mt-1 shrink-0">
        <div
          className={cn(
            "w-2.5 h-2.5 rounded-full",
            task.priority === 1 ? "bg-red-400" :
            task.priority === 2 ? "bg-orange-400" :
            task.priority === 3 ? "bg-yellow-400" :
            task.priority === 4 ? "bg-blue-400" : "bg-zinc-600"
          )}
          title={PRIORITY_LABEL[task.priority]}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-2 flex-wrap">
          <span
            className={cn(
              "text-sm",
              task.status === "done" ? "text-zinc-500 line-through" : "text-white"
            )}
          >
            {task.title}
          </span>
          <Badge variant={STATUS_BADGE[task.status] ?? "outline"}>
            {STATUS_LABEL[task.status] ?? task.status}
          </Badge>
          {task.category && task.category !== "general" && (
            <Badge variant={CATEGORY_BADGE[task.category] ?? "outline"}>
              {task.category}
            </Badge>
          )}
        </div>
        {task.description && (
          <p className="text-zinc-500 text-xs mt-0.5">{truncate(task.description, 100)}</p>
        )}
        <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
          {task.due_date && (
            <span className={cn(isOverdue && "text-red-400")}>
              📅 {isOverdue ? "⚠️ " : ""}
              {formatDate(task.due_date)}
            </span>
          )}
          {task.completed_at && (
            <span className="text-green-500">✓ {formatTimeAgo(task.completed_at)}</span>
          )}
        </div>
      </div>

      {/* Priority badge */}
      <span
        className={cn(
          "text-xs px-1.5 py-0.5 rounded font-medium shrink-0",
          PRIORITY_BADGE_COLOR[task.priority] ?? "bg-zinc-800 text-zinc-500"
        )}
      >
        P{task.priority}
      </span>
    </div>
  );
}

function GroupedTaskList({ tasks }: { tasks: Task[] }) {
  const groups: Record<string, Task[]> = {};
  tasks.forEach((t) => {
    const cat = t.category ?? "general";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(t);
  });

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([category, catTasks]) => (
        <div key={category} className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-2">
          <div className="flex items-center gap-2 py-2 border-b border-zinc-800 mb-1">
            <Badge variant={CATEGORY_BADGE[category] ?? "outline"}>{category}</Badge>
            <span className="text-zinc-500 text-xs">{catTasks.length} Tasks</span>
          </div>
          {catTasks.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function TasksPage() {
  const { data, error, isLoading } = useAllTasks();
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [groupByCategory, setGroupByCategory] = useState(false);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  let tasks = data?.tasks ?? [];

  if (statusFilter !== "all") tasks = tasks.filter((t) => t.status === statusFilter);
  if (priorityFilter !== null) tasks = tasks.filter((t) => t.priority === priorityFilter);
  if (search.trim()) {
    const q = search.toLowerCase();
    tasks = tasks.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        (t.description?.toLowerCase().includes(q) ?? false)
    );
  }

  const all = data?.tasks ?? [];
  const statusCounts = STATUS_FILTERS.reduce(
    (acc, f) => ({
      ...acc,
      [f.key]: f.key === "all" ? all.length : all.filter((t) => t.status === f.key).length,
    }),
    {} as Record<string, number>
  );

  return (
    <div>
      <Header
        title="✅ Tasks"
        subtitle={`${statusCounts.todo} offen · ${statusCounts.in_progress} in Arbeit · ${statusCounts.done} erledigt`}
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 mb-6">
        {/* Status Filter */}
        <div className="flex gap-2 flex-wrap">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setStatusFilter(f.key)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm transition-colors",
                statusFilter === f.key
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:text-white"
              )}
            >
              {f.label} ({statusCounts[f.key] ?? 0})
            </button>
          ))}
        </div>

        {/* Priority + Search + Group */}
        <div className="flex gap-2 flex-wrap items-center">
          <div className="flex gap-1">
            {[null, 1, 2, 3, 4, 5].map((p) => (
              <button
                key={p ?? "all"}
                onClick={() => setPriorityFilter(p)}
                className={cn(
                  "px-2.5 py-1 rounded text-xs transition-colors",
                  priorityFilter === p
                    ? "bg-blue-600 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:text-white"
                )}
              >
                {p === null ? "Alle P" : `P${p}`}
              </button>
            ))}
          </div>
          <button
            onClick={() => setGroupByCategory(!groupByCategory)}
            className={cn(
              "px-3 py-1 rounded text-xs transition-colors",
              groupByCategory
                ? "bg-purple-700 text-white"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            )}
          >
            {groupByCategory ? "Gruppiert" : "Gruppieren"}
          </button>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Suchen..."
            className="flex-1 min-w-40 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>

      {/* Task list */}
      {tasks.length === 0 ? (
        <EmptyState emoji="✅" message="Keine Tasks gefunden" />
      ) : groupByCategory ? (
        <GroupedTaskList tasks={tasks} />
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-2">
          {tasks.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}
          <div className="py-2 text-xs text-zinc-600 text-center">
            {tasks.length} Tasks
          </div>
        </div>
      )}
    </div>
  );
}
