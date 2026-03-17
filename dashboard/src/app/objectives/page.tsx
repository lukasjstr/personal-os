"use client";

import React, { useState, useCallback } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useObjectives } from "@/hooks/useApi";
import { CATEGORY_EMOJI, CATEGORY_COLORS, formatDate, cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Objective, ObjectiveTask, KeyResult } from "@/lib/api";
import { ChevronDown, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";

// ─── Constants ────────────────────────────────────────────────────────────────

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

const CATEGORIES = [
  "health", "fitness", "business", "personal",
  "finance", "learning", "relationships",
];

const OBJECTIVE_STATUSES = ["active", "completed", "paused", "abandoned"];

const KR_METRIC_TYPES = ["number", "percentage", "boolean", "streak", "checklist"];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function avgProgress(obj: Objective): number {
  if (obj.key_results.length > 0) {
    return Math.round(
      obj.key_results.reduce((s, kr) => s + kr.progress_pct, 0) / obj.key_results.length
    );
  }
  if (obj.tasks.length > 0) {
    return Math.round(
      (obj.tasks.filter((t) => t.status === "done").length / obj.tasks.length) * 100
    );
  }
  return 0;
}

function progressColor(pct: number): string {
  if (pct >= 75) return "#22c55e";
  if (pct >= 40) return "#3b82f6";
  if (pct >= 20) return "#f59e0b";
  return "#ef4444";
}

function momentumDot(avg: number): string {
  if (avg >= 60) return "bg-emerald-400";
  if (avg >= 30) return "bg-yellow-400";
  return "bg-red-400";
}

// ─── Modals ───────────────────────────────────────────────────────────────────

function CreateObjectiveModal({
  onSave,
  onClose,
  saving,
  allObjectives = [],
  defaultCategory,
}: {
  onSave: (data: {
    title: string;
    category: string;
    description: string | null;
    target_date: string | null;
    parent_objective_id: number | null;
  }) => void;
  onClose: () => void;
  saving: boolean;
  allObjectives?: Objective[];
  defaultCategory?: string;
}) {
  const [form, setForm] = useState({
    title: "",
    category: defaultCategory ?? "personal",
    description: "",
    target_date: "",
    parent_objective_id: "",
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full shadow-2xl">
        <h3 className="text-white font-semibold text-lg mb-5">Neues Objective</h3>
        <div className="space-y-4">
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Titel *</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Objective-Titel"
              autoFocus
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          {allObjectives.length > 0 && (
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Übergeordnetes Ziel (optional)</label>
              <select
                value={form.parent_objective_id}
                onChange={(e) => setForm((f) => ({ ...f, parent_objective_id: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="">— Kein übergeordnetes Ziel —</option>
                {allObjectives
                  .filter((o) => o.status === "active")
                  .map((o) => (
                    <option key={o.id} value={String(o.id)}>
                      {CATEGORY_EMOJI[o.category] ?? "🎯"} {o.title}
                    </option>
                  ))}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Kategorie</label>
              <select
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_EMOJI[c] ?? "🎯"} {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Zieldatum</label>
              <input
                type="date"
                value={form.target_date}
                onChange={(e) => setForm((f) => ({ ...f, target_date: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Beschreibung</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={3}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
            />
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
            onClick={() =>
              onSave({
                title: form.title.trim(),
                category: form.category,
                description: form.description.trim() || null,
                target_date: form.target_date || null,
                parent_objective_id: form.parent_objective_id
                  ? parseInt(form.parent_objective_id)
                  : null,
              })
            }
            disabled={saving || !form.title.trim()}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium"
          >
            {saving ? "Erstellen…" : "Objective erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditObjectiveModal({
  obj,
  onSave,
  onClose,
  saving,
}: {
  obj: Objective;
  onSave: (data: {
    title: string;
    category: string;
    description: string | null;
    target_date: string | null;
    status: string;
  }) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    title: obj.title,
    category: obj.category,
    description: obj.description ?? "",
    target_date: obj.target_date ?? "",
    status: obj.status,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full shadow-2xl max-h-[90vh] overflow-y-auto">
        <h3 className="text-white font-semibold text-lg mb-5">Objective bearbeiten</h3>
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
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_EMOJI[c] ?? "🎯"} {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Status</label>
              <select
                value={form.status}
                onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                {OBJECTIVE_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s] ?? s}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Beschreibung</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={3}
              placeholder="Optionale Beschreibung…"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Zieldatum</label>
            <input
              type="date"
              value={form.target_date}
              onChange={(e) => setForm((f) => ({ ...f, target_date: e.target.value }))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
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
            onClick={() =>
              onSave({
                title: form.title.trim(),
                category: form.category,
                description: form.description.trim() || null,
                target_date: form.target_date || null,
                status: form.status,
              })
            }
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

function AddKRModal({
  onSave,
  onClose,
  saving,
}: {
  onSave: (data: {
    title: string;
    metric_type: string;
    target_value: number | null;
    unit: string | null;
  }) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({ title: "", metric_type: "number", target_value: "", unit: "" });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-sm w-full shadow-2xl">
        <h3 className="text-white font-semibold text-base mb-4">Key Result hinzufügen</h3>
        <div className="space-y-3">
          <div>
            <label className="text-zinc-400 text-xs mb-1 block">Titel *</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              autoFocus
              placeholder="Key Result Titel"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Typ</label>
              <select
                value={form.metric_type}
                onChange={(e) => setForm((f) => ({ ...f, metric_type: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                {KR_METRIC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Zielwert</label>
              <input
                type="number"
                value={form.target_value}
                onChange={(e) => setForm((f) => ({ ...f, target_value: e.target.value }))}
                placeholder="100"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1 block">Einheit</label>
            <input
              type="text"
              value={form.unit}
              onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))}
              placeholder="z.B. kg, km, mal"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={() =>
              onSave({
                title: form.title.trim(),
                metric_type: form.metric_type,
                target_value: form.target_value ? parseFloat(form.target_value) : null,
                unit: form.unit.trim() || null,
              })
            }
            disabled={saving || !form.title.trim()}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium"
          >
            {saving ? "Erstellen…" : "Hinzufügen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditKRModal({
  kr,
  onSave,
  onClose,
  saving,
}: {
  kr: KeyResult;
  onSave: (data: {
    title: string;
    metric_type: string;
    target_value: number | null;
    unit: string | null;
  }) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    title: kr.title,
    metric_type: kr.metric_type,
    target_value: kr.target_value != null ? String(kr.target_value) : "",
    unit: kr.unit ?? "",
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-sm w-full shadow-2xl">
        <h3 className="text-white font-semibold text-base mb-4">Key Result bearbeiten</h3>
        <div className="space-y-3">
          <div>
            <label className="text-zinc-400 text-xs mb-1 block">Titel</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Typ</label>
              <select
                value={form.metric_type}
                onChange={(e) => setForm((f) => ({ ...f, metric_type: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              >
                {KR_METRIC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Zielwert</label>
              <input
                type="number"
                value={form.target_value}
                onChange={(e) => setForm((f) => ({ ...f, target_value: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1 block">Einheit</label>
            <input
              type="text"
              value={form.unit}
              onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))}
              placeholder="z.B. kg, km, mal"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={() =>
              onSave({
                title: form.title.trim(),
                metric_type: form.metric_type,
                target_value: form.target_value ? parseFloat(form.target_value) : null,
                unit: form.unit.trim() || null,
              })
            }
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

// ─── Task Row ─────────────────────────────────────────────────────────────────

function TaskRow({ task }: { task: ObjectiveTask }) {
  const isDone = task.status === "done";
  return (
    <div className="flex items-center gap-2 py-0.5 text-xs">
      <span className={cn("shrink-0", isDone ? "text-green-400" : "text-zinc-600")}>
        {isDone ? "✓" : "○"}
      </span>
      <span className={cn("flex-1 min-w-0 truncate", isDone ? "text-zinc-500 line-through" : "text-zinc-400")}>
        {task.title}
      </span>
      <span className="text-zinc-700 font-mono shrink-0">P{task.priority}</span>
    </div>
  );
}

// ─── Objective Card (within area) ─────────────────────────────────────────────

function AreaObjectiveCard({
  obj,
  onEdit,
  onDelete,
  onAddKR,
  onEditKR,
  onDeleteKR,
}: {
  obj: Objective;
  onEdit: (obj: Objective) => void;
  onDelete: (obj: Objective) => void;
  onAddKR: (obj: Objective) => void;
  onEditKR: (obj: Objective, kr: KeyResult) => void;
  onDeleteKR: (obj: Objective, kr: KeyResult) => void;
}) {
  const [expanded, setExpanded] = useState(
    obj.status === "active" && obj.key_results.length > 0
  );

  const pct = avgProgress(obj);
  const pColor = progressColor(pct);

  // Group tasks by KR
  const tasksByKr: Record<number, ObjectiveTask[]> = {};
  const unlinkedTasks: ObjectiveTask[] = [];
  for (const t of obj.tasks) {
    if (t.key_result_id != null) {
      (tasksByKr[t.key_result_id] ??= []).push(t);
    } else {
      unlinkedTasks.push(t);
    }
  }

  const catColor = CATEGORY_COLORS[obj.category] ?? CATEGORY_COLORS.default;

  return (
    <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg mx-3 mb-2 overflow-hidden group/card">
      {/* Card header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start gap-3 px-4 py-3 hover:bg-zinc-800/70 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span className="text-white font-medium text-sm leading-snug">{obj.title}</span>
            <span
              className={cn(
                "text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0",
                STATUS_STYLE[obj.status] ?? "bg-zinc-800 text-zinc-400"
              )}
            >
              {STATUS_LABEL[obj.status] ?? obj.status}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded-full font-medium border shrink-0"
              style={{
                color: catColor.hex,
                borderColor: catColor.hex + "50",
                backgroundColor: catColor.hex + "15",
              }}
            >
              {obj.category}
            </span>
            {obj.target_date && (
              <span className="text-xs text-zinc-500 shrink-0">
                bis {formatDate(obj.target_date)}
              </span>
            )}
          </div>

          {obj.key_results.length > 0 || obj.tasks.length > 0 ? (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: pColor }}
                />
              </div>
              <span className="text-xs font-medium shrink-0" style={{ color: pColor }}>
                {pct}%
              </span>
            </div>
          ) : (
            <span className="text-xs text-zinc-600 italic">
              Noch keine Key Results oder Tasks
            </span>
          )}
        </div>

        <div className="text-zinc-600 shrink-0 mt-0.5">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </button>

      {/* Expanded: KRs + tasks */}
      {expanded && (
        <div className="border-t border-zinc-700/50">
          {/* Key Results */}
          {obj.key_results.map((kr) => {
            const krTasks = tasksByKr[kr.id] ?? [];
            return (
              <div key={kr.id} className="border-b border-zinc-700/30 last:border-b-0">
                <div className="flex items-center gap-3 px-4 py-2.5 group/kr">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs bg-zinc-700 text-zinc-300 px-1.5 py-0.5 rounded font-medium shrink-0">
                        {KR_TYPE_LABEL[kr.metric_type] ?? kr.metric_type}
                      </span>
                      <span className="text-sm text-zinc-300 truncate">{kr.title}</span>
                      {kr.status === "completed" && (
                        <span className="text-green-400 text-xs shrink-0">✓</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1 bg-zinc-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full transition-all duration-500"
                          style={{ width: `${kr.progress_pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-zinc-500 shrink-0 w-8 text-right">
                        {kr.progress_pct}%
                      </span>
                    </div>
                  </div>

                  <div className="text-right shrink-0 w-20">
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

                  <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover/kr:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditKR(obj, kr);
                      }}
                      className="p-1 rounded text-zinc-600 hover:text-blue-400 transition-colors"
                      title="KR bearbeiten"
                    >
                      <Pencil size={11} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteKR(obj, kr);
                      }}
                      className="p-1 rounded text-zinc-600 hover:text-red-400 transition-colors"
                      title="KR löschen"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                </div>

                {/* Tasks under this KR */}
                {krTasks.length > 0 && (
                  <div className="px-4 pb-2 pl-8 space-y-0.5">
                    {krTasks.map((t) => (
                      <TaskRow key={t.id} task={t} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* Add KR */}
          <div className="px-4 py-2 border-b border-zinc-700/30">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAddKR(obj);
              }}
              className="flex items-center gap-1 text-xs text-zinc-600 hover:text-blue-400 transition-colors"
            >
              <Plus size={11} /> Key Result hinzufügen
            </button>
          </div>

          {/* Unlinked tasks */}
          {unlinkedTasks.length > 0 && (
            <div className="px-4 py-2">
              <div className="text-xs text-zinc-600 font-medium mb-1">Weitere Tasks</div>
              <div className="space-y-0.5 pl-2">
                {unlinkedTasks.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </div>
            </div>
          )}

          {/* Edit / Delete footer */}
          <div className="px-4 py-2 flex items-center justify-end gap-1 border-t border-zinc-700/30 opacity-0 group-hover/card:opacity-100 transition-opacity">
            <span className="text-xs text-zinc-600 mr-auto">
              {obj.key_results.length} KRs
              {obj.tasks.length > 0 &&
                ` · ${obj.tasks.filter((t) => t.status === "done").length}/${obj.tasks.length} Tasks`}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit(obj);
              }}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-zinc-700/50"
            >
              <Pencil size={11} /> Bearbeiten
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(obj);
              }}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-zinc-700/50"
            >
              <Trash2 size={11} /> Löschen
            </button>
          </div>
        </div>
      )}

      {/* When collapsed: edit/delete on hover */}
      {!expanded && (
        <div className="px-4 pb-2 flex justify-end gap-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEdit(obj);
            }}
            className="p-1 rounded text-zinc-600 hover:text-blue-400 transition-colors"
            title="Bearbeiten"
          >
            <Pencil size={12} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(obj);
            }}
            className="p-1 rounded text-zinc-600 hover:text-red-400 transition-colors"
            title="Löschen"
          >
            <Trash2 size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Area Section ─────────────────────────────────────────────────────────────

function AreaSection({
  category,
  objectives,
  allObjectives,
  onEdit,
  onDelete,
  onAddKR,
  onEditKR,
  onDeleteKR,
  onCreateInArea,
}: {
  category: string;
  objectives: Objective[];
  allObjectives: Objective[];
  onEdit: (obj: Objective) => void;
  onDelete: (obj: Objective) => void;
  onAddKR: (obj: Objective) => void;
  onEditKR: (obj: Objective, kr: KeyResult) => void;
  onDeleteKR: (obj: Objective, kr: KeyResult) => void;
  onCreateInArea: (category: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const catColor = CATEGORY_COLORS[category] ?? CATEGORY_COLORS.default;
  const emoji = CATEGORY_EMOJI[category] ?? "🎯";

  const activeCount = objectives.filter((o) => o.status === "active").length;
  const avgPct =
    objectives.length > 0
      ? Math.round(objectives.reduce((s, o) => s + avgProgress(o), 0) / objectives.length)
      : 0;

  const dotClass = momentumDot(avgPct);
  const areaLabel = category.charAt(0).toUpperCase() + category.slice(1);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl mb-4 overflow-hidden">
      {/* Area header bar */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-800/40 transition-colors text-left"
        style={{ borderLeft: `3px solid ${catColor.hex}` }}
      >
        <span className="text-xl shrink-0">{emoji}</span>
        <span className="text-white font-semibold text-sm uppercase tracking-wide">
          {areaLabel}
        </span>
        <span className="text-xs text-zinc-500">
          {objectives.length} Ziel{objectives.length !== 1 ? "e" : ""}
          {activeCount > 0 && ` · ${activeCount} aktiv`}
        </span>

        {/* Momentum dot */}
        <span className={cn("w-2 h-2 rounded-full shrink-0", dotClass)} title={`Avg ${avgPct}%`} />

        {/* Avg progress bar */}
        <div className="flex-1 flex items-center gap-2 min-w-0 max-w-40">
          <div className="flex-1 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${avgPct}%`, backgroundColor: catColor.hex }}
            />
          </div>
          <span className="text-xs text-zinc-500 shrink-0 w-8 text-right">{avgPct}%</span>
        </div>

        <div className="text-zinc-600 shrink-0 ml-1">
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* Objectives in area */}
      {!collapsed && (
        <>
          <div className="pt-2">
            {objectives.map((obj) => (
              <AreaObjectiveCard
                key={obj.id}
                obj={obj}
                onEdit={onEdit}
                onDelete={onDelete}
                onAddKR={onAddKR}
                onEditKR={onEditKR}
                onDeleteKR={onDeleteKR}
              />
            ))}
          </div>

          {/* Footer: add new objective in this area */}
          <div className="px-4 py-3 border-t border-zinc-800">
            <button
              onClick={() => onCreateInArea(category)}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-blue-400 transition-colors"
            >
              <Plus size={12} /> Neues Ziel in {areaLabel}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ObjectivesPage() {
  const { data, error, isLoading, mutate } = useObjectives();
  const [editingObj, setEditingObj] = useState<Objective | null>(null);
  const [deletingObj, setDeletingObj] = useState<Objective | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createCategory, setCreateCategory] = useState<string | undefined>(undefined);
  // KR state
  const [addingKRToObj, setAddingKRToObj] = useState<Objective | null>(null);
  const [editingKR, setEditingKR] = useState<{ obj: Objective; kr: KeyResult } | null>(null);
  const [deletingKR, setDeletingKR] = useState<{ obj: Objective; kr: KeyResult } | null>(null);
  const [krSaving, setKRSaving] = useState(false);
  const [krDeleting, setKRDeleting] = useState(false);
  // Completed/paused section
  const [archivedExpanded, setArchivedExpanded] = useState(false);

  const { toasts, addToast, dismissToast } = useToast();

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleCreate = useCallback(
    async (formData: {
      title: string;
      category: string;
      description: string | null;
      target_date: string | null;
      parent_objective_id: number | null;
    }) => {
      setSaving(true);
      try {
        await api.createObjective(formData);
        await mutate();
        addToast("Objective erstellt", "success");
        setCreating(false);
        setCreateCategory(undefined);
      } catch {
        addToast("Fehler beim Erstellen", "error");
      } finally {
        setSaving(false);
      }
    },
    [mutate, addToast]
  );

  const handleEdit = useCallback(
    async (formData: {
      title: string;
      category: string;
      description: string | null;
      target_date: string | null;
      status: string;
    }) => {
      if (!editingObj) return;
      setSaving(true);
      try {
        await api.updateObjective(editingObj.id, formData);
        await mutate();
        addToast("Objective aktualisiert", "success");
        setEditingObj(null);
      } catch {
        addToast("Fehler beim Speichern", "error");
      } finally {
        setSaving(false);
      }
    },
    [editingObj, mutate, addToast]
  );

  const handleDelete = useCallback(async () => {
    if (!deletingObj) return;
    setDeleting(true);
    mutate(
      (prev) =>
        prev ? { objectives: prev.objectives.filter((o) => o.id !== deletingObj.id) } : prev,
      false
    );
    try {
      await api.deleteObjective(deletingObj.id);
      addToast("Objective gelöscht", "success");
      setDeletingObj(null);
    } catch {
      await mutate();
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
    }
  }, [deletingObj, mutate, addToast]);

  const handleAddKR = useCallback(
    async (formData: {
      title: string;
      metric_type: string;
      target_value: number | null;
      unit: string | null;
    }) => {
      if (!addingKRToObj) return;
      setKRSaving(true);
      try {
        await api.createKeyResult(addingKRToObj.id, formData);
        await mutate();
        addToast("Key Result hinzugefügt", "success");
        setAddingKRToObj(null);
      } catch {
        addToast("Fehler beim Hinzufügen", "error");
      } finally {
        setKRSaving(false);
      }
    },
    [addingKRToObj, mutate, addToast]
  );

  const handleEditKR = useCallback(
    async (formData: {
      title: string;
      metric_type: string;
      target_value: number | null;
      unit: string | null;
    }) => {
      if (!editingKR) return;
      setKRSaving(true);
      try {
        await api.updateKeyResult(editingKR.obj.id, editingKR.kr.id, formData);
        await mutate();
        addToast("Key Result aktualisiert", "success");
        setEditingKR(null);
      } catch {
        addToast("Fehler beim Speichern", "error");
      } finally {
        setKRSaving(false);
      }
    },
    [editingKR, mutate, addToast]
  );

  const handleDeleteKR = useCallback(async () => {
    if (!deletingKR) return;
    setKRDeleting(true);
    try {
      await api.deleteKeyResult(deletingKR.obj.id, deletingKR.kr.id);
      await mutate();
      addToast("Key Result gelöscht", "success");
      setDeletingKR(null);
    } catch {
      addToast("Fehler beim Löschen", "error");
    } finally {
      setKRDeleting(false);
    }
  }, [deletingKR, mutate, addToast]);

  // ── Data ──────────────────────────────────────────────────────────────────

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  const all = data?.objectives ?? [];
  // Keep objectiveMap for reference (mirrors structure expected by analysis page)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const objectiveMap = new Map(all.map((o) => [o.id, o.title]));

  const activeObjs = all.filter((o) => o.status === "active");
  const archivedObjs = all.filter((o) => o.status !== "active");

  // Group active objectives by category, preserving a canonical order
  const AREA_ORDER = ["health", "fitness", "business", "finance", "learning", "relationships", "personal"];
  const grouped = new Map<string, Objective[]>();
  for (const cat of AREA_ORDER) grouped.set(cat, []);

  for (const obj of activeObjs) {
    const key = AREA_ORDER.includes(obj.category) ? obj.category : "__other__";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(obj);
  }

  // Also collect uncategorized / unknown categories
  const otherObjs: Objective[] = grouped.get("__other__") ?? [];

  const counts = {
    active: activeObjs.length,
    archived: archivedObjs.length,
  };

  return (
    <div>
      <Header
        title="🎯 Objectives"
        subtitle={`${counts.active} aktiv · ${counts.archived} archiviert`}
        action={
          <div className="flex items-center gap-2">
            <Link
              href="/objectives/analysis"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-300 text-sm font-medium hover:bg-zinc-700 transition-colors"
            >
              🔍 Zielanalyse
            </Link>
            <button
              onClick={() => {
                setCreateCategory(undefined);
                setCreating(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors"
            >
              <Plus size={14} /> Neues Objective
            </button>
          </div>
        }
      />

      {/* Empty state */}
      {all.length === 0 && (
        <EmptyState emoji="🎯" message="Noch keine Objectives — leg dein erstes an!" />
      )}

      {/* Area sections for active objectives */}
      {AREA_ORDER.map((cat) => {
        const objs = grouped.get(cat) ?? [];
        if (objs.length === 0) return null;
        return (
          <AreaSection
            key={cat}
            category={cat}
            objectives={objs}
            allObjectives={all}
            onEdit={setEditingObj}
            onDelete={setDeletingObj}
            onAddKR={setAddingKRToObj}
            onEditKR={(obj, kr) => setEditingKR({ obj, kr })}
            onDeleteKR={(obj, kr) => setDeletingKR({ obj, kr })}
            onCreateInArea={(category) => {
              setCreateCategory(category);
              setCreating(true);
            }}
          />
        );
      })}

      {/* Uncategorized active objectives */}
      {otherObjs.length > 0 && (
        <AreaSection
          category="personal"
          objectives={otherObjs}
          allObjectives={all}
          onEdit={setEditingObj}
          onDelete={setDeletingObj}
          onAddKR={setAddingKRToObj}
          onEditKR={(obj, kr) => setEditingKR({ obj, kr })}
          onDeleteKR={(obj, kr) => setDeletingKR({ obj, kr })}
          onCreateInArea={(category) => {
            setCreateCategory(category);
            setCreating(true);
          }}
        />
      )}

      {/* Archived / completed / paused */}
      {archivedObjs.length > 0 && (
        <div className="mt-6">
          <button
            onClick={() => setArchivedExpanded((v) => !v)}
            className="flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-3"
          >
            {archivedExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Archivierte Ziele ({archivedObjs.length})
          </button>

          {archivedExpanded && (
            <div className="space-y-2">
              {archivedObjs.map((obj) => (
                <AreaObjectiveCard
                  key={obj.id}
                  obj={obj}
                  onEdit={setEditingObj}
                  onDelete={setDeletingObj}
                  onAddKR={setAddingKRToObj}
                  onEditKR={(o, kr) => setEditingKR({ obj: o, kr })}
                  onDeleteKR={(o, kr) => setDeletingKR({ obj: o, kr })}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Modals ── */}

      {creating && (
        <CreateObjectiveModal
          onSave={handleCreate}
          onClose={() => {
            setCreating(false);
            setCreateCategory(undefined);
          }}
          saving={saving}
          allObjectives={all}
          defaultCategory={createCategory}
        />
      )}

      {editingObj && (
        <EditObjectiveModal
          obj={editingObj}
          onSave={handleEdit}
          onClose={() => setEditingObj(null)}
          saving={saving}
        />
      )}

      <ConfirmDialog
        open={!!deletingObj}
        title="Objective löschen?"
        message={`"${deletingObj?.title}" wird dauerhaft gelöscht — inklusive aller Key Results und verknüpften Tasks.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingObj(null)}
      />

      {addingKRToObj && (
        <AddKRModal
          onSave={handleAddKR}
          onClose={() => setAddingKRToObj(null)}
          saving={krSaving}
        />
      )}

      {editingKR && (
        <EditKRModal
          kr={editingKR.kr}
          onSave={handleEditKR}
          onClose={() => setEditingKR(null)}
          saving={krSaving}
        />
      )}

      <ConfirmDialog
        open={!!deletingKR}
        title="Key Result löschen?"
        message={`"${deletingKR?.kr.title}" wird dauerhaft gelöscht.`}
        loading={krDeleting}
        onConfirm={handleDeleteKR}
        onCancel={() => setDeletingKR(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
