"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";

const API_URL = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("api_token");
}

async function apiFetch<T>(path: string): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: token ? `Bearer ${token}` : "" },
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
};

function AreaCard({
  a,
}: {
  a: Cockpit["areas"][number];
}) {
  const score = a.score ?? 0;
  const stale = a.stale_days !== null && a.stale_days > 7;
  // Vakuum-State: kein Objective angelegt. Visuell tot (grau, kein Color-Border).
  const isVacuum = a.active_objectives === 0;

  if (isVacuum) {
    return (
      <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 flex flex-col gap-1 opacity-60">
        <div className="flex items-center justify-between">
          <div className="text-zinc-500 text-sm font-medium">{a.name}</div>
          <div className="text-xs text-zinc-700">💤 kein Objective</div>
        </div>
        <div className="text-zinc-700 text-xs">— Bereich tot —</div>
      </div>
    );
  }

  return (
    <div
      className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 flex flex-col gap-2"
      style={{ borderLeft: `4px solid ${a.color}` }}
    >
      <div className="flex items-center justify-between">
        <div className="text-white text-sm font-semibold">{a.name}</div>
        <div className="text-xs text-zinc-500">
          {a.active_objectives} aktiv
          {stale && <span className="text-amber-400 ml-1">⚠ {a.stale_days}d</span>}
        </div>
      </div>
      <div className="text-2xl font-bold text-white">{a.score ?? "—"}</div>
      <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full"
          style={{ width: `${score}%`, background: a.color }}
        />
      </div>
    </div>
  );
}

export default function CockpitPage() {
  const [data, setData] = useState<Cockpit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await apiFetch<Cockpit>("/api/cockpit");
      setData(d);
      setLastRefresh(new Date());
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

  return (
    <>
      <Header
        title="🎯 Cockpit"
        subtitle="9 Lebensbereiche · Festnagel · Cuts"
      />
      <div className="p-4 space-y-4">
        {!data && !error && <LoadingSpinner />}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">
            ❌ {error}
          </div>
        )}

        {data && (
          <>
            {/* Life Score Hero */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex items-center gap-6">
              <div>
                <div className="text-xs text-zinc-500 mb-1">Life Score</div>
                <div className="text-5xl font-bold text-white">
                  {data.life_score ?? "—"}
                </div>
                {data.life_score !== null && (
                  <div
                    className={
                      "text-xs mt-1 " +
                      (data.life_score_trend >= 0 ? "text-green-400" : "text-red-400")
                    }
                  >
                    {data.life_score_trend >= 0 ? "↗" : "↘"} {Math.abs(data.life_score_trend)} (Q-1)
                  </div>
                )}
              </div>
              <div className="ml-auto text-right text-xs text-zinc-400 space-y-0.5">
                <div>{data.active_objectives} aktive Objectives</div>
                <div className={data.krs_at_risk > 0 ? "text-amber-400" : ""}>
                  {data.krs_at_risk} KRs gefährdet
                </div>
                {data.energy !== null && (
                  <div>Energie: {data.energy}/10</div>
                )}
                {lastRefresh && (
                  <div className="text-zinc-600 mt-1">
                    {lastRefresh.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                  </div>
                )}
              </div>
            </div>

            {/* Festnagel banner */}
            <div className="bg-amber-950/40 border border-amber-800/50 rounded-2xl p-4">
              <div className="text-xs text-amber-300 uppercase tracking-wide mb-1">
                Festnagel heute
              </div>
              <div className="text-amber-50 text-sm">{data.festnagel}</div>
            </div>

            {/* 9 Areas Heatmap */}
            <div>
              <div className="text-xs text-zinc-500 uppercase tracking-wide mb-2">
                9 Lebensbereiche
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {data.areas.map((a) => (
                  <AreaCard key={a.id} a={a} />
                ))}
              </div>
            </div>

            {/* Weekly Priorities */}
            {data.weekly_priorities.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <div className="text-white font-semibold text-sm mb-3">
                  Diese Woche · Top {data.weekly_priorities.length}
                </div>
                <ol className="space-y-1.5">
                  {data.weekly_priorities.map((p) => (
                    <li
                      key={p.id}
                      className="text-sm text-zinc-200 flex items-center gap-3"
                    >
                      <span className="text-zinc-500 w-4">{p.rank}.</span>
                      <span className="flex-1">{p.title}</span>
                      <span className="text-xs text-zinc-500">{p.status}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Streaks at risk */}
            {data.streaks_at_risk.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <div className="text-white font-semibold text-sm mb-2">
                  Streaks gefährdet
                </div>
                <ul className="space-y-1">
                  {data.streaks_at_risk.map((s, i) => (
                    <li key={i} className="text-sm text-zinc-300">⚠ {s}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Cuts this week */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 flex items-center gap-3">
              <div className="text-sm text-zinc-400">Cuts diese Woche:</div>
              <div className="text-2xl font-bold text-white">{data.cuts_this_week}</div>
              {data.cuts_this_week === 0 && (
                <div className="ml-auto text-xs text-amber-400">
                  Kein Cut diese Woche — Expansion droht.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
