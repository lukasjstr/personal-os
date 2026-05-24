"use client";

import { useCallback, useEffect, useState } from "react";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import { cn } from "@/lib/utils";

// ─── API helpers ─────────────────────────────────────────────────────────────

const API_URL = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";
function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("api_token");
}
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ─── Types ────────────────────────────────────────────────────────────────────

type Task = {
  id: number;
  title: string;
  status: string;
  priority: number;
  category: string;
  due_date?: string | null;
  completed_at?: string | null;
  objective_id?: number | null;
  key_result_id?: number | null;
  parent_task_id?: number | null;
  blocked_by_task_id?: number | null;
};

type Objective = {
  id: number;
  title: string;
  category: string;
};

// ─── Constants ────────────────────────────────────────────────────────────────

type ColumnKey = "inbox" | "calendar" | "doing" | "projects" | "done" | "archive";

const COLUMNS: Array<{
  key: ColumnKey;
  emoji: string;
  label: string;
  accent: string;
  dropBg: string;
}> = [
  { key: "inbox",    emoji: "🛒", label: "Inbox",           accent: "border-zinc-800", dropBg: "border-zinc-500 bg-zinc-800/40" },
  { key: "calendar", emoji: "📅", label: "Kalender",        accent: "border-purple-900/40", dropBg: "border-purple-500 bg-purple-950/30" },
  { key: "doing",    emoji: "⚡", label: "Doing",           accent: "border-blue-900/40", dropBg: "border-blue-500 bg-blue-950/30" },
  { key: "projects", emoji: "📂", label: "Projekte/Waiting", accent: "border-amber-900/40", dropBg: "border-amber-500 bg-amber-950/30" },
  { key: "done",     emoji: "✅", label: "Done (7d)",       accent: "border-green-900/40", dropBg: "border-green-500 bg-green-950/30" },
  { key: "archive",  emoji: "📦", label: "Archiv",          accent: "border-zinc-900", dropBg: "border-zinc-700 bg-zinc-900/50" },
];

const PRIORITY_DOT: Record<number, string> = {
  1: "bg-red-500",
  2: "bg-orange-500",
  3: "bg-yellow-500",
  4: "bg-blue-500",
  5: "bg-zinc-500",
};

const CATEGORY_LABEL: Record<string, string> = {
  health: "Health", fitness: "Fitness", business: "Business", personal: "Personal",
  finance: "Finance", learning: "Learning", relationships: "Beziehungen",
  general: "", work: "Work", errand: "Errand", shopping: "Shopping",
};

// ─── Column classification ────────────────────────────────────────────────────

function classify(t: Task, today: string): ColumnKey | null {
  if (t.status === "cancelled") return "archive";
  if (t.status === "done") {
    if (!t.completed_at) return "done";
    const completed = t.completed_at.slice(0, 10);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 7);
    return completed >= cutoff.toISOString().slice(0, 10) ? "done" : "archive";
  }
  if (t.status === "in_progress") return "doing";
  if (t.status === "todo") {
    if (t.parent_task_id || t.blocked_by_task_id) return "projects";
    if (t.due_date) return "calendar";
    return "inbox";
  }
  return null;
}

// Map Column → DB field changes when dropped here
function fieldsForColumn(col: ColumnKey, dueDate?: string): Record<string, unknown> {
  switch (col) {
    case "inbox":    return { status: "todo", due_date: null };
    case "calendar": return { status: "todo", due_date: dueDate || new Date().toISOString().slice(0, 10) };
    case "doing":    return { status: "in_progress" };
    case "projects": return { status: "todo" }; // user sets parent/blocker via modal
    case "done":     return { status: "done" };
    case "archive":  return { status: "cancelled" };
  }
}

// ─── Task Card ────────────────────────────────────────────────────────────────

function TaskCard({
  task,
  objectives,
  onDragStart,
  onClick,
}: {
  task: Task;
  objectives: Objective[];
  onDragStart: (e: React.DragEvent, task: Task) => void;
  onClick: (task: Task) => void;
}) {
  const obj = objectives.find((o) => o.id === task.objective_id);
  const dot = PRIORITY_DOT[task.priority] || "bg-zinc-500";
  const catLabel = CATEGORY_LABEL[task.category];
  const today = new Date().toISOString().slice(0, 10);
  const isOverdue = task.due_date && task.due_date < today && task.status !== "done";
  const isDueToday = task.due_date === today;

  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, task)}
      onClick={() => onClick(task)}
      className={cn(
        "group bg-zinc-900 border border-zinc-800 rounded-xl p-3 cursor-grab active:cursor-grabbing",
        "hover:border-zinc-700 transition-colors select-none",
        task.status === "done" && "opacity-60",
      )}
    >
      <div className="flex items-start gap-2">
        <span className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", dot)} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-zinc-100 leading-snug">{task.title}</div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-zinc-500 flex-wrap">
            {obj && <span className="truncate">{obj.title}</span>}
            {catLabel && <span className="text-zinc-600">· {catLabel}</span>}
            {task.due_date && (
              <span className={cn(
                "shrink-0",
                isOverdue ? "text-red-400" : isDueToday ? "text-amber-400" : "text-zinc-500",
              )}>
                {isOverdue ? "⚠ " : ""}fällig {task.due_date}
              </span>
            )}
            {task.blocked_by_task_id && <span className="text-amber-500">🔒 #{task.blocked_by_task_id}</span>}
            {task.parent_task_id && <span className="text-zinc-500">↳ #{task.parent_task_id}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Add / Edit Task Modal ────────────────────────────────────────────────────

function TaskModal({
  task,
  defaultColumn,
  objectives,
  onClose,
  onSaved,
}: {
  task: Task | null;
  defaultColumn: ColumnKey | null;
  objectives: Objective[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = task === null;
  const [title, setTitle] = useState(task?.title || "");
  const [priority, setPriority] = useState<number>(task?.priority || 3);
  const [objectiveId, setObjectiveId] = useState<number | "">(task?.objective_id ?? "");
  const [category, setCategory] = useState(task?.category || "general");
  const [dueDate, setDueDate] = useState<string>(task?.due_date || "");
  const [blockedBy, setBlockedBy] = useState<string>(task?.blocked_by_task_id?.toString() || "");
  const [parentId, setParentId] = useState<string>(task?.parent_task_id?.toString() || "");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        title: title.trim(),
        priority,
        category,
        due_date: dueDate || null,
        objective_id: objectiveId === "" ? null : Number(objectiveId),
        blocked_by_task_id: blockedBy ? Number(blockedBy) : null,
        parent_task_id: parentId ? Number(parentId) : null,
      };
      // status from default column on create
      if (isNew && defaultColumn) {
        Object.assign(body, fieldsForColumn(defaultColumn, dueDate));
      }
      if (isNew) {
        await apiFetch("/api/tasks", { method: "POST", body: JSON.stringify(body) });
      } else {
        await apiFetch(`/api/tasks/${task!.id}`, { method: "PUT", body: JSON.stringify(body) });
      }
      onSaved();
      onClose();
    } catch {
      // ignore — alert handled upstream
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!task) return;
    if (!confirm(`Task '${task.title}' streichen?`)) return;
    setSaving(true);
    try {
      await apiFetch(`/api/tasks/${task.id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "cancelled" }),
      });
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 w-full max-w-md space-y-3"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-white font-semibold">{isNew ? "Neuer Task" : `Task #${task!.id}`}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white">✕</button>
        </div>

        <div>
          <label className="text-[11px] text-zinc-500 block mb-1">Titel</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] text-zinc-500 block mb-1">Priorität</label>
            <select
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
              className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
            >
              {[1, 2, 3, 4, 5].map((p) => <option key={p} value={p}>P{p}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[11px] text-zinc-500 block mb-1">Kategorie</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
            >
              {["general", "personal", "work", "errand", "fitness", "learning", "shopping"].map((c) =>
                <option key={c} value={c}>{c}</option>
              )}
            </select>
          </div>
        </div>

        <div>
          <label className="text-[11px] text-zinc-500 block mb-1">Objective</label>
          <select
            value={String(objectiveId)}
            onChange={(e) => setObjectiveId(e.target.value === "" ? "" : Number(e.target.value))}
            className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
          >
            <option value="">— Kein Objective —</option>
            {objectives.map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] text-zinc-500 block mb-1">Fällig am</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
            />
          </div>
          <div>
            <label className="text-[11px] text-zinc-500 block mb-1">Wartet auf Task #</label>
            <input
              type="number"
              value={blockedBy}
              onChange={(e) => setBlockedBy(e.target.value)}
              placeholder="(optional)"
              className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
            />
          </div>
        </div>

        <div>
          <label className="text-[11px] text-zinc-500 block mb-1">Parent-Task # (Sub-Task)</label>
          <input
            type="number"
            value={parentId}
            onChange={(e) => setParentId(e.target.value)}
            placeholder="(optional)"
            className="w-full bg-black border border-zinc-800 text-zinc-200 text-sm rounded-lg p-2 outline-none focus:border-indigo-600"
          />
        </div>

        <div className="flex gap-2 pt-2">
          <button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-semibold"
          >
            {saving ? "…" : isNew ? "Erstellen" : "Speichern"}
          </button>
          {!isNew && (
            <button
              onClick={handleDelete}
              disabled={saving}
              className="bg-zinc-800 hover:bg-red-900/40 hover:text-red-300 text-zinc-400 rounded-lg px-3 py-2 text-sm"
            >
              Cut
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function KanbanPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<Task | null>(null);
  const [dragOver, setDragOver] = useState<ColumnKey | null>(null);
  const [openTask, setOpenTask] = useState<Task | null>(null);
  const [addForColumn, setAddForColumn] = useState<ColumnKey | null>(null);
  const [filterObjective, setFilterObjective] = useState<number | "all">("all");
  const [filterPriority, setFilterPriority] = useState<number | "all">("all");
  const [includeShopping, setIncludeShopping] = useState(false);

  const today = new Date().toISOString().slice(0, 10);

  const load = useCallback(async () => {
    try {
      const [tasksRes, objRes] = await Promise.all([
        apiFetch<{ tasks: Task[] }>("/api/tasks?limit=300&include_cancelled=true"),
        apiFetch<{ objectives: Objective[] }>("/api/objectives"),
      ]);
      let arr = tasksRes.tasks || [];
      if (!includeShopping) arr = arr.filter((t) => t.category !== "shopping");
      setTasks(arr);
      setObjectives((objRes.objectives || []).filter((o) => o.category !== "shopping"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [includeShopping]);

  useEffect(() => { load(); }, [load]);

  const handleDragStart = (e: React.DragEvent, task: Task) => {
    setDragging(task);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = async (e: React.DragEvent, col: ColumnKey) => {
    e.preventDefault();
    setDragOver(null);
    if (!dragging) return;
    const currentCol = classify(dragging, today);
    if (currentCol === col) { setDragging(null); return; }

    // Calendar drop → prompt for due date
    let dueOverride: string | undefined;
    if (col === "calendar") {
      const input = prompt("Fällig am (YYYY-MM-DD):", today);
      if (!input) { setDragging(null); return; }
      dueOverride = input;
    }
    // Archive confirmation
    if (col === "archive") {
      if (!confirm(`'${dragging.title}' archivieren (cancellen)?`)) { setDragging(null); return; }
    }

    const taskId = dragging.id;
    const updates = fieldsForColumn(col, dueOverride);
    setTasks((prev) => prev.map((t) => t.id === taskId ? { ...t, ...updates } as Task : t));
    setDragging(null);
    try {
      await apiFetch(`/api/tasks/${taskId}`, { method: "PUT", body: JSON.stringify(updates) });
    } catch {
      await load();
    }
  };

  // Filters + grouping
  const filtered = tasks.filter((t) => {
    if (filterObjective !== "all" && t.objective_id !== filterObjective) return false;
    if (filterPriority !== "all" && t.priority !== filterPriority) return false;
    return true;
  });

  const byColumn: Record<ColumnKey, Task[]> = {
    inbox: [], calendar: [], doing: [], projects: [], done: [], archive: [],
  };
  for (const t of filtered) {
    const c = classify(t, today);
    if (c) byColumn[c].push(t);
  }
  // Sort each column
  for (const k of Object.keys(byColumn) as ColumnKey[]) {
    byColumn[k].sort((a, b) => {
      if (k === "calendar") {
        return (a.due_date || "9999").localeCompare(b.due_date || "9999");
      }
      if (k === "done" || k === "archive") {
        return (b.completed_at || "").localeCompare(a.completed_at || "");
      }
      return a.priority - b.priority;
    });
  }
  // Limit done + archive to 20 visible
  byColumn.done = byColumn.done.slice(0, 20);
  byColumn.archive = byColumn.archive.slice(0, 30);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white">🗂 Kanban</h1>
          <p className="text-zinc-500 text-xs mt-0.5">
            {byColumn.inbox.length} inbox · {byColumn.calendar.length} kalender · {byColumn.doing.length} doing · {byColumn.projects.length} projekte
          </p>
        </div>
        <button onClick={load} className="text-zinc-500 hover:text-zinc-300 text-xs flex items-center gap-1">
          ↺ Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap items-center">
        <select
          value={filterObjective === "all" ? "all" : String(filterObjective)}
          onChange={(e) => setFilterObjective(e.target.value === "all" ? "all" : Number(e.target.value))}
          className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-3 py-1.5"
        >
          <option value="all">Alle Ziele</option>
          {objectives.map((o) => (<option key={o.id} value={o.id}>{o.title}</option>))}
        </select>
        <div className="flex gap-1">
          {(["all", 1, 2, 3, 4, 5] as const).map((p) => (
            <button
              key={String(p)}
              onClick={() => setFilterPriority(p)}
              className={cn(
                "px-2 py-1 rounded text-[10px] border transition-colors",
                filterPriority === p
                  ? "bg-zinc-700 border-zinc-600 text-white"
                  : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300",
              )}
            >
              {p === "all" ? "Alle" : `P${p}`}
            </button>
          ))}
        </div>
        <label className="text-xs text-zinc-500 flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={includeShopping}
            onChange={(e) => setIncludeShopping(e.target.checked)}
            className="accent-indigo-600"
          />
          Shopping zeigen
        </label>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 flex-1">
        {COLUMNS.map((col) => {
          const items = byColumn[col.key];
          const isDrag = dragOver === col.key;
          return (
            <div
              key={col.key}
              className={cn(
                "flex flex-col rounded-2xl border bg-zinc-950 min-h-[140px]",
                isDrag ? col.dropBg : col.accent,
              )}
              onDragOver={(e) => { e.preventDefault(); setDragOver(col.key); }}
              onDragLeave={() => setDragOver(null)}
              onDrop={(e) => handleDrop(e, col.key)}
            >
              <div className="flex items-center justify-between px-3 py-2.5 border-b border-zinc-900">
                <div className="flex items-center gap-1.5">
                  <span>{col.emoji}</span>
                  <h3 className="text-xs font-semibold text-zinc-200">{col.label}</h3>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-zinc-500 bg-zinc-900/60 px-1.5 py-0.5 rounded font-medium">
                    {items.length}
                  </span>
                  {col.key !== "done" && col.key !== "archive" && (
                    <button
                      onClick={() => setAddForColumn(col.key)}
                      className="w-5 h-5 flex items-center justify-center text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 rounded text-sm"
                      title="Neue Task"
                    >+</button>
                  )}
                </div>
              </div>

              <div className="flex-1 p-2 space-y-1.5 overflow-y-auto">
                {items.length === 0 ? (
                  <div className={cn(
                    "flex items-center justify-center h-16 rounded-lg border border-dashed text-[11px]",
                    isDrag ? "border-indigo-500/60 text-indigo-300" : "border-zinc-900 text-zinc-700",
                  )}>
                    {isDrag ? "Hier ablegen" : "leer"}
                  </div>
                ) : (
                  items.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      objectives={objectives}
                      onDragStart={handleDragStart}
                      onClick={setOpenTask}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal */}
      {(openTask || addForColumn) && (
        <TaskModal
          task={openTask}
          defaultColumn={addForColumn}
          objectives={objectives}
          onClose={() => { setOpenTask(null); setAddForColumn(null); }}
          onSaved={load}
        />
      )}
    </div>
  );
}
