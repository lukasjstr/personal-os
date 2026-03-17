"use client";

import { useState, useCallback, useRef } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { cn } from "@/lib/utils";
import { Plus, RefreshCw } from "lucide-react";

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

type Task = {
  id: number;
  title: string;
  status: string;
  priority: number;
  category: string;
  due_date?: string;
  objective_id?: number;
};

type Objective = {
  id: number;
  title: string;
};

const COLUMNS = [
  { key: "todo", label: "📋 Todo", color: "border-zinc-700" },
  { key: "in_progress", label: "⚡ In Progress", color: "border-blue-700" },
  { key: "done", label: "✅ Done", color: "border-green-700" },
] as const;

const PRIORITY_COLORS: Record<number, string> = {
  1: "bg-red-900/60 text-red-300",
  2: "bg-orange-900/60 text-orange-300",
  3: "bg-yellow-900/60 text-yellow-300",
  4: "bg-blue-900/60 text-blue-300",
  5: "bg-zinc-700 text-zinc-400",
};
const PRIORITY_LABELS: Record<number, string> = { 1: "P1", 2: "P2", 3: "P3", 4: "P4", 5: "P5" };

function TaskCard({
  task,
  objectives,
  onDragStart,
}: {
  task: Task;
  objectives: Objective[];
  onDragStart: (e: React.DragEvent, task: Task) => void;
}) {
  const obj = objectives.find((o) => o.id === task.objective_id);
  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== "done";

  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, task)}
      className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 cursor-grab active:cursor-grabbing hover:border-zinc-600 transition-colors select-none"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-white font-medium leading-snug flex-1">{task.title}</p>
        <span className={cn("text-xs px-1.5 py-0.5 rounded font-medium shrink-0", PRIORITY_COLORS[task.priority] || PRIORITY_COLORS[3])}>
          {PRIORITY_LABELS[task.priority] || "P3"}
        </span>
      </div>
      {(obj || task.due_date) && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          {obj && (
            <span className="text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded truncate max-w-[140px]">
              {obj.title}
            </span>
          )}
          {task.due_date && (
            <span className={cn("text-xs", isOverdue ? "text-red-400" : "text-zinc-500")}>
              {isOverdue ? "⚠️ " : ""}{new Date(task.due_date).toLocaleDateString("de-DE", { month: "short", day: "numeric" })}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function AddTaskModal({
  defaultStatus,
  onClose,
  onSave,
}: {
  defaultStatus: string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState(3);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), priority, status: defaultStatus }),
      });
      onSave();
      onClose();
    } catch (e) {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-md p-5">
        <h2 className="text-base font-bold text-white mb-3">Neuer Task</h2>
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          placeholder="Task-Titel"
          className="w-full bg-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm outline-none border border-zinc-700 focus:border-indigo-500 mb-3"
        />
        <div className="flex gap-1 mb-4">
          {[1, 2, 3, 4, 5].map((p) => (
            <button
              key={p}
              onClick={() => setPriority(p)}
              className={cn(
                "flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors",
                priority === p ? PRIORITY_COLORS[p] : "bg-zinc-800 text-zinc-500 hover:text-white"
              )}
            >
              P{p}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl py-2.5 font-semibold text-sm transition-colors"
          >
            {saving ? "Speichern…" : "Erstellen"}
          </button>
          <button onClick={onClose} className="px-4 py-2.5 text-zinc-400 hover:text-white text-sm transition-colors">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

export default function KanbanPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addForStatus, setAddForStatus] = useState<string | null>(null);
  const [dragging, setDragging] = useState<Task | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const load = useCallback(async () => {
    try {
      const [tasksRes, objRes] = await Promise.all([
        apiFetch<{ tasks: Task[] }>("/api/tasks?limit=200"),
        apiFetch<{ objectives: Objective[] }>("/api/objectives"),
      ]);
      setTasks(tasksRes.tasks);
      setObjectives(objRes.objectives);
      setLastRefresh(new Date());
      setError(null);
    } catch (e) {
      setError("Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30000);
  useState(() => { load(); });

  const handleDragStart = (e: React.DragEvent, task: Task) => {
    setDragging(task);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent, status: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOver(status);
  };

  const handleDrop = async (e: React.DragEvent, newStatus: string) => {
    e.preventDefault();
    setDragOver(null);
    if (!dragging || dragging.status === newStatus) {
      setDragging(null);
      return;
    }
    const taskId = dragging.id;
    // Optimistic update
    setTasks((prev) => prev.map((t) => t.id === taskId ? { ...t, status: newStatus } : t));
    setDragging(null);
    try {
      await apiFetch(`/api/tasks/${taskId}`, {
        method: "PUT",
        body: JSON.stringify({ status: newStatus }),
      });
    } catch (e) {
      // Revert on failure
      await load();
    }
  };

  const getColumnTasks = (status: string) =>
    tasks.filter((t) => t.status === status)
      .sort((a, b) => a.priority - b.priority);

  return (
    <>
      <Header
        title="🗂 Kanban"
        subtitle={`${tasks.filter(t => t.status === "todo").length} Todo · ${tasks.filter(t => t.status === "in_progress").length} In Progress`}
      />
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs text-zinc-500">
            Zuletzt aktualisiert: {lastRefresh.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} · auto-refresh 30s
          </p>
          <button
            onClick={load}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors"
          >
            <RefreshCw size={12} />
            Aktualisieren
          </button>
        </div>

        {loading && <LoadingSpinner />}
        {error && <ErrorState message={error} />}

        {!loading && !error && (
          <div className="flex flex-col md:flex-row gap-4">
            {COLUMNS.map((col) => {
              const colTasks = getColumnTasks(col.key);
              const isDragTarget = dragOver === col.key;

              return (
                <div
                  key={col.key}
                  className={cn(
                    "flex-1 bg-zinc-950 border rounded-2xl p-3 min-h-[200px] transition-colors",
                    isDragTarget ? "border-indigo-500 bg-indigo-950/20" : col.color
                  )}
                  onDragOver={(e) => handleDragOver(e, col.key)}
                  onDragLeave={() => setDragOver(null)}
                  onDrop={(e) => handleDrop(e, col.key)}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-white">{col.label}</h3>
                    <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full">
                      {colTasks.length}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {colTasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        objectives={objectives}
                        onDragStart={handleDragStart}
                      />
                    ))}
                  </div>

                  <button
                    onClick={() => setAddForStatus(col.key)}
                    className="w-full mt-3 flex items-center justify-center gap-1.5 text-zinc-600 hover:text-zinc-400 text-xs py-2 border border-dashed border-zinc-800 hover:border-zinc-600 rounded-lg transition-colors"
                  >
                    <Plus size={12} />
                    Neuer Task
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {addForStatus && (
        <AddTaskModal
          defaultStatus={addForStatus}
          onClose={() => setAddForStatus(null)}
          onSave={load}
        />
      )}
    </>
  );
}
