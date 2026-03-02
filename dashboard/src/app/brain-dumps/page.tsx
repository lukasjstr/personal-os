"use client";

import { useState, useCallback } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useBrainDumps } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { BrainDump } from "@/lib/api";
import { formatDateTime, formatTimeAgo, cn } from "@/lib/utils";
import { Pencil, Trash2, Search } from "lucide-react";

// ─── Edit Modal ───────────────────────────────────────────────────────────────

function EditBrainDumpModal({
  dump,
  onSave,
  onClose,
  saving,
}: {
  dump: BrainDump;
  onSave: (raw_input: string) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [text, setText] = useState(dump.raw_input);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full shadow-2xl">
        <h3 className="text-white font-semibold text-lg mb-5">Brain Dump bearbeiten</h3>

        <div>
          <label className="text-zinc-400 text-xs mb-1.5 block">Inhalt</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
          />
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
            onClick={() => onSave(text.trim())}
            disabled={saving || !text.trim()}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium"
          >
            {saving ? "Wird gespeichert…" : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────

function BrainDumpCard({
  dump,
  onEdit,
  onDelete,
}: {
  dump: BrainDump;
  onEdit: (dump: BrainDump) => void;
  onDelete: (dump: BrainDump) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isLong = dump.raw_input.length > 200;

  return (
    <div
      className={cn(
        "bg-zinc-900 border rounded-xl overflow-hidden transition-all",
        dump.processed ? "border-zinc-800 hover:border-zinc-700" : "border-blue-900/60 hover:border-blue-800"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 pt-4 pb-2">
        <span className="text-xl">🧠</span>
        <span
          className="text-zinc-500 text-xs flex-1 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          {formatTimeAgo(dump.created_at)}
        </span>
        <div className="flex items-center gap-2">
          {!dump.processed && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900/60 text-blue-400 border border-blue-800/50">
              Neu
            </span>
          )}
          {dump.processed && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-900/50 text-green-400 border border-green-800/50">
              Verarbeitet
            </span>
          )}
          {dump.linked_objective_id && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-violet-900/50 text-violet-400 border border-violet-800/50">
              🎯 Linked
            </span>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onEdit(dump); }}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-blue-400 hover:bg-blue-900/30 transition-colors"
            title="Bearbeiten"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(dump); }}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-900/30 transition-colors"
            title="Löschen"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div
        className="px-5 pb-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <p className={cn("text-white text-sm leading-relaxed", !expanded && isLong && "line-clamp-3")}>
          {dump.raw_input}
        </p>

        {dump.ai_interpretation && (
          <div className={cn("mt-3 pl-3 border-l-2 border-blue-600/70", !expanded && "line-clamp-2")}>
            <div className="text-xs text-zinc-500 mb-1">🤖 KI-Interpretation</div>
            <p className="text-blue-300 text-sm leading-relaxed">{dump.ai_interpretation}</p>
          </div>
        )}

        {isLong && (
          <button className="text-xs text-zinc-500 mt-2 hover:text-zinc-300 transition-colors">
            {expanded ? "Weniger anzeigen ↑" : "Mehr anzeigen ↓"}
          </button>
        )}

        <div className="text-zinc-600 text-xs mt-2">{formatDateTime(dump.created_at)}</div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function BrainDumpsPage() {
  const { data, error, isLoading, mutate } = useBrainDumps();
  const [search, setSearch] = useState("");
  const [filterProcessed, setFilterProcessed] = useState<boolean | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const [editingDump, setEditingDump] = useState<BrainDump | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingDump, setDeletingDump] = useState<BrainDump | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleSave = useCallback(async (raw_input: string) => {
    if (!editingDump) return;
    setSaving(true);
    try {
      await api.updateBrainDump(editingDump.id, { raw_input });
      await mutate();
      addToast("Brain Dump aktualisiert");
      setEditingDump(null);
    } catch {
      addToast("Fehler beim Speichern", "error");
    } finally {
      setSaving(false);
    }
  }, [editingDump, mutate, addToast]);

  const handleDelete = useCallback(async () => {
    if (!deletingDump) return;
    setDeleting(true);
    mutate(
      (prev) => prev ? { brain_dumps: prev.brain_dumps.filter((d) => d.id !== deletingDump.id) } : prev,
      false
    );
    try {
      await api.deleteBrainDump(deletingDump.id);
      await mutate();
      addToast("Brain Dump gelöscht");
    } catch {
      await mutate();
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
      setDeletingDump(null);
    }
  }, [deletingDump, mutate, addToast]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  let dumps = data?.brain_dumps ?? [];

  if (filterProcessed !== null) {
    dumps = dumps.filter((d) => d.processed === filterProcessed);
  }

  if (search.trim()) {
    const q = search.toLowerCase();
    dumps = dumps.filter(
      (d) =>
        d.raw_input.toLowerCase().includes(q) ||
        (d.ai_interpretation?.toLowerCase().includes(q) ?? false)
    );
  }

  const all = data?.brain_dumps ?? [];
  const unprocessed = all.filter((d) => !d.processed).length;
  const withLinked = all.filter((d) => d.linked_objective_id).length;

  return (
    <div>
      <Header
        title="🧠 Brain Dumps"
        subtitle={`${all.length} gesamt · ${unprocessed} unverarbeitet · ${withLinked} verknüpft`}
      />

      {/* Search & Filter */}
      <div className="flex flex-col gap-3 mb-6">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Brain Dumps durchsuchen..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-4 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
        <div className="flex gap-2">
          {([
            [null, "Alle", "bg-zinc-800 text-zinc-400"],
            [false, "Unverarbeitet", "bg-blue-900/60 text-blue-400 border-blue-800"],
            [true, "Verarbeitet", "bg-green-900/50 text-green-400 border-green-800"],
          ] as const).map(([val, label, activeStyle]) => (
            <button
              key={String(val)}
              onClick={() => setFilterProcessed(val)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm border transition-colors",
                filterProcessed === val
                  ? `${activeStyle} border-current`
                  : "bg-zinc-900 text-zinc-400 border-zinc-700 hover:text-white hover:border-zinc-600"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {dumps.length === 0 ? (
        <EmptyState emoji="🧠" message="Keine Brain Dumps gefunden" />
      ) : (
        <div className="space-y-4">
          {dumps.map((dump) => (
            <BrainDumpCard
              key={dump.id}
              dump={dump}
              onEdit={setEditingDump}
              onDelete={setDeletingDump}
            />
          ))}
          <div className="text-center text-xs text-zinc-600 py-2">{dumps.length} Brain Dumps</div>
        </div>
      )}

      {editingDump && (
        <EditBrainDumpModal
          dump={editingDump}
          onSave={handleSave}
          onClose={() => setEditingDump(null)}
          saving={saving}
        />
      )}

      <ConfirmDialog
        open={!!deletingDump}
        title="Brain Dump löschen?"
        message={`"${deletingDump?.raw_input.slice(0, 80)}…" wird dauerhaft gelöscht.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingDump(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
