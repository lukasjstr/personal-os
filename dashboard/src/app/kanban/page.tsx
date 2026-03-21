"use client";

import { useState, useCallback, useEffect } from "react";
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
  due_date?: string;
  objective_id?: number;
  key_result_id?: number;
};

type Objective = {
  id: number;
  title: string;
  category: string;
};

// ─── Constants ────────────────────────────────────────────────────────────────

const COLUMNS = [
  {
    key: "todo",
    label: "Todo",
    icon: "○",
    accent: "border-zinc-700",
    headerBg: "bg-zinc-800/60",
    dropBg: "bg-zinc-800/20 border-zinc-500",
  },
  {
    key: "in_progress",
    label: "In Arbeit",
    icon: "◑",
    accent: "border-blue-800/60",
    headerBg: "bg-blue-950/40",
    dropBg: "bg-blue-950/30 border-blue-500",
  },
  {
    key: "done",
    label: "Erledigt",
    icon: "●",
    accent: "border-green-800/60",
    headerBg: "bg-green-950/30",
    dropBg: "bg-green-950/20 border-green-500",
  },
] as const;

const PRIORITY_CONFIG: Record<number, { label: string; dot: string; text: string; bg: string }> = {
  1: { label: "P1", dot: "bg-red-500",    text: "text-red-400",    bg: "bg-red-900/30 border-red-800/40" },
  2: { label: "P2", dot: "bg-orange-500", text: "text-orange-400", bg: "bg-orange-900/30 border-orange-800/40" },
  3: { label: "P3", dot: "bg-yellow-500", text: "text-yellow-400", bg: "bg-yellow-900/30 border-yellow-800/40" },
  4: { label: "P4", dot: "bg-blue-500",   text: "text-blue-400",   bg: "bg-blue-900/30 border-blue-800/40" },
  5: { label: "P5", dot: "bg-zinc-500",   text: "text-zinc-500",   bg: "bg-zinc-800/40 border-zinc-700/40" },
};

const CATEGORY_EMOJI: Record<string, string> = {
  health: "❤️", fitness: "💪", business: "💼", personal: "👤",
  finance: "💶", learning: "📚", relationships: "👥", general: "📌",
};

// ─── Task Card ────────────────────────────────────────────────────────────────

function TaskCard({
  task,
  objectives,
  onDragStart,
  onComplete,
  onMoveNext,
  completing,
}: {
  task: Task;
  objectives: Objective[];
  onDragStart: (e: React.DragEvent, task: Task) => void;
  onComplete: (id: number) => void;
  onMoveNext: (task: Task) => void;
  completing: number | null;
}) {
  const obj = objectives.find((o) => o.id === task.objective_id);
  const p = PRIORITY_CONFIG[task.priority] ?? PRIORITY_CONFIG[3];
  const today = new Date().toISOString().split("T")[0];
  const isOverdue = task.due_date && task.due_date < today && task.status !== "done";
  const isDueToday = task.due_date && task.due_date === today;

  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, task)}
      className={cn(
        "group relative bg-zinc-900 border rounded-xl p-3.5 cursor-grab active:cursor-grabbing",
        "hover:border-zinc-600 transition-all select-none",
        task.status === "done" ? "border-zinc-800 opacity-60" : "border-zinc-800"
      )}
    >
      {/* Priority dot + title row */}
      <div className="flex items-start gap-2.5">
        <div className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", p.dot)} />
        <p className={cn("text-sm font-medium leading-snug flex-1",
          task.status === "done" ? "text-zinc-500 line-through" : "text-white"
        )}>
          {task.title}
        </p>
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-2 mt-2.5 flex-wrap">
        {/* Priority badge */}
        <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded border", p.bg, p.text)}>
          {p.label}
        </span>

        {/* Category emoji */}
        {task.category && task.category !== "general" && task.category !== "shopping" && (
          <span className="text-xs">{CATEGORY_EMOJI[task.category] ?? "📌"}</span>
        )}

        {/* Objective */}
        {obj && (
          <span className="text-[10px] text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded truncate max-w-[110px]">
            {obj.title}
          </span>
        )}

        {/* Due date */}
        {task.due_date && (
          <span className={cn(
            "text-[10px] font-medium",
            isOverdue ? "text-red-400" : isDueToday ? "text-yellow-400" : "text-zinc-600"
          )}>
            {isOverdue ? "⚠️ " : isDueToday ? "📅 " : ""}
            {new Date(task.due_date + "T00:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "short" })}
          </span>
        )}
      </div>

      {/* Action buttons — visible on hover */}
      {task.status !== "done" && (
        <div className="absolute top-2.5 right-2.5 hidden group-hover:flex items-center gap-1">
          {task.status === "todo" && (
            <button
              onClick={(e) => { e.stopPropagation(); onMoveNext(task); }}
              title="In Arbeit verschieben"
              className="w-6 h-6 rounded-full bg-blue-900/60 hover:bg-blue-700/80 text-blue-300 text-xs flex items-center justify-center transition-colors"
            >
              →
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onComplete(task.id); }}
            disabled={completing === task.id}
            title="Als erledigt markieren"
            className="w-6 h-6 rounded-full bg-green-900/60 hover:bg-green-700/80 text-green-300 text-xs flex items-center justify-center transition-colors disabled:opacity-50"
          >
            {completing === task.id ? "…" : "✓"}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Add Task Modal ───────────────────────────────────────────────────────────

function AddTaskModal({
  defaultStatus,
  objectives,
  onClose,
  onSave,
}: {
  defaultStatus: string;
  objectives: Objective[];
  onClose: () => void;
  onSave: () => void;
}) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState(3);
  const [objectiveId, setObjectiveId] = useState<number | "">("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          priority,
          status: defaultStatus,
          objective_id: objectiveId || undefined,
        }),
      });
      onSave();
      onClose();
    } catch { /* ignore */ }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-md p-5 shadow-2xl">
        <h2 className="text-base font-bold text-white mb-4">Neuer Task</h2>

        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          placeholder="Was muss erledigt werden?"
          className="w-full bg-zinc-800 text-white rounded-xl px-3.5 py-3 text-sm outline-none border border-zinc-700 focus:border-blue-500 mb-3 placeholder:text-zinc-600"
        />

        {/* Priority */}
        <div className="mb-3">
          <div className="text-zinc-500 text-xs mb-2">Priorität</div>
          <div className="flex gap-1.5">
            {[1, 2, 3, 4, 5].map((p) => {
              const cfg = PRIORITY_CONFIG[p];
              return (
                <button
                  key={p}
                  onClick={() => setPriority(p)}
                  className={cn(
                    "flex-1 py-1.5 rounded-lg text-xs font-bold border transition-colors",
                    priority === p ? cn(cfg.bg, cfg.text) : "bg-zinc-800 border-zinc-700 text-zinc-500 hover:text-white"
                  )}
                >
                  {cfg.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Objective */}
        {objectives.length > 0 && (
          <div className="mb-4">
            <div className="text-zinc-500 text-xs mb-2">Verknüpftes Ziel (optional)</div>
            <select
              value={objectiveId}
              onChange={(e) => setObjectiveId(e.target.value ? Number(e.target.value) : "")}
              className="w-full bg-zinc-800 border border-zinc-700 text-zinc-200 text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:border-blue-500"
            >
              <option value="">Kein Ziel</option>
              {objectives.map((o) => (
                <option key={o.id} value={o.id}>{o.title}</option>
              ))}
            </select>
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-xl py-2.5 font-semibold text-sm transition-colors"
          >
            {saving ? "Erstelle…" : "Task erstellen"}
          </button>
          <button onClick={onClose} className="px-4 py-2.5 text-zinc-400 hover:text-white text-sm transition-colors">
            Abbrechen
          </button>
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
  const [addForStatus, setAddForStatus] = useState<string | null>(null);
  const [dragging, setDragging] = useState<Task | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [completing, setCompleting] = useState<number | null>(null);
  const [filterObjective, setFilterObjective] = useState<number | "all">("all");
  const [filterPriority, setFilterPriority] = useState<number | "all">("all");
  const [showDone, setShowDone] = useState(false);

  const load = useCallback(async () => {
    try {
      const [tasksRes, objRes] = await Promise.all([
        apiFetch<{ tasks: Task[] }>("/api/tasks?limit=200"),
        apiFetch<{ objectives: Objective[] }>("/api/objectives"),
      ]);
      // Exclude shopping tasks
      setTasks(tasksRes.tasks.filter((t) => t.category !== "shopping"));
      setObjectives(objRes.objectives.filter((o: Objective) => o.category !== "shopping"));
      setError(null);
    } catch {
      setError("Fehler beim Laden der Tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDragStart = (e: React.DragEvent, task: Task) => {
    setDragging(task);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = async (e: React.DragEvent, newStatus: string) => {
    e.preventDefault();
    setDragOver(null);
    if (!dragging || dragging.status === newStatus) { setDragging(null); return; }
    const taskId = dragging.id;
    setTasks((prev) => prev.map((t) => t.id === taskId ? { ...t, status: newStatus } : t));
    setDragging(null);
    try {
      await apiFetch(`/api/tasks/${taskId}`, {
        method: "PUT",
        body: JSON.stringify({ status: newStatus }),
      });
    } catch { await load(); }
  };

  const handleComplete = async (id: number) => {
    setCompleting(id);
    try {
      await apiFetch(`/api/tasks/${id}/complete`, { method: "POST" });
      setTasks((prev) => prev.map((t) => t.id === id ? { ...t, status: "done" } : t));
    } catch { /* ignore */ }
    finally { setCompleting(null); }
  };

  const handleMoveNext = async (task: Task) => {
    const newStatus = task.status === "todo" ? "in_progress" : "done";
    setTasks((prev) => prev.map((t) => t.id === task.id ? { ...t, status: newStatus } : t));
    try {
      await apiFetch(`/api/tasks/${task.id}`, {
        method: "PUT",
        body: JSON.stringify({ status: newStatus }),
      });
    } catch { await load(); }
  };

  // Apply filters
  const filteredTasks = tasks.filter((t) => {
    if (filterObjective !== "all" && t.objective_id !== filterObjective) return false;
    if (filterPriority !== "all" && t.priority !== filterPriority) return false;
    return true;
  });

  const getColumnTasks = (status: string) => {
    const col = filteredTasks.filter((t) => t.status === status)
      .sort((a, b) => a.priority - b.priority);
    if (status === "done") return showDone ? col : col.slice(0, 5);
    return col;
  };

  const todoCount = tasks.filter((t) => t.status === "todo").length;
  const inProgressCount = tasks.filter((t) => t.status === "in_progress").length;
  const doneCount = tasks.filter((t) => t.status === "done").length;

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            🗂 Kanban
          </h1>
          <p className="text-zinc-500 text-sm mt-0.5">
            {todoCount} offen · {inProgressCount} in Arbeit · {doneCount} erledigt
          </p>
        </div>
        <button
          onClick={load}
          className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors flex items-center gap-1.5"
        >
          <span className="text-base">↺</span> Refresh
        </button>
      </div>

      {/* ── Filters ────────────────────────────────────────────────────────── */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {/* Objective filter */}
        <select
          value={filterObjective === "all" ? "all" : String(filterObjective)}
          onChange={(e) => setFilterObjective(e.target.value === "all" ? "all" : Number(e.target.value))}
          className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-blue-500"
        >
          <option value="all">Alle Ziele</option>
          {objectives.map((o) => (
            <option key={o.id} value={o.id}>{o.title}</option>
          ))}
        </select>

        {/* Priority filter */}
        <div className="flex gap-1">
          {(["all", 1, 2, 3, 4, 5] as const).map((p) => {
            const cfg = typeof p === "number" ? PRIORITY_CONFIG[p] : null;
            return (
              <button
                key={String(p)}
                onClick={() => setFilterPriority(p)}
                className={cn(
                  "px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                  filterPriority === p
                    ? cfg ? cn(cfg.bg, cfg.text) : "bg-zinc-700 border-zinc-600 text-white"
                    : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                )}
              >
                {p === "all" ? "Alle" : `P${p}`}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Columns ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row gap-4 flex-1">
        {COLUMNS.map((col) => {
          const colTasks = getColumnTasks(col.key);
          const totalInCol = filteredTasks.filter((t) => t.status === col.key).length;
          const isDragTarget = dragOver === col.key;

          return (
            <div
              key={col.key}
              className={cn(
                "flex-1 flex flex-col rounded-2xl border transition-all min-h-[120px]",
                isDragTarget ? col.dropBg : `bg-zinc-950 ${col.accent}`
              )}
              onDragOver={(e) => { e.preventDefault(); setDragOver(col.key); }}
              onDragLeave={() => setDragOver(null)}
              onDrop={(e) => handleDrop(e, col.key)}
            >
              {/* Column header */}
              <div className={cn("flex items-center justify-between px-4 py-3 rounded-t-2xl border-b border-zinc-800/60", col.headerBg)}>
                <div className="flex items-center gap-2">
                  <span className="text-base">{col.icon}</span>
                  <h3 className="text-sm font-semibold text-white">{col.label}</h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500 bg-zinc-900/60 px-2 py-0.5 rounded-full font-medium">
                    {totalInCol}
                  </span>
                  <button
                    onClick={() => setAddForStatus(col.key)}
                    className="text-zinc-500 hover:text-zinc-200 text-lg leading-none transition-colors w-6 h-6 flex items-center justify-center rounded-lg hover:bg-zinc-800"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Task list */}
              <div className="flex-1 p-3 space-y-2 overflow-y-auto">
                {colTasks.length === 0 ? (
                  <div className={cn(
                    "flex items-center justify-center h-16 rounded-xl border-2 border-dashed",
                    isDragTarget ? "border-blue-500/50 text-blue-400" : "border-zinc-800 text-zinc-700"
                  )}>
                    <span className="text-xs">{isDragTarget ? "Hier ablegen" : "Keine Tasks"}</span>
                  </div>
                ) : (
                  colTasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      objectives={objectives}
                      onDragStart={handleDragStart}
                      onComplete={handleComplete}
                      onMoveNext={handleMoveNext}
                      completing={completing}
                    />
                  ))
                )}

                {/* Show more done tasks */}
                {col.key === "done" && !showDone && totalInCol > 5 && (
                  <button
                    onClick={() => setShowDone(true)}
                    className="w-full text-xs text-zinc-600 hover:text-zinc-400 py-2 transition-colors"
                  >
                    + {totalInCol - 5} weitere anzeigen
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Add Task Modal ─────────────────────────────────────────────────── */}
      {addForStatus && (
        <AddTaskModal
          defaultStatus={addForStatus}
          objectives={objectives}
          onClose={() => setAddForStatus(null)}
          onSave={load}
        />
      )}
    </div>
  );
}
