"use client";

import { useState, useEffect, useCallback } from "react";
import { Zap, Plus, Trash2, ToggleLeft, ToggleRight, Play, ChevronDown, ChevronUp } from "lucide-react";

const API_URL = typeof window !== "undefined" ? window.location.origin : "";

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("api_token") || "";
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

interface AutomationRule {
  id: number;
  title: string;
  is_active: boolean;
  trigger_type: string;
  trigger_conditions: Record<string, unknown> | null;
  action_type: string;
  action_params: Record<string, unknown> | null;
  cooldown_hours: number;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string | null;
}

interface Template {
  id: string;
  title: string;
  description: string;
  trigger_type: string;
  trigger_conditions: Record<string, unknown> | null;
  action_type: string;
  action_params: Record<string, unknown> | null;
  cooldown_hours: number;
}

const TRIGGER_LABELS: Record<string, string> = {
  workout_skipped: "Workout übersprungen",
  energy_low: "Energie niedrig",
  kr_completed: "KR abgeschlossen",
  sleep_low: "Schlaf niedrig",
  routine_skipped: "Routine übersprungen",
  kr_at_risk: "KR gefährdet",
  manual: "Manuell",
};

const ACTION_LABELS: Record<string, string> = {
  send_message: "Nachricht senden",
  create_task: "Task erstellen",
  reschedule_workout: "Training umplanen",
  suggest_routine: "Routine vorschlagen",
  update_setting: "Einstellung ändern",
};

export default function AutomationPage() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showTemplates, setShowTemplates] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [triggerResult, setTriggerResult] = useState<Record<number, string>>({});
  const [newRule, setNewRule] = useState({
    title: "",
    trigger_type: "manual",
    action_type: "send_message",
    action_params: { message: "" },
    cooldown_hours: 24,
  });

  const loadRules = useCallback(async () => {
    try {
      const data = await apiFetch<AutomationRule[]>("/api/automation/rules");
      setRules(data);
    } catch (e) {
      setError("Fehler beim Laden der Regeln");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTemplates = useCallback(async () => {
    try {
      const data = await apiFetch<Template[]>("/api/automation/templates");
      setTemplates(data);
    } catch (e) {
      console.warn("Templates failed to load");
    }
  }, []);

  useEffect(() => {
    loadRules();
    loadTemplates();
  }, [loadRules, loadTemplates]);

  const toggleRule = async (id: number) => {
    try {
      await apiFetch(`/api/automation/rules/${id}/toggle`, { method: "POST" });
      await loadRules();
    } catch (e) {
      alert("Fehler beim Umschalten der Regel");
    }
  };

  const deleteRule = async (id: number) => {
    if (!confirm("Regel löschen?")) return;
    try {
      await apiFetch(`/api/automation/rules/${id}`, { method: "DELETE" });
      await loadRules();
    } catch (e) {
      alert("Fehler beim Löschen der Regel");
    }
  };

  const triggerRule = async (id: number) => {
    try {
      const data = await apiFetch<{ ok: boolean; result: string }>(
        `/api/automation/rules/${id}/trigger`,
        { method: "POST" }
      );
      setTriggerResult((prev) => ({ ...prev, [id]: data.result || "Ausgeführt" }));
      setTimeout(() => setTriggerResult((prev) => { const n = { ...prev }; delete n[id]; return n; }), 5000);
      await loadRules();
    } catch (e) {
      alert("Fehler beim Auslösen der Regel");
    }
  };

  const createFromTemplate = async (tpl: Template) => {
    try {
      await apiFetch("/api/automation/rules", {
        method: "POST",
        body: JSON.stringify({
          title: tpl.title,
          trigger_type: tpl.trigger_type,
          trigger_conditions: tpl.trigger_conditions,
          action_type: tpl.action_type,
          action_params: tpl.action_params,
          cooldown_hours: tpl.cooldown_hours,
          is_active: true,
        }),
      });
      await loadRules();
      setShowTemplates(false);
    } catch (e) {
      alert("Fehler beim Erstellen der Regel");
    }
  };

  const createRule = async () => {
    if (!newRule.title.trim()) return;
    try {
      await apiFetch("/api/automation/rules", {
        method: "POST",
        body: JSON.stringify({
          ...newRule,
          action_params: newRule.action_type === "send_message"
            ? { message: newRule.action_params.message }
            : newRule.action_params,
        }),
      });
      await loadRules();
      setShowCreateForm(false);
      setNewRule({ title: "", trigger_type: "manual", action_type: "send_message", action_params: { message: "" }, cooldown_hours: 24 });
    } catch (e) {
      alert("Fehler beim Erstellen der Regel");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap size={28} className="text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Automatisierungs-Engine</h1>
            <p className="text-zinc-400 text-sm">Wenn-Dann Regeln für deinen Alltag</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowTemplates(!showTemplates); setShowCreateForm(false); }}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
          >
            <Plus size={16} />
            Aus Template
          </button>
          <button
            onClick={() => { setShowCreateForm(!showCreateForm); setShowTemplates(false); }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
          >
            <Plus size={16} />
            Neue Regel
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">{error}</div>
      )}

      {/* Templates Panel */}
      {showTemplates && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 space-y-3">
          <h2 className="text-white font-semibold mb-3">Templates</h2>
          {templates.map((tpl) => (
            <div key={tpl.id} className="flex items-start justify-between gap-4 p-3 bg-zinc-800 rounded-lg">
              <div className="flex-1">
                <div className="text-white text-sm font-medium">{tpl.title}</div>
                <div className="text-zinc-400 text-xs mt-1">{tpl.description}</div>
                <div className="flex gap-2 mt-2">
                  <span className="text-xs bg-blue-900/40 text-blue-300 px-2 py-0.5 rounded">
                    {TRIGGER_LABELS[tpl.trigger_type] || tpl.trigger_type}
                  </span>
                  <span className="text-xs bg-green-900/40 text-green-300 px-2 py-0.5 rounded">
                    {ACTION_LABELS[tpl.action_type] || tpl.action_type}
                  </span>
                </div>
              </div>
              <button
                onClick={() => createFromTemplate(tpl)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs transition-colors flex-shrink-0"
              >
                Hinzufügen
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 space-y-4">
          <h2 className="text-white font-semibold">Neue Regel erstellen</h2>
          <input
            value={newRule.title}
            onChange={(e) => setNewRule((p) => ({ ...p, title: e.target.value }))}
            placeholder="Regelname"
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
          />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Auslöser</label>
              <select
                value={newRule.trigger_type}
                onChange={(e) => setNewRule((p) => ({ ...p, trigger_type: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              >
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-xs mb-1 block">Aktion</label>
              <select
                value={newRule.action_type}
                onChange={(e) => setNewRule((p) => ({ ...p, action_type: e.target.value }))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              >
                {Object.entries(ACTION_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>
          {newRule.action_type === "send_message" && (
            <textarea
              value={String(newRule.action_params.message || "")}
              onChange={(e) => setNewRule((p) => ({ ...p, action_params: { message: e.target.value } }))}
              placeholder="Nachrichtentext"
              rows={3}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          )}
          <div className="flex items-center gap-3">
            <label className="text-zinc-400 text-xs">Cooldown (Stunden)</label>
            <input
              type="number"
              value={newRule.cooldown_hours}
              onChange={(e) => setNewRule((p) => ({ ...p, cooldown_hours: parseInt(e.target.value) || 24 }))}
              className="w-24 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex gap-2">
            <button onClick={createRule} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors">
              Erstellen
            </button>
            <button onClick={() => setShowCreateForm(false)} className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors">
              Abbrechen
            </button>
          </div>
        </div>
      )}

      {/* Rules List */}
      {rules.length === 0 ? (
        <div className="text-center py-16 text-zinc-500">
          <Zap size={48} className="mx-auto mb-4 opacity-30" />
          <p>Noch keine Regeln. Erstelle deine erste Automatisierung!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`bg-zinc-900 border rounded-xl p-4 transition-all ${
                rule.is_active ? "border-zinc-700" : "border-zinc-800 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-white font-medium text-sm truncate">{rule.title}</span>
                    {!rule.is_active && (
                      <span className="text-xs bg-zinc-700 text-zinc-400 px-2 py-0.5 rounded">Inaktiv</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs bg-blue-900/40 text-blue-300 px-2 py-0.5 rounded">
                      Wenn: {TRIGGER_LABELS[rule.trigger_type] || rule.trigger_type}
                    </span>
                    <span className="text-xs bg-green-900/40 text-green-300 px-2 py-0.5 rounded">
                      Dann: {ACTION_LABELS[rule.action_type] || rule.action_type}
                    </span>
                    <span className="text-xs text-zinc-500">
                      Cooldown: {rule.cooldown_hours}h
                    </span>
                    {rule.trigger_count > 0 && (
                      <span className="text-xs text-zinc-500">
                        {rule.trigger_count}× ausgelöst
                      </span>
                    )}
                  </div>
                  {rule.last_triggered_at && (
                    <div className="text-xs text-zinc-500 mt-1">
                      Zuletzt: {new Date(rule.last_triggered_at).toLocaleString("de-DE")}
                    </div>
                  )}
                  {triggerResult[rule.id] && (
                    <div className="mt-2 text-xs text-green-400 bg-green-900/20 rounded px-2 py-1">
                      ✓ {triggerResult[rule.id]}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => triggerRule(rule.id)}
                    title="Manuell auslösen"
                    className="p-1.5 text-zinc-400 hover:text-indigo-400 transition-colors"
                  >
                    <Play size={16} />
                  </button>
                  <button
                    onClick={() => toggleRule(rule.id)}
                    title={rule.is_active ? "Deaktivieren" : "Aktivieren"}
                    className="p-1.5 text-zinc-400 hover:text-white transition-colors"
                  >
                    {rule.is_active ? (
                      <ToggleRight size={20} className="text-indigo-400" />
                    ) : (
                      <ToggleLeft size={20} />
                    )}
                  </button>
                  <button
                    onClick={() => deleteRule(rule.id)}
                    title="Löschen"
                    className="p-1.5 text-zinc-400 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
