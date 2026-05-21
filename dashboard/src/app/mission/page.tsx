"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";
import { Save, Target } from "lucide-react";

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

export default function MissionPage() {
  const [areas, setAreas] = useState<Area[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ vision: string; current_state: string }>({
    vision: "",
    current_state: "",
  });
  const [savingId, setSavingId] = useState<number | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ areas: Area[] }>("/api/life-areas");
      setAreas(data.areas || []);
      setError(null);
    } catch (e) {
      setError("Lebensbereiche konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const startEdit = (area: Area) => {
    setEditingId(area.id);
    setDraft({ vision: area.vision || "", current_state: area.current_state || "" });
    setSuccessMsg(null);
  };

  const save = async (id: number) => {
    setSavingId(id);
    try {
      await apiFetch(`/api/life-areas/${id}`, {
        method: "PATCH",
        body: JSON.stringify(draft),
      });
      await load();
      setEditingId(null);
      setSuccessMsg("Gespeichert");
      setTimeout(() => setSuccessMsg(null), 2500);
    } catch (e) {
      setError("Speichern fehlgeschlagen");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <>
      <Header
        title="🎯 Mission"
        subtitle="9 Lebensbereiche — Vision & aktueller Stand"
      />
      <div className="p-4 space-y-4">
        {loading && <LoadingSpinner />}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">
            ❌ {error}
          </div>
        )}
        {successMsg && (
          <div className="bg-green-900/30 border border-green-700 rounded-xl p-3 text-green-300 text-sm">
            ✅ {successMsg}
          </div>
        )}

        {!loading && areas.length === 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 text-center">
            <Target size={40} className="mx-auto text-zinc-600 mb-4" />
            <h2 className="text-white font-semibold mb-2">Noch keine Lebensbereiche</h2>
            <p className="text-zinc-400 text-sm">
              Server-side: <code>python3 scripts/seed_lukas_life_areas.py --remap</code>
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {areas.map((a) => (
            <div
              key={a.id}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 flex flex-col gap-2"
              style={{ borderLeft: `4px solid ${a.color_hex}` }}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-white font-semibold">{a.name}</h3>
                <span className="text-xs text-zinc-500">P{a.priority}</span>
              </div>
              <div className="text-xs text-zinc-500 flex gap-3">
                <span>{a.active_objectives} aktiv</span>
                {a.stale_days !== null && (
                  <span className={a.stale_days > 14 ? "text-amber-400" : ""}>
                    {a.stale_days}d ohne Log
                  </span>
                )}
              </div>

              {editingId === a.id ? (
                <div className="space-y-2">
                  <textarea
                    value={draft.vision}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, vision: e.target.value }))
                    }
                    placeholder="Vision (langfristig)"
                    className="w-full bg-black border border-zinc-800 text-zinc-200 text-xs rounded-lg p-2 outline-none focus:border-indigo-600 min-h-[60px]"
                  />
                  <textarea
                    value={draft.current_state}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, current_state: e.target.value }))
                    }
                    placeholder="Wo stehst du heute? (current state)"
                    className="w-full bg-black border border-zinc-800 text-zinc-200 text-xs rounded-lg p-2 outline-none focus:border-indigo-600 min-h-[60px]"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => save(a.id)}
                      disabled={savingId === a.id}
                      className="flex items-center gap-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-xs font-semibold"
                    >
                      <Save size={12} />
                      {savingId === a.id ? "…" : "Speichern"}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg px-3 py-1.5 text-xs"
                    >
                      Abbrechen
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="text-zinc-300 text-xs">
                    <div className="text-zinc-500 mb-0.5">Vision</div>
                    <div className="whitespace-pre-line">{a.vision || "—"}</div>
                  </div>
                  {a.current_state && (
                    <div className="text-zinc-300 text-xs">
                      <div className="text-zinc-500 mb-0.5">Aktueller Stand</div>
                      <div className="whitespace-pre-line">{a.current_state}</div>
                    </div>
                  )}
                  <button
                    onClick={() => startEdit(a)}
                    className="self-start text-xs text-indigo-400 hover:text-indigo-300 mt-1"
                  >
                    Bearbeiten
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
