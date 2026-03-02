"use client";

import { useState, useMemo, useCallback } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useAllTasks, useObjectives } from "@/hooks/useApi";
import { CATEGORY_COLORS, PRIORITY_LABEL, formatDate, formatTimeAgo, truncate, cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Task } from "@/lib/api";
import { Pencil, Trash2 } from "lucide-react";

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

const OBJECTIVE_COLORS = [
  "#3b82f6", "#8b5cf6", "#f59e0b", "#10b981", "#ef4444",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#6366f1",
];

const TASK_STATUSES = ["todo", "in_progress", "done", "cancelled"];
const TASK_CATEGORIES = ["general", "health", "fitness", "business", "personal", "finance", "learning", "relationships", "shopping"];

// ─── Edit Modal ───────────────────────────────────────────────────────────────

function EditTaskModal({
  task,
  objectives,
  onSave,
  onClose,
  saving,
}: {
  task: Task;
  objectives: { id: number; title: string }[];
  onSave: (data: {
    title: string;
    category: string | null;
    priority: number;
    due_date: string | null;
    status: string;
    objective_id: number | null;
  }) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    title: task.title,
    category: task.category ?? "general",
    priority: task.priority,
    due_date: task.due_date ?? "",
    status: task.status,
    objective_id: task.objective_id ?? 0,
  });

  function handleSave() {
    onSave({
      title: form.title.trim(),
      category: form.category || null,
      priority: form.priority,
      due_date: form.due_date || null,
      status: form.status,
      objective_id: form.objective_id > 0 ? form.objective_id : null,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <h3 className="text-white font-semibold text-lg mb-5">Task bearbeiten</h3>

        <div className="space-y-4">
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Titel</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Kategorie</label>
              <select
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                {TASK_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Priorität</label>
              <select
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: Number(e.target.value) }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value={1}>P1 – Höchste</option>
                <option value={2}>P2 – Hoch</option>
                <option value={3}>P3 – Mittel</option>
                <option value={4}>P4 – Niedrig</option>
                <option value={5}>P5 – Niedrigste</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Status</label>
              <select
                value={form.status}
                onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                {TASK_STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Fällig am</label>
              <input
                type="date"
                value={form.due_date}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {objectives.length > 0 && (
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Objective</label>
              <select
                value={form.objective_id}
                onChange={(e) => setForm((f) => ({ ...f, objective_id: Number(e.target.value) }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value={0}>— kein Objective —</option>
                {objectives.map((o) => (
                  <option key={o.id} value={o.id}>{o.title}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end mt-6">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !form.title.trim()}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium"
          >
            {saving ? "Speichern…" : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Task Card ────────────────────────────────────────────────────────────────

function TaskCard({
  task,
  indent = 0,
  taskMap,
  onEdit,
  onDelete,
}: {
  task: Task;
  indent?: number;
  taskMap: Map<number, Task>;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
}) {
  const isOverdue =
    task.due_date &&
    task.status !== "done" &&
    task.status !== "cancelled" &&
    new Date(task.due_date) < new Date();

  const catColor = task.category ? (CATEGORY_COLORS[task.category] ?? CATEGORY_COLORS.default) : null;
  const blocker = task.blocked_by_task_id ? taskMap.get(task.blocked_by_task_id) : null;
  const isBlocked = blocker != null && blocker.status !== "done" && blocker.status !== "cancelled";

  return (
    <div
      className={cn(
        "flex items-start gap-3 py-3 px-4 border-b border-zinc-800/60 last:border-0 group",
        task.status === "done" && "opacity-50",
        isOverdue && "bg-red-950/20",
        isBlocked && "opacity-40",
        indent > 0 && "pl-10 border-l-2 border-zinc-700/30 ml-4",
      )}
    >
      <div
        className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", PRIORITY_DOT[task.priority] ?? "bg-zinc-600")}
        title={PRIORITY_LABEL[task.priority]}
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-2 flex-wrap">
          <span
            className={cn(
              "text-sm",
              task.status === "done"
                ? "text-zinc-500 line-through"
                : isOverdue
                ? "text-red-300"
                : isBlocked
                ? "text-zinc-500"
                : "text-white",
            )}
          >
            {task.title}
          </span>

          {task.objective_title && (
            <span className="text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 bg-purple-900/40 text-purple-300 border border-purple-700/40">
              🎯 {task.objective_title}
            </span>
          )}

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

          {isBlocked && blocker && (
            <span className="text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 bg-red-900/30 text-red-400 border border-red-800/40">
              🔒 wartet auf: {truncate(blocker.title, 30)}
            </span>
          )}

          {task.parent_task_id && (
            <span className="text-xs text-zinc-600 shrink-0">↳ Sub-Task</span>
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

      <span className="text-xs text-zinc-600 shrink-0 font-mono">P{task.priority}</span>

      {/* Action buttons */}
      <div className="flex gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => { e.stopPropagation(); onEdit(task); }}
          className="text-zinc-500 hover:text-blue-400 transition-colors p-1 rounded"
          title="Bearbeiten"
        >
          <Pencil size={13} />
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(task); }}
          className="text-zinc-500 hover:text-red-400 transition-colors p-1 rounded"
          title="Löschen"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}

// ─── Kanban Section ───────────────────────────────────────────────────────────

function KanbanSection({
  section,
  tasks,
  taskMap,
  onEdit,
  onDelete,
}: {
  section: (typeof STATUS_SECTIONS)[0];
  tasks: Task[];
  taskMap: Map<number, Task>;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
}) {
  const [collapsed, setCollapsed] = useState(section.key === "cancelled");

  const topLevel = tasks.filter((t) => !t.parent_task_id || !tasks.find((p) => p.id === t.parent_task_id));
  const subTaskMap = tasks.reduce<Record<number, Task[]>>((acc, t) => {
    if (t.parent_task_id && tasks.find((p) => p.id === t.parent_task_id)) {
      (acc[t.parent_task_id] ??= []).push(t);
    }
    return acc;
  }, {});

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
          {topLevel.map((task) => (
            <div key={task.id}>
              <TaskCard task={task} taskMap={taskMap} onEdit={onEdit} onDelete={onDelete} />
              {(subTaskMap[task.id] ?? []).map((sub) => (
                <TaskCard key={sub.id} task={sub} indent={1} taskMap={taskMap} onEdit={onEdit} onDelete={onDelete} />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function TasksPage() {
  const { data, error, isLoading, mutate } = useAllTasks();
  const { data: objData } = useObjectives();
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [objectiveFilter, setObjectiveFilter] = useState<string>("");
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [deletingTask, setDeletingTask] = useState<Task | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const { toasts, addToast, dismissToast } = useToast();

  const objectives = useMemo(
    () => (objData?.objectives ?? []).map((o) => ({ id: o.id, title: o.title })),
    [objData]
  );

  const handleEdit = useCallback(
    async (data: {
      title: string;
      category: string | null;
      priority: number;
      due_date: string | null;
      status: string;
      objective_id: number | null;
    }) => {
      if (!editingTask) return;
      setSaving(true);
      try {
        await api.updateTask(editingTask.id, data);
        await mutate();
        addToast("Task aktualisiert", "success");
        setEditingTask(null);
      } catch {
        addToast("Fehler beim Speichern", "error");
      } finally {
        setSaving(false);
      }
    },
    [editingTask, mutate, addToast]
  );

  const handleDelete = useCallback(async () => {
    if (!deletingTask) return;
    setDeleting(true);
    mutate(
      (prev) =>
        prev ? { tasks: prev.tasks.filter((t) => t.id !== deletingTask.id) } : prev,
      false
    );
    try {
      await api.deleteTask(deletingTask.id);
      addToast("Task gelöscht", "success");
      setDeletingTask(null);
    } catch {
      await mutate();
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
    }
  }, [deletingTask, mutate, addToast]);

  const all = data?.tasks ?? [];
  const taskMap = useMemo(() => new Map(all.map((t) => [t.id, t])), [all]);

  const objectiveOptions = useMemo(
    () =>
      Array.from(
        new Map(
          all
            .filter((t) => t.objective_title)
            .map((t) => [t.objective_title!, t.objective_title!]),
        ).values(),
      ).sort(),
    [all]
  );

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  let tasks = all;
  if (priorityFilter !== null) tasks = tasks.filter((t) => t.priority === priorityFilter);
  if (categoryFilter) tasks = tasks.filter((t) => t.category === categoryFilter);
  if (objectiveFilter) tasks = tasks.filter((t) => t.objective_title === objectiveFilter);
  if (search.trim()) {
    const q = search.toLowerCase();
    tasks = tasks.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        (t.description?.toLowerCase().includes(q) ?? false) ||
        (t.objective_title?.toLowerCase().includes(q) ?? false),
    );
  }

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
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-zinc-500 text-xs">Priorität:</span>
          {[null, 1, 2, 3, 4, 5].map((p) => (
            <button
              key={p ?? "all"}
              onClick={() => setPriorityFilter(p)}
              className={cn(
                "px-2.5 py-1 rounded text-xs transition-colors",
                priorityFilter === p ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white",
              )}
            >
              {p === null ? "Alle" : `P${p}`}
            </button>
          ))}
        </div>

        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-zinc-500 text-xs">Kategorie:</span>
          <button
            onClick={() => setCategoryFilter("")}
            className={cn(
              "px-2.5 py-1 rounded text-xs transition-colors",
              !categoryFilter ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white",
            )}
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
        </div>

        {objectiveOptions.length > 0 && (
          <div className="flex gap-2 flex-wrap items-center">
            <span className="text-zinc-500 text-xs">Objective:</span>
            <button
              onClick={() => setObjectiveFilter("")}
              className={cn(
                "px-2.5 py-1 rounded text-xs transition-colors",
                !objectiveFilter ? "bg-purple-700 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white",
              )}
            >
              Alle
            </button>
            {objectiveOptions.map((obj, i) => (
              <button
                key={obj}
                onClick={() => setObjectiveFilter(obj)}
                className={cn("px-2.5 py-1 rounded text-xs transition-colors border")}
                style={
                  objectiveFilter === obj
                    ? {
                        color: OBJECTIVE_COLORS[i % OBJECTIVE_COLORS.length],
                        backgroundColor: OBJECTIVE_COLORS[i % OBJECTIVE_COLORS.length] + "20",
                        borderColor: OBJECTIVE_COLORS[i % OBJECTIVE_COLORS.length] + "60",
                      }
                    : { color: "#71717a", backgroundColor: "transparent", borderColor: "#3f3f46" }
                }
              >
                🎯 {obj}
              </button>
            ))}
          </div>
        )}

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Tasks suchen..."
          className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
        />
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
              taskMap={taskMap}
              onEdit={setEditingTask}
              onDelete={setDeletingTask}
            />
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editingTask && (
        <EditTaskModal
          task={editingTask}
          objectives={objectives}
          onSave={handleEdit}
          onClose={() => setEditingTask(null)}
          saving={saving}
        />
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deletingTask}
        title="Task löschen?"
        message={`"${deletingTask?.title}" wird dauerhaft gelöscht.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingTask(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
