"use client";

import React, { useState } from "react";
import useSWR from "swr";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import { ToastContainer, useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import type { UserDoc } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Pencil, Trash2, Plus, ChevronDown, ChevronRight, X, Check, FlaskConical, Dumbbell } from "lucide-react";

// ─── Doc Modal ────────────────────────────────────────────────────────────────

const EMOJI_SUGGESTIONS = ["📄","📝","📓","📖","🗒️","💡","🌅","💪","🍽️","🎯","⚡","🧠","🏋️","🗺️","🔑","❤️","🌿","✨","📊","🎨"];

function DocModal({
  doc,
  onSave,
  onClose,
  saving,
}: {
  doc?: UserDoc;
  onSave: (data: { title: string; emoji: string; content: string }) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [title, setTitle] = useState(doc?.title ?? "");
  const [emoji, setEmoji] = useState(doc?.emoji ?? "📄");
  const [content, setContent] = useState(doc?.content ?? "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSave({ title: title.trim(), emoji: emoji.trim() || "📄", content });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h3 className="text-white font-semibold text-lg">
            {doc ? "Dokument bearbeiten" : "Neues Dokument"}
          </h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="px-6 py-4 space-y-4 overflow-y-auto flex-1">
            {/* Emoji + Title row */}
            <div className="flex gap-3">
              <div>
                <label className="text-zinc-400 text-xs mb-1.5 block">Emoji</label>
                <input
                  type="text"
                  value={emoji}
                  onChange={(e) => setEmoji(e.target.value)}
                  maxLength={4}
                  className="w-16 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-center text-xl focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="flex-1">
                <label className="text-zinc-400 text-xs mb-1.5 block">Titel *</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="z.B. Morgenroutine, Dankbarkeits-Journal..."
                  autoFocus
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Emoji suggestions */}
            <div className="flex flex-wrap gap-2">
              {EMOJI_SUGGESTIONS.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => setEmoji(e)}
                  className={cn(
                    "w-8 h-8 rounded-lg text-base transition-colors",
                    emoji === e ? "bg-blue-600" : "bg-zinc-800 hover:bg-zinc-700"
                  )}
                >
                  {e}
                </button>
              ))}
            </div>

            {/* Content */}
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Inhalt (Markdown unterstützt)</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={14}
                placeholder="Schreib hier alles auf, was du dir merken willst..."
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500 resize-none leading-relaxed"
              />
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-zinc-800 flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={saving || !title.trim()}
              className="px-5 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors disabled:opacity-40"
            >
              {saving ? "Speichern…" : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Doc Card ─────────────────────────────────────────────────────────────────

function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, '<code class="bg-zinc-700 px-1 rounded text-xs font-mono">$1</code>')
    .replace(/^## (.+)$/gm, '<div class="text-white font-semibold text-base mt-3 mb-1">$1</div>')
    .replace(/^### (.+)$/gm, '<div class="text-zinc-300 font-medium mt-2 mb-0.5">$1</div>')
    .replace(/^— (.+)$/gm, '<div class="ml-3 text-zinc-400 text-sm">— $1</div>')
    .replace(/^→ (.+)$/gm, '<div class="ml-3 text-blue-400 text-sm">→ $1</div>')
    .replace(/\n/g, "<br/>");
}

function DocCard({
  doc,
  onEdit,
  onDelete,
}: {
  doc: UserDoc;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const hasContent = doc.content.trim().length > 0;
  const preview = doc.content.slice(0, 120).trim();

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4">
        <span className="text-2xl shrink-0">{doc.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="text-white font-semibold truncate">{doc.title}</div>
          {!expanded && hasContent && (
            <div className="text-zinc-500 text-xs mt-0.5 truncate">{preview}{doc.content.length > 120 ? "…" : ""}</div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onEdit}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <Pencil size={14} />
          </button>
          {confirmDelete ? (
            <>
              <button
                onClick={onDelete}
                className="p-1.5 rounded-lg text-red-400 hover:bg-red-900/30 transition-colors"
              >
                <Check size={14} />
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors"
              >
                <X size={14} />
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-zinc-800 transition-colors"
            >
              <Trash2 size={14} />
            </button>
          )}
          {hasContent && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors ml-1"
            >
              {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && hasContent && (
        <div className="px-5 pb-5 border-t border-zinc-800 pt-4">
          <div
            className="text-zinc-300 text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(doc.content) }}
          />
        </div>
      )}

      {!hasContent && (
        <div className="px-5 pb-4">
          <button
            onClick={onEdit}
            className="text-xs text-zinc-600 hover:text-blue-400 transition-colors"
          >
            + Inhalt hinzufügen
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Protocol Editor ─────────────────────────────────────────────────────────

function ProtocolJsonModal({
  title,
  emoji,
  initialData,
  onSave,
  onClose,
}: {
  title: string;
  emoji: React.ReactNode;
  initialData: unknown;
  onSave: (data: unknown) => Promise<void>;
  onClose: () => void;
}) {
  const [text, setText] = useState(JSON.stringify(initialData, null, 2));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setError("");
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (e: unknown) {
      setError("Ungültiges JSON: " + (e instanceof Error ? e.message : "Parse-Fehler"));
      return;
    }
    setSaving(true);
    try {
      await onSave(parsed);
      onClose();
    } catch (e: unknown) {
      setError("Fehler beim Speichern: " + (e instanceof Error ? e.message : "Unbekannt"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h3 className="text-white font-semibold flex items-center gap-2">
            {emoji} {title}
          </h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col px-6 py-4 gap-3">
          {error && (
            <div className="bg-red-950/50 border border-red-800/40 rounded-lg px-3 py-2 text-red-400 text-xs">
              ⚠️ {error}
            </div>
          )}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            className="flex-1 w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-zinc-200 text-xs font-mono focus:outline-none focus:border-blue-500 resize-none leading-relaxed min-h-[400px]"
          />
          <p className="text-zinc-600 text-xs">JSON direkt editieren. Ungültiges JSON wird vor dem Speichern abgefangen.</p>
        </div>
        <div className="px-6 py-4 border-t border-zinc-800 flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors">
            Abbrechen
          </button>
          <button onClick={handleSave} disabled={saving} className="px-5 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors disabled:opacity-40">
            {saving ? "Speichern…" : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProtocolCard({
  emoji,
  title,
  description,
  fetchFn,
  saveFn,
  addToast,
}: {
  emoji: React.ReactNode;
  title: string;
  description: string;
  fetchFn: () => Promise<unknown>;
  saveFn: (data: unknown) => Promise<{ ok: boolean }>;
  addToast: (msg: string, type: "success" | "error") => void;
}) {
  const { data, error, isLoading, mutate } = useSWR(title, fetchFn);
  const [editing, setEditing] = useState(false);

  const handleSave = async (parsed: unknown) => {
    await saveFn(parsed);
    await mutate();
    addToast(`${title} gespeichert`, "success");
  };

  return (
    <>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex items-start gap-4">
        <div className="text-3xl shrink-0">{emoji}</div>
        <div className="flex-1 min-w-0">
          <div className="text-white font-semibold mb-1">{title}</div>
          <div className="text-zinc-500 text-xs mb-3">{description}</div>
          {isLoading && <p className="text-zinc-600 text-xs">Lädt…</p>}
          {error && <p className="text-red-400 text-xs">Fehler beim Laden</p>}
          {data && !isLoading && (
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs rounded-lg transition-colors"
            >
              <Pencil size={12} /> Bearbeiten
            </button>
          )}
        </div>
      </div>
      {editing && data && (
        <ProtocolJsonModal
          title={title}
          emoji={emoji}
          initialData={data}
          onSave={handleSave}
          onClose={() => setEditing(false)}
        />
      )}
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DocsPage() {
  const { data, error, isLoading, mutate } = useSWR("/api/docs", () => api.listDocs());
  const { toasts, addToast, dismissToast } = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingDoc, setEditingDoc] = useState<UserDoc | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"docs" | "protocols">("docs");

  const docs = data?.docs ?? [];

  const handleSave = async (formData: { title: string; emoji: string; content: string }) => {
    setSaving(true);
    try {
      if (editingDoc) {
        await api.updateDoc(editingDoc.id, formData);
        addToast("Dokument gespeichert", "success");
      } else {
        await api.createDoc({ ...formData, sort_order: docs.length });
        addToast("Dokument erstellt", "success");
      }
      await mutate();
      setModalOpen(false);
      setEditingDoc(undefined);
    } catch {
      addToast("Fehler beim Speichern", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteDoc(id);
      await mutate();
      addToast("Dokument gelöscht", "success");
    } catch {
      addToast("Fehler beim Löschen", "error");
    }
  };

  const openCreate = () => {
    setEditingDoc(undefined);
    setModalOpen(true);
  };

  const openEdit = (doc: UserDoc) => {
    setEditingDoc(doc);
    setModalOpen(true);
  };

  return (
    <div>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <Header
        title="Dokumente"
        subtitle="Deine persönliche Referenz-Bibliothek"
        action={
          activeTab === "docs" ? (
            <button
              onClick={openCreate}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Plus size={16} />
              Neu
            </button>
          ) : undefined
        }
      />

      {/* Tab bar */}
      <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-xl p-1 mb-5">
        <button
          onClick={() => setActiveTab("docs")}
          className={cn(
            "flex-1 py-2 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2",
            activeTab === "docs" ? "bg-zinc-700 text-white" : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          📄 Dokumente
        </button>
        <button
          onClick={() => setActiveTab("protocols")}
          className={cn(
            "flex-1 py-2 text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2",
            activeTab === "protocols" ? "bg-zinc-700 text-white" : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          🔬 Protokolle
        </button>
      </div>

      {/* ── Docs tab ── */}
      {activeTab === "docs" && (
        <>
          {isLoading && <LoadingSpinner />}
          {error && <ErrorState message="Dokumente konnten nicht geladen werden." />}

          {!isLoading && !error && (
            <>
              {docs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="text-5xl mb-4">📄</div>
                  <h3 className="text-white font-semibold text-lg mb-2">Noch keine Dokumente</h3>
                  <p className="text-zinc-500 text-sm mb-6 max-w-sm">
                    Leg deine erste persönliche Referenz an — Routinen, Journal-Templates, Ernährungsplan, Notizen, was immer du willst.
                  </p>
                  <button
                    onClick={openCreate}
                    className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-xl transition-colors"
                  >
                    <Plus size={16} />
                    Erstes Dokument erstellen
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {docs.map((doc) => (
                    <DocCard
                      key={doc.id}
                      doc={doc}
                      onEdit={() => openEdit(doc)}
                      onDelete={() => handleDelete(doc.id)}
                    />
                  ))}
                  <button
                    onClick={openCreate}
                    className="w-full flex items-center justify-center gap-2 py-3 border border-dashed border-zinc-700 rounded-xl text-zinc-500 hover:text-white hover:border-zinc-500 transition-colors text-sm"
                  >
                    <Plus size={16} />
                    Weiteres Dokument
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ── Protokolle tab ── */}
      {activeTab === "protocols" && (
        <div className="space-y-4">
          <p className="text-zinc-500 text-sm">
            Bearbeite deine Protokoll-Dateien direkt als JSON. Änderungen werden sofort wirksam.
          </p>
          <ProtocolCard
            emoji={<FlaskConical size={28} className="text-purple-400" />}
            title="💊 Supplement-Protokoll"
            description="Keto-Supplement-Stack · Morgens / Mittags / Abends · Makro-Ziele · Hydration"
            fetchFn={() => api.getSupplementProtocol()}
            saveFn={(d) => api.updateSupplementProtocol(d)}
            addToast={addToast}
          />
          <ProtocolCard
            emoji={<Dumbbell size={28} className="text-green-400" />}
            title="🏋️ Fitness-Split"
            description="3er Rotation: Beine / Pull / Push · Übungen · Ruhetage · Rotation-Anker"
            fetchFn={() => api.getFitnessProtocol()}
            saveFn={(d) => api.updateFitnessProtocol(d)}
            addToast={addToast}
          />
        </div>
      )}

      {modalOpen && (
        <DocModal
          doc={editingDoc}
          onSave={handleSave}
          onClose={() => { setModalOpen(false); setEditingDoc(undefined); }}
          saving={saving}
        />
      )}
    </div>
  );
}
