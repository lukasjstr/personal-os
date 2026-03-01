"use client";

import { useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useAllTasks } from "@/hooks/useApi";
import { CATEGORY_COLORS, PRIORITY_LABEL, formatDate, formatTimeAgo, truncate, cn } from "@/lib/utils";
import type { Task } from "@/lib/api";

const STATUS_SECTIONS = [
  { key: "todo", label: "Offen", dotColor: "bg-zinc-400" },
  { key: "in_progress", label: "In Arbeit", dotColor: "bg-blue-400" },
  { key: "done", label: "Erledigt", dotColor: "bg-green-400" },
  { key: "cancelled", label: "Abgebrochen", dotColor: "bg-red-400" },
];

const PRIORITY_DOT: Record<number, string> = {
  1: "bg-red-400",
  2: "bg-orange-400",
  3: "bg-yellow-400",
  4: "bg-blue-400",
  5: "bg-zinc-500",
};

function TaskCard({ task }: { task: Task }) {
  const isOverdue =
    task.due_date &&
    task.status !== "done" &&
    task.status !== "cancelled" &&
    new Date(task.due_date) < new Date();

  const catColor = task.category ? (CATEGORY_COLORS[task.category] ?? CATEGORY_COLORS.default) : null;

  return (
    <div
      className={cn(
        "flex items-start gap-3 py-3 px-4 border-b border-zinc-800/60 last:border-0",
        task.status === "done" && "opacity-50",
        isOverdue && "bg-red-950/20"
      )}
    >
      {/* Priority dot */}
      <div className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", PRIORITY_DOT[task.priority] ?? "bg-zinc-600")} title={PRIORITY_LABEL[task.priority]} />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-2 flex-wrap">
          <span className={cn("text-sm", task.status === "done" ? "text-zinc-500 line-through" : isOverdue ? "text-red-300" : "text-white")}>
            {task.title}
          </span>
          {catColor && task.category && task.category !== "general" && (
            <span
              className="text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0"
              style={{
                color: catColor.hex,
                backgroundColor: catColor.hex + "20",
                border: `1px solid ${catColor.hex}40`,
              }}
            >
              {task.category}
            </span>
          )}
        </div>
        {task.description && (
          <p className="text-zinc-500 text-xs mt-0.5">{truncate(task.description, 100)}</p>
        )}
        <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
          {task.due_date && (
            <span className={cn(isOverdue && "text-red-400 font-medium")}>
              {isOverdue ? "⚠️ " : "📅 "}
              {formatDate(task.due_date)}
            </span>
          )}
          {task.completed_at && (
            <span className="text-green-500">✓ {formatTimeAgo(task.completed_at)}</span>
          )}
        </div>
      </div>

      {/* Priority label */}
      <span className="text-xs text-zinc-600 shrink-0 font-mono">P{task.priority}</span>
    </div>
  );
}

function KanbanSection({ section, tasks }: { section: typeof STATUS_SECTIONS[0]; tasks: Task[] }) {
  const [collapsed, setCollapsed] = useState(section.key === "cancelled");
  if (tasks.length === 0) return null;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 border-b border-zinc-800 hover:bg-zinc-800/40 transition-colors"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className={cn("w-2.5 h-2.5 rounded-full", section.dotColor)} />
        <span className="text-white font-medium text-sm flex-1 text-left">{section.label}</span>
        <span className="text-zinc-500 text-xs bg-zinc-800 px-2 py-0.5 rounded-full">{tasks.length}</span>
        <span className="text-zinc-500 text-xs">{collapsed ? "▶" : "▼"}</span>
      </button>
      {!collapsed && (
        <div>
          {tasks.map((task) => <TaskCard key={task.id} task={task} />)}
        </div>
      )}
    </div>
  );
}

export default function TasksPage() {
  const { data, error, isLoading } = useAllTasks();
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  let tasks = data?.tasks ?? [];

  if (priorityFilter !== null) tasks = tasks.filter((t) => t.priority === priorityFilter);
  if (categoryFilter) tasks = tasks.filter((t) => t.category === categoryFilter);
  if (search.trim()) {
    const q = search.toLowerCase();
    tasks = tasks.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        (t.description?.toLowerCase().includes(q) ?? false)
    );
  }

  const all = data?.tasks ?? [];
  const counts = {
    todo: all.filter((t) => t.status === "todo").length,
    in_progress: all.filter((t) => t.status === "in_progress").length,
    done: all.filter((t) => t.status === "done").length,
    cancelled: all.filter((t) => t.status === "cancelled").length,
  };

  const categories = Array.from(new Set(all.map((t) => t.category).filter(Boolean))).sort() as string[];

  return (
    <div>
      <Header
        title="✅ Tasks"
        subtitle={`${counts.todo} offen · ${counts.in_progress} in Arbeit · ${counts.done} erledigt`}
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 mb-6">
        {/* Priority */}
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-zinc-500 text-xs">Priorität:</span>
          {[null, 1, 2, 3, 4, 5].map((p) => (
            <button
              key={p ?? "all"}
              onClick={() => setPriorityFilter(p)}
              className={cn(
                "px-2.5 py-1 rounded text-xs transition-colors",
                priorityFilter === p ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white"
              )}
            >
              {p === null ? "Alle" : `P${p}`}
            </button>
          ))}
        </div>

        {/* Category + Search */}
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-zinc-500 text-xs">Kategorie:</span>
          <button
            onClick={() => setCategoryFilter("")}
            className={cn("px-2.5 py-1 rounded text-xs transition-colors", !categoryFilter ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white")}
          >
            Alle
          </button>
          {categories.map((cat) => {
            const catColor = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.default;
            return (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={cn("px-2.5 py-1 rounded text-xs transition-colors border")}
                style={
                  categoryFilter === cat
                    ? { color: catColor.hex, backgroundColor: catColor.hex + "20", borderColor: catColor.hex + "60" }
                    : { color: "#71717a", backgroundColor: "transparent", borderColor: "#3f3f46" }
                }
              >
                {cat}
              </button>
            );
          })}
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Suchen..."
            className="flex-1 min-w-32 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
      </div>

      {/* Kanban Sections */}
      {tasks.length === 0 ? (
        <EmptyState emoji="✅" message="Keine Tasks gefunden" />
      ) : (
        <div className="space-y-4">
          {STATUS_SECTIONS.map((section) => (
            <KanbanSection
              key={section.key}
              section={section}
              tasks={tasks.filter((t) => t.status === section.key)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
