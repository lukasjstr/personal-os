"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";
import { Check, SkipForward, X, ArrowRight, Zap } from "lucide-react";

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
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

type Cockpit = {
  date: string;
  life_score: number | null;
  life_score_trend: number;
  active_objectives: number;
  krs_at_risk: number;
  energy: number | null;
  areas: Array<{
    id: number;
    name: string;
    short_code: string;
    color: string;
    score: number | null;
    stale_days: number | null;
    active_objectives: number;
  }>;
  weekly_priorities: Array<{ id: number; rank: number; title: string; status: string }>;
  festnagel: string;
  streaks_at_risk: string[];
  cuts_this_week: number;
  next_action: null | {
    task_id: number;
    title: string;
    objective_title?: string;
    kr_title?: string;
    priority: number;
    due_date?: string;
    reason: string;
  };
  kanban_summary: {
    top_todo: Array<{ id: number; title: string; priority: number; category: string; objective_id: number | null }>;
    doing_count: number;
    done_today_count: number;
    open_total: number;
  };
};

function AreaCard({ a }: { a: Cockpit["areas"][number] }) {
  const isVacuum = a.active_objectives === 0;
  if (isVacuum) {
    return (
      <a
        href={`/mission`}
        className="bg-zinc-950 border border-zinc-900 rounded-xl p-3 flex flex-col gap-1 opacity-50 hover:opacity-80 hover:border-zinc-700 transition"
      >
        <div className="flex items-center justify-between">
          <div className="text-zinc-500 text-xs font-medium">{a.name}</div>
          <div className="text-[10px] text-zinc-700">💤</div>
        </div>
        <div className="text-zinc-700 text-[10px]">— leer —</div>
      </a>
    );
  }
  const score = a.score ?? 0;
  const stale = a.stale_days !== null && a.stale_days > 7;
  return (
    <a
      href={`/mission`}
      className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex flex-col gap-1.5 hover:border-zinc-700 transition"
      style={{ borderLeft: `4px solid ${a.color}` }}
    >
      <div className="flex items-center justify-between">
        <div className="text-white text-xs font-semibold">{a.name}</div>
        <div className="text-[10px] text-zinc-500">
          {a.active_objectives}
          {stale && <span className="text-amber-400 ml-1">⚠</span>}
        </div>
      </div>
      <div className="text-xl font-bold text-white">{a.score ?? "—"}</div>
      <div className="w-full bg-zinc-800 rounded-full h-1 overflow-hidden">
        <div className="h-full" style={{ width: `${score}%`, background: a.color }} />
      </div>
    </a>
  );
}

const PRIORITY_DOT: Record<number, string> = {
  1: "bg-red-500",
  2: "bg-orange-500",
  3: "bg-yellow-500",
  4: "bg-blue-500",
  5: "bg-zinc-500",
};

export default function CockpitPage() {
  const [data, setData] = useState<Cockpit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await apiFetch<Cockpit>("/api/cockpit");
      setData(d);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const completeNext = async () => {
    if (!data?.next_action) return;
    setBusy(true);
    try {
      await apiFetch(`/api/tasks/${data.next_action.task_id}/complete`, { method: "POST" });
      await load();
    } catch {
      setError("Konnte nicht abschließen");
    } finally {
      setBusy(false);
    }
  };
  const skipNext = async () => {
    if (!data?.next_action) return;
    setBusy(true);
    try {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const dueStr = tomorrow.toISOString().slice(0, 10);
      await apiFetch(`/api/tasks/${data.next_action.task_id}`, {
        method: "PUT",
        body: JSON.stringify({ due_date: dueStr }),
      });
      await load();
    } catch {
      setError("Konnte nicht verschieben");
    } finally {
      setBusy(false);
    }
  };
  const cutNext = async () => {
    if (!data?.next_action) return;
    if (!confirm(`'${data.next_action.title}' streichen?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/api/tasks/${data.next_action.task_id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "cancelled" }),
      });
      await load();
    } catch {
      setError("Konnte nicht streichen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Header title="Cockpit" subtitle={data ? data.date : "..."} />
      <div className="p-4 space-y-4 max-w-5xl mx-auto">
        {!data && !error && <LoadingSpinner />}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        {data && (
          <>
            {/* JETZT — Next Action */}
            <div className="bg-indigo-950/40 border border-indigo-800/60 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-2">
                <Zap size={14} className="text-indigo-300" />
                <div className="text-[11px] uppercase tracking-wider text-indigo-300 font-semibold">
                  Jetzt
                </div>
              </div>
              {data.next_action ? (
                <>
                  <div className="text-white text-lg font-semibold leading-snug">
                    {data.next_action.title}
                  </div>
                  <div className="text-zinc-400 text-xs mt-1 flex gap-2 flex-wrap">
                    <span className={`inline-block w-2 h-2 rounded-full mt-1 ${PRIORITY_DOT[data.next_action.priority] || "bg-zinc-500"}`} />
                    <span>P{data.next_action.priority}</span>
                    {data.next_action.objective_title && (
                      <>
                        <span>·</span>
                        <span>{data.next_action.objective_title}</span>
                      </>
                    )}
                    {data.next_action.due_date && (
                      <>
                        <span>·</span>
                        <span>fällig {data.next_action.due_date}</span>
                      </>
                    )}
                  </div>
                  {data.next_action.reason && (
                    <div className="text-zinc-500 text-xs mt-1 italic">
                      {data.next_action.reason}
                    </div>
                  )}
                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={completeNext}
                      disabled={busy}
                      className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-semibold"
                    >
                      <Check size={14} /> Erledigt
                    </button>
                    <button
                      onClick={skipNext}
                      disabled={busy}
                      className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-200 rounded-lg px-4 py-2 text-sm"
                    >
                      <SkipForward size={14} /> Morgen
                    </button>
                    <button
                      onClick={cutNext}
                      disabled={busy}
                      className="flex items-center gap-1.5 bg-zinc-800 hover:bg-red-900/50 hover:text-red-300 disabled:opacity-50 text-zinc-400 rounded-lg px-3 py-2 text-sm ml-auto"
                    >
                      <X size={14} /> Cut
                    </button>
                  </div>
                </>
              ) : (
                <div className="text-zinc-400 text-sm">
                  Keine offene Task. Schreib dem Bot eine neue Sache oder öffne
                  {" "}
                  <a href="/kanban" className="text-indigo-400 hover:underline">
                    Kanban
                  </a>.
                </div>
              )}
            </div>

            {/* FESTNAGEL */}
            <div className="bg-amber-950/40 border border-amber-800/50 rounded-2xl p-4">
              <div className="text-[11px] text-amber-300 uppercase tracking-wider mb-1 font-semibold">
                Festnagel
              </div>
              <div className="text-amber-50 text-sm">{data.festnagel}</div>
            </div>

            {/* STATUS + KANBAN-SUMMARY */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <a href="/quarterly" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 hover:border-zinc-700 transition">
                <div className="text-[10px] uppercase text-zinc-500 tracking-wide">Life Score</div>
                <div className="text-3xl font-bold text-white mt-1">{data.life_score ?? "—"}</div>
                {data.life_score !== null && (
                  <div className={"text-[10px] mt-0.5 " + (data.life_score_trend >= 0 ? "text-green-400" : "text-red-400")}>
                    {data.life_score_trend >= 0 ? "↗" : "↘"} {Math.abs(data.life_score_trend)} vs Q-1
                  </div>
                )}
              </a>
              <a href="/objectives" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 hover:border-zinc-700 transition">
                <div className="text-[10px] uppercase text-zinc-500 tracking-wide">Aktive Ziele</div>
                <div className="text-3xl font-bold text-white mt-1">{data.active_objectives}</div>
                <div className={"text-[10px] mt-0.5 " + (data.krs_at_risk > 0 ? "text-amber-400" : "text-zinc-500")}>
                  {data.krs_at_risk} KRs gefährdet
                </div>
              </a>
              <a href="/kanban" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 hover:border-zinc-700 transition">
                <div className="text-[10px] uppercase text-zinc-500 tracking-wide">Tasks offen</div>
                <div className="text-3xl font-bold text-white mt-1">{data.kanban_summary.open_total}</div>
                <div className="text-[10px] mt-0.5 text-zinc-500">
                  {data.kanban_summary.doing_count} doing · {data.kanban_summary.done_today_count} done heute
                </div>
              </a>
              <a href="/kanban" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 hover:border-zinc-700 transition">
                <div className="text-[10px] uppercase text-zinc-500 tracking-wide">Cuts Woche</div>
                <div className="text-3xl font-bold text-white mt-1">{data.cuts_this_week}</div>
                <div className={"text-[10px] mt-0.5 " + (data.cuts_this_week === 0 ? "text-amber-400" : "text-green-400")}>
                  {data.cuts_this_week === 0 ? "Expansion droht" : "ok"}
                </div>
              </a>
            </div>

            {/* HEUTE OPERATIV — Mini-Kanban */}
            {data.kanban_summary.top_todo.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-white text-sm font-semibold">Heute operativ</div>
                  <a href="/kanban" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                    Alle Tasks <ArrowRight size={12} />
                  </a>
                </div>
                <div className="space-y-1.5">
                  {data.kanban_summary.top_todo.map((t) => (
                    <a
                      key={t.id}
                      href="/kanban"
                      className="flex items-center gap-3 px-2 py-1.5 hover:bg-zinc-800/60 rounded-lg transition"
                    >
                      <span className={`w-2 h-2 rounded-full shrink-0 ${PRIORITY_DOT[t.priority] || "bg-zinc-500"}`} />
                      <span className="text-zinc-200 text-sm flex-1 truncate">{t.title}</span>
                      <span className="text-[10px] text-zinc-500">P{t.priority}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* 9 LEBENSBEREICHE */}
            <div>
              <div className="text-zinc-500 text-[11px] uppercase tracking-wider mb-2 font-semibold">
                9 Lebensbereiche
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {data.areas.map((a) => <AreaCard key={a.id} a={a} />)}
              </div>
            </div>

            {/* Streaks gefährdet */}
            {data.streaks_at_risk.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
                <div className="text-white text-sm font-semibold mb-2">Streaks gefährdet</div>
                <ul className="space-y-1">
                  {data.streaks_at_risk.map((s, i) => (
                    <li key={i} className="text-sm text-zinc-300 flex gap-2">
                      <span className="text-amber-400">⚠</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
