"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";
import { Save, Edit3, Plus, ArrowRight } from "lucide-react";

const API_URL = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";

function getToken(): string | null {
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
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

type Area = {
  id: number;
  name: string;
  short_code: string;
  vision: string;
  current_state: string | null;
  priority: number;
  color_hex: string;
  active_objectives: number;
  stale_days: number | null;
  last_log_at: string | null;
};

type KR = {
  id: number;
  title: string;
  current_value: number;
  target_value: number | null;
  unit: string | null;
  frequency: string;
  pct: number;
};

type ObjectiveFull = {
  id: number;
  title: string;
  category: string;
  priority_weight: number;
  status: string;
  kr_count: number;
  avg_pct: number;
  key_results: KR[];
};

export default function MissionPage() {
  const [areas, setAreas] = useState<Area[]>([]);
  const [objectivesByArea, setObjectivesByArea] = useState<Record<number, ObjectiveFull[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [editingArea, setEditingArea] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ vision: string; current_state: string }>({
    vision: "",
    current_state: "",
  });
  const [savingId, setSavingId] = useState<number | null>(null);
  const [reassigning, setReassigning] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ areas: Area[] }>("/api/life-areas");
      const newAreas = (data.areas || []).slice().sort((a, b) => a.priority - b.priority);
      setAreas(newAreas);
      const map: Record<number, ObjectiveFull[]> = {};
      await Promise.all(
        newAreas.map(async (a) => {
          try {
            const r = await apiFetch<{ objectives: ObjectiveFull[] }>(
              `/api/life-areas/${a.id}/objectives`,
            );
            map[a.id] = r.objectives;
          } catch {
            map[a.id] = [];
          }
        }),
      );
      setObjectivesByArea(map);
      setError(null);
    } catch {
      setError("Lebensbereiche konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const startEdit = (a: Area) => {
    setEditingArea(a.id);
    setDraft({ vision: a.vision || "", current_state: a.current_state || "" });
  };
  const save = async (id: number) => {
    setSavingId(id);
    try {
      await apiFetch(`/api/life-areas/${id}`, {
        method: "PATCH",
        body: JSON.stringify(draft),
      });
      await load();
      setEditingArea(null);
      setSuccessMsg("Gespeichert");
      setTimeout(() => setSuccessMsg(null), 2000);
    } catch {
      setError("Speichern fehlgeschlagen");
    } finally {
      setSavingId(null);
    }
  };
  const reassign = async (objectiveId: number, newAreaId: number) => {
    setReassigning(objectiveId);
    try {
      await apiFetch(`/api/objectives/${objectiveId}/life-area`, {
        method: "PATCH",
        body: JSON.stringify({ life_area_id: newAreaId }),
      });
      await load();
      setSuccessMsg("Objective verschoben");
      setTimeout(() => setSuccessMsg(null), 2000);
    } catch {
      setError("Verschieben fehlgeschlagen");
    } finally {
      setReassigning(null);
    }
  };

  const activeAreas = areas.filter((a) => (objectivesByArea[a.id] || []).length > 0);
  const emptyAreas = areas.filter((a) => (objectivesByArea[a.id] || []).length === 0);

  return (
    <>
      <Header
        title="🎯 Mission"
        subtitle="9 Lebensbereiche · Vision · Aktive Ziele"
      />
      <div className="p-4 space-y-4">
        {loading && <LoadingSpinner />}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">
            {error}
          </div>
        )}
        {successMsg && (
          <div className="bg-green-900/30 border border-green-700 rounded-xl p-3 text-green-300 text-sm">
            {successMsg}
          </div>
        )}

        {!loading && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Active areas: 2/3 of width */}
            <div className="lg:col-span-2 space-y-3">
              <div className="text-zinc-500 text-xs uppercase tracking-wide">
                Aktiv ({activeAreas.length})
              </div>
              {activeAreas.length === 0 && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 text-center text-zinc-500 text-sm">
                  Noch keine aktiven Objectives. Schreib dem Bot ein Ziel
                  oder füg eines rechts in einem leeren Bereich hinzu.
                </div>
              )}
              {activeAreas.map((a) => {
                const objs = objectivesByArea[a.id] || [];
                const isEditing = editingArea === a.id;
                return (
                  <div
                    key={a.id}
                    className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden"
                    style={{ borderLeft: `4px solid ${a.color_hex}` }}
                  >
                    {/* Header */}
                    <div className="p-4 flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-white font-semibold">{a.name}</h3>
                          <span className="text-[10px] text-zinc-500 px-1.5 py-0.5 bg-zinc-800 rounded">
                            P{a.priority}
                          </span>
                          {a.stale_days !== null && a.stale_days > 14 && (
                            <span className="text-[10px] text-amber-400">
                              ⚠ {a.stale_days}d ohne Log
                            </span>
                          )}
                        </div>
                        {!isEditing && (
                          <p className="text-zinc-400 text-xs leading-snug">{a.vision || "—"}</p>
                        )}
                      </div>
                      <button
                        onClick={() => (isEditing ? setEditingArea(null) : startEdit(a))}
                        className="text-zinc-500 hover:text-zinc-300 p-1"
                      >
                        <Edit3 size={14} />
                      </button>
                    </div>

                    {/* Edit form */}
                    {isEditing && (
                      <div className="px-4 pb-3 space-y-2 border-t border-zinc-800 pt-3">
                        <div>
                          <div className="text-[10px] text-zinc-500 mb-1">Vision</div>
                          <textarea
                            value={draft.vision}
                            onChange={(e) =>
                              setDraft((d) => ({ ...d, vision: e.target.value }))
                            }
                            className="w-full bg-black border border-zinc-800 text-zinc-200 text-xs rounded-lg p-2 outline-none focus:border-indigo-600 min-h-[50px]"
                          />
                        </div>
                        <div>
                          <div className="text-[10px] text-zinc-500 mb-1">Aktueller Stand</div>
                          <textarea
                            value={draft.current_state}
                            onChange={(e) =>
                              setDraft((d) => ({ ...d, current_state: e.target.value }))
                            }
                            placeholder="Wo stehst du heute?"
                            className="w-full bg-black border border-zinc-800 text-zinc-200 text-xs rounded-lg p-2 outline-none focus:border-indigo-600 min-h-[50px]"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => save(a.id)}
                            disabled={savingId === a.id}
                            className="flex items-center gap-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-xs"
                          >
                            <Save size={12} />
                            {savingId === a.id ? "…" : "Speichern"}
                          </button>
                          <button
                            onClick={() => setEditingArea(null)}
                            className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg px-3 py-1.5 text-xs"
                          >
                            Abbrechen
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Current state (read-only) */}
                    {!isEditing && a.current_state && (
                      <div className="px-4 pb-3 border-t border-zinc-800 pt-3">
                        <div className="text-[10px] text-zinc-500 uppercase tracking-wide mb-1">
                          Heute
                        </div>
                        <div className="text-zinc-300 text-xs whitespace-pre-line">
                          {a.current_state}
                        </div>
                      </div>
                    )}

                    {/* Objectives + KRs */}
                    <div className="border-t border-zinc-800 divide-y divide-zinc-800/60">
                      {objs.map((o) => (
                        <div key={o.id} className="px-4 py-3">
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <a
                              href={`/objectives`}
                              className="flex-1 min-w-0 text-zinc-100 text-sm font-medium hover:text-indigo-300 truncate"
                              title={o.title}
                            >
                              {o.title}
                              {o.priority_weight >= 8 && (
                                <span className="ml-1.5 text-[10px] text-amber-400 align-middle">P1</span>
                              )}
                            </a>
                            <span className="text-xs text-zinc-500 shrink-0">{o.avg_pct}%</span>
                            <select
                              value={a.id}
                              onChange={(e) => reassign(o.id, parseInt(e.target.value, 10))}
                              disabled={reassigning === o.id}
                              className="bg-zinc-800 text-zinc-400 text-[10px] rounded px-1.5 py-1 outline-none border border-zinc-700 hover:border-zinc-600"
                              title="In anderen Lebensbereich verschieben"
                            >
                              {areas.map((opt) => (
                                <option key={opt.id} value={opt.id}>
                                  {opt.name}
                                </option>
                              ))}
                            </select>
                          </div>
                          {/* KRs */}
                          {o.key_results.length > 0 && (
                            <div className="space-y-1.5">
                              {o.key_results.map((kr) => (
                                <div key={kr.id} className="flex items-center gap-2">
                                  <div className="text-[11px] text-zinc-400 flex-1 truncate" title={kr.title}>
                                    {kr.title}
                                  </div>
                                  <div className="w-24 bg-zinc-800 rounded-full h-1 overflow-hidden">
                                    <div
                                      className="h-full"
                                      style={{ width: `${kr.pct}%`, background: a.color_hex }}
                                    />
                                  </div>
                                  <div className="text-[10px] text-zinc-500 w-20 text-right shrink-0 tabular-nums">
                                    {kr.current_value}/{kr.target_value} {kr.unit || ""}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Empty areas: 1/3 of width, compact */}
            <div className="space-y-3">
              <div className="text-zinc-500 text-xs uppercase tracking-wide">
                Leer ({emptyAreas.length})
              </div>
              {emptyAreas.map((a) => {
                const isEditing = editingArea === a.id;
                return (
                  <div
                    key={a.id}
                    className="bg-zinc-950 border border-zinc-900 rounded-xl p-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ background: a.color_hex }}
                        />
                        <span className="text-zinc-300 text-sm font-medium">{a.name}</span>
                      </div>
                      <button
                        onClick={() => (isEditing ? setEditingArea(null) : startEdit(a))}
                        className="text-zinc-600 hover:text-zinc-400 p-0.5"
                      >
                        <Edit3 size={12} />
                      </button>
                    </div>
                    {!isEditing && (
                      <div className="text-[11px] text-zinc-500 leading-snug mb-2">
                        {a.vision || "—"}
                      </div>
                    )}
                    {isEditing && (
                      <div className="space-y-1.5 mb-2">
                        <textarea
                          value={draft.vision}
                          onChange={(e) => setDraft((d) => ({ ...d, vision: e.target.value }))}
                          placeholder="Vision"
                          className="w-full bg-black border border-zinc-800 text-zinc-200 text-xs rounded p-1.5 outline-none focus:border-indigo-600 min-h-[40px]"
                        />
                        <div className="flex gap-1">
                          <button
                            onClick={() => save(a.id)}
                            disabled={savingId === a.id}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white rounded px-2 py-1 text-[10px]"
                          >
                            Speichern
                          </button>
                          <button
                            onClick={() => setEditingArea(null)}
                            className="bg-zinc-800 text-zinc-400 rounded px-2 py-1 text-[10px]"
                          >
                            X
                          </button>
                        </div>
                      </div>
                    )}
                    <a
                      href="/objectives"
                      className="flex items-center gap-1 text-[10px] text-indigo-400 hover:text-indigo-300"
                    >
                      <Plus size={10} /> Objective anlegen <ArrowRight size={10} />
                    </a>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
