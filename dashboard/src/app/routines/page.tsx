"use client";

import { useState, useCallback } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import CircularProgress from "@/components/CircularProgress";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useRoutines } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { Routine } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Pencil, Trash2, Check } from "lucide-react";

// ─── Time-of-day config ───────────────────────────────────────────────────────

const TIME_SECTIONS = [
  { key: "morning", label: "Morgens", emoji: "🌅" },
  { key: "midday",  label: "Mittags", emoji: "☀️" },
  { key: "evening", label: "Abends",  emoji: "🌙" },
  { key: "anytime", label: "Jederzeit", emoji: "🔄" },
] as const;

// ─── Edit Modal ───────────────────────────────────────────────────────────────

function EditRoutineModal({
  routine,
  onSave,
  onClose,
  saving,
}: {
  routine: Routine;
  onSave: (data: {
    title: string;
    description: string | null;
    frequency_human: string | null;
    status: string;
    time_of_day: string;
  }) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    title: routine.title,
    description: routine.description ?? "",
    frequency_human: routine.frequency_human ?? "",
    status: routine.status,
    time_of_day: routine.time_of_day ?? "anytime",
  });

  function handleSave() {
    onSave({
      title: form.title.trim(),
      description: form.description.trim() || null,
      frequency_human: form.frequency_human.trim() || null,
      status: form.status,
      time_of_day: form.time_of_day,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full shadow-2xl">
        <h3 className="text-white font-semibold text-lg mb-5">Routine bearbeiten</h3>

        <div className="space-y-4">
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Name</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Beschreibung</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={2}
              placeholder="Optionale Beschreibung…"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>

          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Frequenz (z.B. "täglich", "3× pro Woche")</label>
            <input
              type="text"
              value={form.frequency_human}
              onChange={(e) => setForm((f) => ({ ...f, frequency_human: e.target.value }))}
              placeholder="z.B. täglich morgens"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="text-zinc-400 text-xs mb-2 block">Tageszeit</label>
            <div className="grid grid-cols-2 gap-2">
              {TIME_SECTIONS.map((s) => (
                <button
                  key={s.key}
                  onClick={() => setForm((f) => ({ ...f, time_of_day: s.key }))}
                  className={cn(
                    "py-2 rounded-lg text-sm font-medium border transition-colors",
                    form.time_of_day === s.key
                      ? "bg-blue-900/60 border-blue-600 text-blue-300"
                      : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-white"
                  )}
                >
                  {s.emoji} {s.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-zinc-400 text-xs mb-2 block">Status</label>
            <div className="flex gap-3">
              {["active", "paused"].map((s) => (
                <button
                  key={s}
                  onClick={() => setForm((f) => ({ ...f, status: s }))}
                  className={cn(
                    "flex-1 py-2 rounded-lg text-sm font-medium border transition-colors",
                    form.status === s
                      ? s === "active"
                        ? "bg-green-900/60 border-green-700 text-green-300"
                        : "bg-yellow-900/60 border-yellow-700 text-yellow-300"
                      : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-white"
                  )}
                >
                  {s === "active" ? "✅ Aktiv" : "⏸️ Pausiert"}
                </button>
              ))}
            </div>
          </div>
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

// ─── Routine Card ─────────────────────────────────────────────────────────────

function RoutineCard({
  routine,
  onComplete,
  onEdit,
  onDelete,
  completing,
}: {
  routine: Routine;
  onComplete: (id: number) => void;
  onEdit: (r: Routine) => void;
  onDelete: (r: Routine) => void;
  completing: number | null;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 p-3.5 rounded-xl border transition-all group",
        routine.completed_today
          ? "bg-green-950/40 border-green-900/50"
          : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700"
      )}
    >
      {/* Completion checkbox */}
      <button
        onClick={() => !routine.completed_today && onComplete(routine.id)}
        disabled={routine.completed_today || completing === routine.id}
        className={cn(
          "shrink-0 w-8 h-8 rounded-lg border-2 flex items-center justify-center transition-all",
          routine.completed_today
            ? "bg-green-600 border-green-600 cursor-default"
            : completing === routine.id
            ? "border-zinc-600 bg-zinc-800 animate-pulse"
            : "border-zinc-600 bg-zinc-800 hover:border-green-500 hover:bg-green-950/40 cursor-pointer"
        )}
        title={routine.completed_today ? "Erledigt" : "Als erledigt markieren"}
      >
        {routine.completed_today && <Check size={14} className="text-white" strokeWidth={3} />}
        {completing === routine.id && <div className="w-3 h-3 rounded-full bg-zinc-500" />}
      </button>

      <div className="flex-1 min-w-0">
        <div
          className={cn(
            "font-medium text-sm",
            routine.completed_today ? "text-zinc-400 line-through" : "text-white"
          )}
        >
          {routine.title}
        </div>
        {routine.description && (
          <p className="text-zinc-500 text-xs mt-0.5 truncate">{routine.description}</p>
        )}
        {routine.frequency_human && (
          <p className="text-zinc-600 text-xs mt-0.5">{routine.frequency_human}</p>
        )}
      </div>

      <div className="shrink-0 flex flex-col items-end gap-1.5">
        {routine.completed_today ? (
          <span className="text-green-400 text-xs font-medium bg-green-950/60 px-2 py-0.5 rounded-full border border-green-900/60">
            Done ✅
          </span>
        ) : (
          <span className="text-zinc-500 text-xs bg-zinc-800/60 px-2 py-0.5 rounded-full">
            Offen
          </span>
        )}
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onEdit(routine)}
            className="text-zinc-500 hover:text-blue-400 transition-colors p-1 rounded"
            title="Bearbeiten"
          >
            <Pencil size={12} />
          </button>
          <button
            onClick={() => onDelete(routine)}
            className="text-zinc-500 hover:text-red-400 transition-colors p-1 rounded"
            title="Löschen"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function RoutinesPage() {
  const { data, error, isLoading, mutate } = useRoutines();
  const [editingRoutine, setEditingRoutine] = useState<Routine | null>(null);
  const [deletingRoutine, setDeletingRoutine] = useState<Routine | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [completing, setCompleting] = useState<number | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const handleComplete = useCallback(
    async (routineId: number) => {
      setCompleting(routineId);
      mutate(
        (prev) =>
          prev
            ? {
                routines: prev.routines.map((r) =>
                  r.id === routineId ? { ...r, completed_today: true } : r
                ),
              }
            : prev,
        false
      );
      try {
        await api.completeRoutine(routineId);
        addToast("Routine erledigt ✅", "success");
      } catch {
        await mutate();
        addToast("Fehler beim Abhaken", "error");
      } finally {
        setCompleting(null);
      }
    },
    [mutate, addToast]
  );

  const handleEdit = useCallback(
    async (formData: {
      title: string;
      description: string | null;
      frequency_human: string | null;
      status: string;
      time_of_day: string;
    }) => {
      if (!editingRoutine) return;
      setSaving(true);
      try {
        await api.updateRoutine(editingRoutine.id, formData);
        await mutate();
        addToast("Routine aktualisiert", "success");
        setEditingRoutine(null);
      } catch {
        addToast("Fehler beim Speichern", "error");
      } finally {
        setSaving(false);
      }
    },
    [editingRoutine, mutate, addToast]
  );

  const handleDelete = useCallback(async () => {
    if (!deletingRoutine) return;
    setDeleting(true);
    mutate(
      (prev) =>
        prev
          ? { routines: prev.routines.filter((r) => r.id !== deletingRoutine.id) }
          : prev,
      false
    );
    try {
      await api.deleteRoutine(deletingRoutine.id);
      addToast("Routine gelöscht", "success");
      setDeletingRoutine(null);
    } catch {
      await mutate();
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
    }
  }, [deletingRoutine, mutate, addToast]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  const routines = data?.routines ?? [];
  const active = routines.filter((r) => r.status === "active");
  const paused = routines.filter((r) => r.status === "paused");
  const doneToday = active.filter((r) => r.completed_today).length;
  const pct = active.length > 0 ? Math.round((doneToday / active.length) * 100) : 0;

  return (
    <div>
      <Header
        title="🔄 Routinen"
        subtitle={`${doneToday}/${active.length} heute erledigt · ${pct}%`}
      />

      {active.length > 0 && (
        <>
          {/* Progress overview */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6 flex items-center gap-5">
            <CircularProgress
              value={pct}
              size={72}
              strokeWidth={7}
              color="#22c55e"
              label={`${pct}%`}
            />
            <div>
              <div className="text-white font-semibold text-lg">{doneToday} / {active.length}</div>
              <div className="text-zinc-400 text-sm">Routinen heute erledigt</div>
              {doneToday === active.length && active.length > 0 && (
                <div className="text-green-400 text-xs mt-1">🎉 Alle Routinen abgehakt!</div>
              )}
            </div>
          </div>

          {/* Time-of-day sections */}
          <div className="space-y-5 mb-6">
            {TIME_SECTIONS.map(({ key, label, emoji }) => {
              const sectionRoutines = active.filter(
                (r) => (r.time_of_day || "anytime") === key
              );
              if (sectionRoutines.length === 0) return null;

              const sectionDone = sectionRoutines.filter((r) => r.completed_today).length;

              return (
                <div key={key}>
                  <div className="flex items-center gap-2 mb-2.5">
                    <span className="text-base">{emoji}</span>
                    <h2 className="text-white font-semibold text-sm">{label}</h2>
                    <span className="text-zinc-500 text-xs">
                      {sectionDone}/{sectionRoutines.length}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {sectionRoutines.map((r) => (
                      <RoutineCard
                        key={r.id}
                        routine={r}
                        onComplete={handleComplete}
                        onEdit={setEditingRoutine}
                        onDelete={setDeletingRoutine}
                        completing={completing}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Paused */}
      {paused.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-3 flex items-center gap-2">
            <span>⏸️</span> Pausierte Routinen
          </h2>
          <div className="space-y-2">
            {paused.map((r) => (
              <div key={r.id} className="flex items-center gap-4 p-3 rounded-lg bg-zinc-800/30 border border-zinc-800 group">
                <span className="text-xl opacity-40">⏸</span>
                <div className="flex-1 min-w-0">
                  <div className="text-zinc-500 font-medium text-sm">{r.title}</div>
                  {r.frequency_human && (
                    <div className="text-zinc-600 text-xs">{r.frequency_human}</div>
                  )}
                </div>
                <span className="text-yellow-400 text-xs bg-yellow-900/40 border border-yellow-800/40 px-2 py-0.5 rounded-full">
                  Pausiert
                </span>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => setEditingRoutine(r)}
                    className="text-zinc-500 hover:text-blue-400 transition-colors p-1 rounded"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    onClick={() => setDeletingRoutine(r)}
                    className="text-zinc-500 hover:text-red-400 transition-colors p-1 rounded"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {routines.length === 0 && (
        <EmptyState emoji="🔄" message="Keine Routinen — per Telegram erstellen!" />
      )}

      {/* Edit Modal */}
      {editingRoutine && (
        <EditRoutineModal
          routine={editingRoutine}
          onSave={handleEdit}
          onClose={() => setEditingRoutine(null)}
          saving={saving}
        />
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deletingRoutine}
        title="Routine löschen?"
        message={`"${deletingRoutine?.title}" wird dauerhaft gelöscht — inkl. der gesamten Completion-Historie.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingRoutine(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
