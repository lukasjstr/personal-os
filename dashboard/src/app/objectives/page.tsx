"use client";

import React, { useState, useCallback } from "react";
import Link from "next/link";
import useSWR from "swr";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useObjectives } from "@/hooks/useApi";
import { CATEGORY_EMOJI, CATEGORY_COLORS, formatDate, cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { Objective, ObjectiveTask, KeyResult, GoalMomentumResponse, NodeRelation } from "@/lib/api";
import { ChevronDown, ChevronRight, Pencil, Plus, Trash2, GitBranch, Sparkles, Check, X } from "lucide-react";
import type { ObjectiveAnalysis } from "@/lib/api";

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

// ─── Edit Modal ───────────────────────────────────────────────────────────────

function CreateObjectiveModal({
  onSave,
  onClose,
  saving,
  allObjectives = [],
  defaultParentId,
}: {
  onSave: (data: { title: string; category: string; description: string | null; target_date: string | null; parent_objective_id: number | null }) => void;
  onClose: () => void;
  saving: boolean;
  allObjectives?: Objective[];
  defaultParentId?: number;
}) {
  const [form, setForm] = useState({ title: "", category: "personal", description: "", target_date: "", parent_objective_id: defaultParentId ? String(defaultParentId) : "" });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl p-6 max-w-md w-full shadow-2xl">
        <h3 className="text-white font-semibold text-lg mb-5">Neues Objective</h3>
        <div className="space-y-4">
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Titel *</label>
            <input type="text" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Objective-Titel" autoFocus className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          {allObjectives.length > 0 && (
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Übergeordnetes Ziel (optional)</label>
              <select value={form.parent_objective_id} onChange={(e) => setForm((f) => ({ ...f, parent_objective_id: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                <option value="">— Kein übergeordnetes Ziel —</option>
                {allObjectives.filter((o) => o.status === "active").map((o) => <option key={o.id} value={String(o.id)}>{CATEGORY_EMOJI[o.category] ?? "🎯"} {o.title}</option>)}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Kategorie</label>
              <select value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_EMOJI[c] ?? "🎯"} {c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">Zieldatum</label>
              <input type="date" value={form.target_date} onChange={(e) => setForm((f) => ({ ...f, target_date: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1.5 block">Beschreibung</label>
            <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none" />
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-6">
          <button onClick={onClose} disabled={saving} className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors">Abbrechen</button>
          <button onClick={() => onSave({ title: form.title.trim(), category: form.category, description: form.description.trim() || null, target_date: form.target_date || null, parent_objective_id: form.parent_objective_id ? parseInt(form.parent_objective_id) : null })} disabled={saving || !form.title.trim()} className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium">
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

  function handleSave() {
    onSave({
      title: form.title.trim(),
      category: form.category,
      description: form.description.trim() || null,
      target_date: form.target_date || null,
      status: form.status,
    });
  }

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

// ─── KR Modals ────────────────────────────────────────────────────────────────

const KR_METRIC_TYPES = ["number", "percentage", "boolean", "streak", "checklist"];

function AddKRModal({
  onSave,
  onClose,
  saving,
}: {
  onSave: (data: { title: string; metric_type: string; target_value: number | null; unit: string | null }) => void;
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
            <input type="text" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} autoFocus placeholder="Key Result Titel" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Typ</label>
              <select value={form.metric_type} onChange={(e) => setForm((f) => ({ ...f, metric_type: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                {KR_METRIC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Zielwert</label>
              <input type="number" value={form.target_value} onChange={(e) => setForm((f) => ({ ...f, target_value: e.target.value }))} placeholder="100" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1 block">Einheit</label>
            <input type="text" value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} placeholder="z.B. kg, km, mal" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button onClick={onClose} disabled={saving} className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors">Abbrechen</button>
          <button onClick={() => onSave({ title: form.title.trim(), metric_type: form.metric_type, target_value: form.target_value ? parseFloat(form.target_value) : null, unit: form.unit.trim() || null })} disabled={saving || !form.title.trim()} className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium">
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
  onSave: (data: { title: string; metric_type: string; target_value: number | null; unit: string | null }) => void;
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
            <input type="text" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Typ</label>
              <select value={form.metric_type} onChange={(e) => setForm((f) => ({ ...f, metric_type: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                {KR_METRIC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Zielwert</label>
              <input type="number" value={form.target_value} onChange={(e) => setForm((f) => ({ ...f, target_value: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
          </div>
          <div>
            <label className="text-zinc-400 text-xs mb-1 block">Einheit</label>
            <input type="text" value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} placeholder="z.B. kg, km, mal" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button onClick={onClose} disabled={saving} className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors">Abbrechen</button>
          <button onClick={() => onSave({ title: form.title.trim(), metric_type: form.metric_type, target_value: form.target_value ? parseFloat(form.target_value) : null, unit: form.unit.trim() || null })} disabled={saving || !form.title.trim()} className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 text-sm transition-colors disabled:opacity-50 font-medium">
            {saving ? "Speichern…" : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Task Checklist ───────────────────────────────────────────────────────────

function TaskRow({ task }: { task: ObjectiveTask }) {
  const isDone = task.status === "done";
  return (
    <div className="flex items-center gap-2 py-1 text-sm">
      <span className={cn("shrink-0 text-xs", isDone ? "text-green-400" : "text-zinc-600")}>
        {isDone ? "✓" : "○"}
      </span>
      <span className={cn("flex-1 min-w-0 truncate", isDone ? "text-zinc-500 line-through" : "text-zinc-300")}>
        {task.title}
      </span>
      <span className="text-zinc-700 text-xs font-mono shrink-0">P{task.priority}</span>
    </div>
  );
}

function TaskChecklist({ tasks, keyResults }: { tasks: ObjectiveTask[]; keyResults: { id: number; title: string }[] }) {
  if (tasks.length === 0) return null;

  // Group tasks by key_result_id
  const byKr: Record<number, ObjectiveTask[]> = {};
  const unlinked: ObjectiveTask[] = [];
  for (const t of tasks) {
    if (t.key_result_id != null) {
      (byKr[t.key_result_id] ??= []).push(t);
    } else {
      unlinked.push(t);
    }
  }

  const krMap = Object.fromEntries(keyResults.map((kr) => [kr.id, kr.title]));
  const hasGroups = Object.keys(byKr).length > 0;

  if (!hasGroups) {
    // No KR linkage — flat list
    return (
      <div className="px-5 py-3 border-t border-zinc-800 space-y-0.5">
        <div className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-2">Tasks</div>
        {tasks.map((t) => <TaskRow key={t.id} task={t} />)}
      </div>
    );
  }

  return (
    <div className="border-t border-zinc-800">
      {Object.entries(byKr).map(([krId, krTasks]) => (
        <div key={krId} className="px-5 py-2 border-b border-zinc-800/50 last:border-b-0">
          <div className="text-xs text-blue-400/80 font-medium mb-1.5 flex items-center gap-1">
            <span className="text-zinc-600">↳</span>
            {krMap[Number(krId)] ?? "Key Result"}
          </div>
          <div className="space-y-0.5 pl-3">
            {krTasks.map((t) => <TaskRow key={t.id} task={t} />)}
          </div>
        </div>
      ))}
      {unlinked.length > 0 && (
        <div className="px-5 py-2">
          <div className="text-xs text-zinc-600 font-medium mb-1.5">Weitere Tasks</div>
          <div className="space-y-0.5 pl-3">
            {unlinked.map((t) => <TaskRow key={t.id} task={t} />)}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Objective Card ───────────────────────────────────────────────────────────

function objRelationChips(relations: NodeRelation[], objId: number, objectiveMap: Map<number, string>): React.ReactNode[] {
  const chips: React.ReactNode[] = [];
  for (const rel of relations) {
    if (rel.relation_type === "blocks" && rel.to_type === "objective" && rel.to_id === objId) {
      const title = objectiveMap.get(rel.from_id) ?? `#${rel.from_id}`;
      chips.push(
        <span key={`bl-${rel.id}`} className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-red-900/30 text-red-400 border border-red-800/40">
          🔒 blocked by: {title.length > 28 ? title.slice(0, 28) + "…" : title}
        </span>
      );
    }
    if (rel.relation_type === "depends_on" && rel.from_type === "objective" && rel.from_id === objId) {
      const title = objectiveMap.get(rel.to_id) ?? `#${rel.to_id}`;
      chips.push(
        <span key={`dep-${rel.id}`} className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-red-900/30 text-red-400 border border-red-800/40">
          ⬆ needs: {title.length > 28 ? title.slice(0, 28) + "…" : title}
        </span>
      );
    }
    if (rel.relation_type === "blocks" && rel.from_type === "objective" && rel.from_id === objId) {
      const title = objectiveMap.get(rel.to_id) ?? `#${rel.to_id}`;
      chips.push(
        <span key={`blk-${rel.id}`} className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-orange-900/30 text-orange-400 border border-orange-800/40">
          → blocks: {title.length > 28 ? title.slice(0, 28) + "…" : title}
        </span>
      );
    }
    if (rel.relation_type === "unlocks" && rel.from_id === objId) {
      const title = rel.to_type === "objective" ? (objectiveMap.get(rel.to_id) ?? `#${rel.to_id}`) : `${rel.to_type} #${rel.to_id}`;
      chips.push(
        <span key={`ul-${rel.id}`} className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-green-900/30 text-green-400 border border-green-800/40">
          🔓 unlocks: {title.length > 28 ? title.slice(0, 28) + "…" : title}
        </span>
      );
    }
    if (rel.relation_type === "contributes_to" && rel.from_id === objId) {
      const title = rel.to_type === "objective" ? (objectiveMap.get(rel.to_id) ?? `obj #${rel.to_id}`) : `${rel.to_type} #${rel.to_id}`;
      chips.push(
        <span key={`ct-${rel.id}`} className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-purple-900/40 text-purple-300 border border-purple-700/40">
          ↑ {title.length > 30 ? title.slice(0, 30) + "…" : title}
        </span>
      );
    }
  }
  return chips;
}

function ObjectiveCard({
  obj,
  objectiveMap,
  onEdit,
  onDelete,
  onAddKR,
  onEditKR,
  onDeleteKR,
}: {
  obj: Objective;
  objectiveMap: Map<number, string>;
  onEdit: (obj: Objective) => void;
  onDelete: (obj: Objective) => void;
  onAddKR: (obj: Objective) => void;
  onEditKR: (obj: Objective, kr: KeyResult) => void;
  onDeleteKR: (obj: Objective, kr: KeyResult) => void;
}) {
  const [expanded, setExpanded] = useState(obj.status === "active");
  const isLifeArea = obj.key_results.length === 0 && obj.tasks.length === 0;
  const catColor = CATEGORY_COLORS[obj.category] ?? CATEGORY_COLORS.default;

  const krProgress =
    obj.key_results.length > 0
      ? Math.round(
          obj.key_results.reduce((s, kr) => s + kr.progress_pct, 0) / obj.key_results.length
        )
      : null;

  const taskProgress =
    obj.tasks.length > 0
      ? Math.round((obj.tasks.filter((t) => t.status === "done").length / obj.tasks.length) * 100)
      : null;

  const avgProgress = krProgress ?? taskProgress ?? 0;

  const progressColor =
    avgProgress >= 75 ? "#22c55e" : avgProgress >= 40 ? "#3b82f6" : avgProgress >= 20 ? "#f59e0b" : "#ef4444";

  // Container objectives (no KRs/tasks yet) still render as full cards, just with a different body


  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden flex">
      <div className="w-1 shrink-0" style={{ backgroundColor: catColor.hex }} />

      <div className="flex-1 min-w-0">
        {/* Header */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-4 p-5 hover:bg-zinc-800/40 transition-colors text-left"
        >
          <span className="text-2xl shrink-0">{CATEGORY_EMOJI[obj.category] ?? "🎯"}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <h3 className="font-semibold text-white">{obj.title}</h3>
              <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", STATUS_STYLE[obj.status] ?? "bg-zinc-800 text-zinc-400")}>
                {STATUS_LABEL[obj.status] ?? obj.status}
              </span>
              <span
                className="text-xs px-2 py-0.5 rounded-full font-medium border"
                style={{ color: catColor.hex, borderColor: catColor.hex + "50", backgroundColor: catColor.hex + "15" }}
              >
                {obj.category}
              </span>
            </div>
            {obj.description && (
              <p className="text-zinc-500 text-xs truncate">{obj.description}</p>
            )}
            {obj.relations && obj.relations.length > 0 && (() => {
              const chips = objRelationChips(obj.relations, obj.id, objectiveMap);
              return chips.length > 0 ? (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {chips}
                </div>
              ) : null;
            })()}
            {isLifeArea ? (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-zinc-500 italic">Übergeordnetes Ziel — füge Key Results oder Unterziele hinzu</span>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3 mt-2">
                  <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${avgProgress}%`, backgroundColor: progressColor }}
                    />
                  </div>
                  <span className="text-xs font-medium shrink-0" style={{ color: progressColor }}>
                    {avgProgress}%
                  </span>
                </div>
                {krProgress !== null && taskProgress !== null && (
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-zinc-600 shrink-0 w-6">T</span>
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-zinc-500 rounded-full transition-all duration-500"
                        style={{ width: `${taskProgress}%` }}
                      />
                    </div>
                    <span className="text-xs text-zinc-500 shrink-0">{taskProgress}%</span>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="text-zinc-500 shrink-0">
            {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </div>
        </button>

        {/* Key Results */}
        {expanded && (
          <div className="border-t border-zinc-800 divide-y divide-zinc-800/50">
            {obj.key_results.map((kr) => (
              <div key={kr.id} className="px-5 py-3 flex items-center gap-4 group/kr">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                      {KR_TYPE_LABEL[kr.metric_type] ?? kr.metric_type}
                    </span>
                    <span className="text-sm text-zinc-300">{kr.title}</span>
                    {kr.status === "completed" && <span className="text-green-400 text-xs">✓ Done</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all duration-500"
                        style={{ width: `${kr.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-zinc-400 shrink-0">{kr.progress_pct}%</span>
                  </div>
                </div>
                <div className="text-right shrink-0 w-24">
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
                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover/kr:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.stopPropagation(); onEditKR(obj, kr); }}
                    className="p-1 rounded text-zinc-500 hover:text-blue-400 transition-colors"
                    title="Bearbeiten"
                  >
                    <Pencil size={12} />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDeleteKR(obj, kr); }}
                    className="p-1 rounded text-zinc-500 hover:text-red-400 transition-colors"
                    title="Löschen"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
            {/* Add KR button */}
            <div className="px-5 py-2">
              <button
                onClick={(e) => { e.stopPropagation(); onAddKR(obj); }}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-blue-400 transition-colors"
              >
                <Plus size={12} /> Key Result hinzufügen
              </button>
            </div>
          </div>
        )}

        {/* Task Checklist */}
        {expanded && obj.tasks.length > 0 && <TaskChecklist tasks={obj.tasks} keyResults={obj.key_results} />}

        {/* Footer */}
        <div className="border-t border-zinc-800 px-5 py-2 flex items-center gap-4 text-xs text-zinc-500">
          <span>{obj.key_results.length} KRs</span>
          {obj.tasks.length > 0 && (
            <span>
              {obj.tasks.filter((t) => t.status === "done").length}/{obj.tasks.length} Tasks
            </span>
          )}
          {obj.target_date && <span>📅 bis {formatDate(obj.target_date)}</span>}
          <span className="ml-auto">erstellt {formatDate(obj.created_at)}</span>
          <button
            onClick={() => onEdit(obj)}
            className="text-zinc-600 hover:text-blue-400 transition-colors p-1 rounded"
            title="Bearbeiten"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(obj)}
            className="text-zinc-600 hover:text-red-400 transition-colors p-1 rounded"
            title="Löschen"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const FILTERS = ["all", "active", "completed", "paused", "abandoned"] as const;
const FILTER_LABELS: Record<string, string> = {
  all: "Alle",
  active: "Aktiv",
  completed: "Abgeschlossen",
  paused: "Pausiert",
  abandoned: "Aufgegeben",
};

const MOMENTUM_COLOR: Record<string, string> = {
  high: "text-emerald-400",
  medium: "text-yellow-400",
  low: "text-red-400",
};

// ─── AI Goal Analysis Panel ───────────────────────────────────────────────────

function AiAnalysisPanel({ onApplyParent }: { onApplyParent: (childId: number, parentId: number) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<ObjectiveAnalysis | null>(null);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const [applying, setApplying] = useState<number | null>(null);

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const result = await api.analyzeObjectives();
      setAnalysis(result);
      setOpen(true);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async (childId: number, parentId: number, idx: number) => {
    setApplying(idx);
    try {
      await onApplyParent(childId, parentId);
      setDismissed((prev) => new Set([...prev, idx]));
    } finally {
      setApplying(null);
    }
  };

  const visibleSuggestions = analysis?.parent_suggestions.filter((_, i) => !dismissed.has(i)) ?? [];

  return (
    <div className="bg-zinc-900 border border-indigo-900/40 rounded-xl overflow-hidden mb-6">
      <button
        onClick={() => (analysis ? setOpen((v) => !v) : runAnalysis())}
        disabled={loading}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-indigo-400" />
          <span className="text-white font-semibold text-sm">KI-Zielanalyse</span>
          {analysis && (
            <span className="text-xs text-indigo-400 bg-indigo-900/30 px-2 py-0.5 rounded-full">
              {visibleSuggestions.length} Vorschläge
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {loading && <span className="text-zinc-500 text-xs">Analysiere…</span>}
          {!analysis && !loading && <span className="text-indigo-400 text-xs">Analyse starten →</span>}
          {analysis && <span className="text-zinc-500 text-xs">{open ? "▲" : "▼"}</span>}
        </div>
      </button>

      {open && analysis && (
        <div className="border-t border-zinc-800 px-5 py-4 space-y-5">
          {/* Summary */}
          <div className="bg-indigo-950/30 border border-indigo-800/30 rounded-lg px-4 py-3">
            <p className="text-indigo-200 text-sm">{analysis.summary}</p>
          </div>

          {/* Hierarchy suggestions */}
          {visibleSuggestions.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <GitBranch size={14} className="text-blue-400" />
                <span className="text-blue-400 text-xs font-semibold uppercase tracking-wider">Hierarchie-Vorschläge</span>
              </div>
              <div className="space-y-2">
                {analysis.parent_suggestions.map((s, i) => dismissed.has(i) ? null : (
                  <div key={i} className="bg-zinc-800 rounded-lg px-4 py-3 flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-white text-sm font-medium truncate">
                        <span className="text-zinc-400">{s.child_title}</span>
                        <span className="text-zinc-600 mx-2">→</span>
                        <span className="text-blue-300">Unterziel von:</span>
                        <span className="text-white ml-1">{s.parent_title}</span>
                      </div>
                      <p className="text-zinc-500 text-xs mt-1">{s.reason}</p>
                    </div>
                    <div className="flex gap-1.5 shrink-0">
                      <button
                        onClick={() => handleApply(s.child_objective_id, s.suggested_parent_id, i)}
                        disabled={applying === i}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-500 transition-colors disabled:opacity-40"
                      >
                        <Check size={12} />
                        {applying === i ? "…" : "Übernehmen"}
                      </button>
                      <button
                        onClick={() => setDismissed((prev) => new Set([...prev, i]))}
                        className="p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-700 transition-colors"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Synergies */}
          {analysis.synergies.length > 0 && (
            <div>
              <div className="text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-2">✨ Synergien</div>
              <div className="space-y-1.5">
                {analysis.synergies.map((s, i) => (
                  <div key={i} className="bg-emerald-950/30 border border-emerald-800/20 rounded-lg px-3 py-2">
                    <div className="text-emerald-300 text-xs font-medium">{s.titles.join(" + ")}</div>
                    <div className="text-zinc-400 text-xs mt-0.5">{s.synergy}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Overlaps */}
          {analysis.overlaps.length > 0 && (
            <div>
              <div className="text-yellow-400 text-xs font-semibold uppercase tracking-wider mb-2">⚠️ Überlappungen</div>
              <div className="space-y-1.5">
                {analysis.overlaps.map((s, i) => (
                  <div key={i} className="bg-yellow-950/30 border border-yellow-800/20 rounded-lg px-3 py-2">
                    <div className="text-yellow-300 text-xs font-medium">{s.titles.join(" & ")}</div>
                    <div className="text-zinc-400 text-xs mt-0.5">{s.overlap}</div>
                    <div className="text-yellow-600 text-xs mt-1">💡 {s.suggestion}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Refresh */}
          <button
            onClick={runAnalysis}
            disabled={loading}
            className="text-xs text-zinc-500 hover:text-indigo-400 transition-colors"
          >
            {loading ? "Analysiere…" : "↻ Erneut analysieren"}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Tree View ────────────────────────────────────────────────────────────────

function buildTree(objectives: Objective[]): { roots: Objective[]; childMap: Map<number, Objective[]> } {
  const childMap = new Map<number, Objective[]>();
  const roots: Objective[] = [];
  for (const obj of objectives) {
    if (obj.parent_objective_id) {
      const arr = childMap.get(obj.parent_objective_id) ?? [];
      arr.push(obj);
      childMap.set(obj.parent_objective_id, arr);
    } else {
      roots.push(obj);
    }
  }
  return { roots, childMap };
}

function ObjectiveTreeNode({
  obj,
  childMap,
  depth,
  objectiveMap,
  onEdit,
  onDelete,
  onAddKR,
  onEditKR,
  onDeleteKR,
  onAddChild,
}: {
  obj: Objective;
  childMap: Map<number, Objective[]>;
  depth: number;
  objectiveMap: Map<number, string>;
  onEdit: (obj: Objective) => void;
  onDelete: (obj: Objective) => void;
  onAddKR: (obj: Objective) => void;
  onEditKR: (obj: Objective, kr: KeyResult) => void;
  onDeleteKR: (obj: Objective, kr: KeyResult) => void;
  onAddChild: (parentId: number) => void;
}) {
  const children = childMap.get(obj.id) ?? [];
  const hasChildren = children.length > 0;

  return (
    <div className={cn(depth > 0 && "ml-6 border-l-2 border-zinc-700/50 pl-4")}>
      <ObjectiveCard
        obj={obj}
        objectiveMap={objectiveMap}
        onEdit={onEdit}
        onDelete={onDelete}
        onAddKR={onAddKR}
        onEditKR={onEditKR}
        onDeleteKR={onDeleteKR}
      />
      {/* Add sub-objective button */}
      <div className="ml-2 mt-1 mb-3">
        <button
          onClick={() => onAddChild(obj.id)}
          className="flex items-center gap-1 text-xs text-zinc-600 hover:text-blue-400 transition-colors"
        >
          <Plus size={10} /> Unterziel hinzufügen
        </button>
      </div>
      {hasChildren && (
        <div className="space-y-4 mb-2">
          {children.map((child) => (
            <ObjectiveTreeNode
              key={child.id}
              obj={child}
              childMap={childMap}
              depth={depth + 1}
              objectiveMap={objectiveMap}
              onEdit={onEdit}
              onDelete={onDelete}
              onAddKR={onAddKR}
              onEditKR={onEditKR}
              onDeleteKR={onDeleteKR}
              onAddChild={onAddChild}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ObjectivesPage() {
  const { data, error, isLoading, mutate } = useObjectives();
  const { data: momentumData } = useSWR<GoalMomentumResponse>("goal-momentum", api.goalMomentum, { refreshInterval: 300_000 });
  const [filter, setFilter] = useState<string>("all");
  const [creating, setCreating] = useState(false);
  const [createParentId, setCreateParentId] = useState<number | undefined>(undefined);
  const [viewMode, setViewMode] = useState<"tree" | "list">("tree");
  const [editingObj, setEditingObj] = useState<Objective | null>(null);
  const [deletingObj, setDeletingObj] = useState<Objective | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // KR state
  const [addingKRToObj, setAddingKRToObj] = useState<Objective | null>(null);
  const [editingKR, setEditingKR] = useState<{ obj: Objective; kr: KeyResult } | null>(null);
  const [deletingKR, setDeletingKR] = useState<{ obj: Objective; kr: KeyResult } | null>(null);
  const [krSaving, setKRSaving] = useState(false);
  const [krDeleting, setKRDeleting] = useState(false);
  const { toasts, addToast, dismissToast } = useToast();

  const handleCreate = useCallback(
    async (data: { title: string; category: string; description: string | null; target_date: string | null; parent_objective_id: number | null }) => {
      setSaving(true);
      try {
        await api.createObjective(data);
        await mutate();
        addToast("Objective erstellt", "success");
        setCreating(false);
        setCreateParentId(undefined);
      } catch {
        addToast("Fehler beim Erstellen", "error");
      } finally {
        setSaving(false);
      }
    },
    [mutate, addToast]
  );

  const handleApplyParent = useCallback(async (childId: number, parentId: number) => {
    try {
      await api.setObjectiveParent(childId, parentId);
      await mutate();
      addToast("Hierarchie aktualisiert ✓", "success");
    } catch {
      addToast("Fehler beim Zuordnen", "error");
    }
  }, [mutate, addToast]);

  const handleEdit = useCallback(
    async (data: {
      title: string;
      category: string;
      description: string | null;
      target_date: string | null;
      status: string;
    }) => {
      if (!editingObj) return;
      setSaving(true);
      try {
        await api.updateObjective(editingObj.id, data);
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
    // Optimistic update
    mutate(
      (prev) =>
        prev
          ? { objectives: prev.objectives.filter((o) => o.id !== deletingObj.id) }
          : prev,
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
    async (data: { title: string; metric_type: string; target_value: number | null; unit: string | null }) => {
      if (!addingKRToObj) return;
      setKRSaving(true);
      try {
        await api.createKeyResult(addingKRToObj.id, data);
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
    async (data: { title: string; metric_type: string; target_value: number | null; unit: string | null }) => {
      if (!editingKR) return;
      setKRSaving(true);
      try {
        await api.updateKeyResult(editingKR.obj.id, editingKR.kr.id, data);
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

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  const all = data?.objectives ?? [];
  const objectiveMap = new Map(all.map((o) => [o.id, o.title]));
  // Build full tree from ALL objectives (not just those with KRs/tasks)
  const { roots: allRoots, childMap } = buildTree(all);
  // Filter which root objectives to show, but children always inherit
  const filteredRoots = filter === "all" ? allRoots : allRoots.filter((o) => o.status === filter);
  // For list view, show flat filtered list
  const filtered = filter === "all" ? all : all.filter((o) => o.status === filter);

  const counts = {
    all: all.length,
    active: all.filter((o) => o.status === "active").length,
    completed: all.filter((o) => o.status === "completed").length,
    paused: all.filter((o) => o.status === "paused").length,
    abandoned: all.filter((o) => o.status === "abandoned").length,
  };

  return (
    <div>
      <Header
        title="🎯 Objectives"
        subtitle={`${counts.active} aktiv · ${counts.completed} abgeschlossen`}
        action={
          <div className="flex items-center gap-2">
            <Link
              href="/objectives/analysis"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-300 text-sm font-medium hover:bg-zinc-700 transition-colors"
            >
              🔍 Zielanalyse
            </Link>
            <button onClick={() => setCreating(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors">
              <Plus size={14} /> Neues Objective
            </button>
          </div>
        }
      />

      {/* Goal Momentum (F3) */}
      {momentumData && momentumData.objectives.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-white font-semibold text-sm">Momentum</span>
            <div className="flex items-center gap-1.5">
              <span className={cn("font-bold text-sm", MOMENTUM_COLOR[momentumData.portfolio_level])}>
                {momentumData.portfolio_momentum}
              </span>
              <span className="text-zinc-600 text-xs">/100 Portfolio</span>
            </div>
          </div>
          <div className="space-y-2">
            {momentumData.objectives.slice(0, 4).map((obj) => (
              <div key={obj.id} className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-zinc-400 text-xs truncate">{obj.title}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="w-20 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        obj.level === "high" ? "bg-emerald-500" :
                        obj.level === "medium" ? "bg-yellow-500" : "bg-red-500"
                      )}
                      style={{ width: `${obj.momentum}%` }}
                    />
                  </div>
                  <span className={cn("text-xs w-6 text-right", MOMENTUM_COLOR[obj.level])}>{obj.momentum}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Analysis Panel */}
      <AiAnalysisPanel onApplyParent={handleApplyParent} />

      {/* Filter + View Toggle */}
      <div className="flex gap-2 mb-6 flex-wrap items-center">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm transition-colors",
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            )}
          >
            {FILTER_LABELS[f]} ({counts[f as keyof typeof counts] ?? 0})
          </button>
        ))}
        <div className="ml-auto flex gap-1 bg-zinc-800 rounded-lg p-1">
          <button onClick={() => setViewMode("tree")} className={cn("px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1", viewMode === "tree" ? "bg-zinc-600 text-white" : "text-zinc-400 hover:text-white")}>
            <GitBranch size={12} /> Baum
          </button>
          <button onClick={() => setViewMode("list")} className={cn("px-2.5 py-1 rounded text-xs transition-colors", viewMode === "list" ? "bg-zinc-600 text-white" : "text-zinc-400 hover:text-white")}>
            Liste
          </button>
        </div>
      </div>

      {/* Objectives — Tree or List */}
      {all.length === 0 ? (
        <EmptyState emoji="🎯" message="Noch keine Objectives — leg dein erstes an!" />
      ) : viewMode === "tree" ? (
        filteredRoots.length === 0 ? (
          <EmptyState emoji="🎯" message="Keine Objectives gefunden" />
        ) : (
        <div className="space-y-4">
          {filteredRoots.map((obj) => (
            <ObjectiveTreeNode
              key={obj.id}
              obj={obj}
              childMap={childMap}
              depth={0}
              objectiveMap={objectiveMap}
              onEdit={setEditingObj}
              onDelete={setDeletingObj}
              onAddKR={setAddingKRToObj}
              onEditKR={(obj, kr) => setEditingKR({ obj, kr })}
              onDeleteKR={(obj, kr) => setDeletingKR({ obj, kr })}
              onAddChild={(parentId) => { setCreateParentId(parentId); setCreating(true); }}
            />
          ))}
        </div>
        )
      ) : (
        <div className="space-y-4">
          {filtered.map((obj) => (
            <ObjectiveCard
              key={obj.id}
              obj={obj}
              objectiveMap={objectiveMap}
              onEdit={setEditingObj}
              onDelete={setDeletingObj}
              onAddKR={setAddingKRToObj}
              onEditKR={(obj, kr) => setEditingKR({ obj, kr })}
              onDeleteKR={(obj, kr) => setDeletingKR({ obj, kr })}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {creating && (
        <CreateObjectiveModal
          onSave={handleCreate}
          onClose={() => { setCreating(false); setCreateParentId(undefined); }}
          saving={saving}
          allObjectives={all}
          defaultParentId={createParentId}
        />
      )}

      {/* Edit Modal */}
      {editingObj && (
        <EditObjectiveModal
          obj={editingObj}
          onSave={handleEdit}
          onClose={() => setEditingObj(null)}
          saving={saving}
        />
      )}

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deletingObj}
        title="Objective löschen?"
        message={`"${deletingObj?.title}" wird dauerhaft gelöscht — inklusive aller Key Results und verknüpften Tasks.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingObj(null)}
      />

      {/* Add KR Modal */}
      {addingKRToObj && (
        <AddKRModal
          onSave={handleAddKR}
          onClose={() => setAddingKRToObj(null)}
          saving={krSaving}
        />
      )}

      {/* Edit KR Modal */}
      {editingKR && (
        <EditKRModal
          kr={editingKR.kr}
          onSave={handleEditKR}
          onClose={() => setEditingKR(null)}
          saving={krSaving}
        />
      )}

      {/* Delete KR Confirm */}
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
