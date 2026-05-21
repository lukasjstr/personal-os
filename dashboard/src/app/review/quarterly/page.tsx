"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";

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

type ReviewListItem = {
  id: number;
  year: number;
  quarter: number;
  quarter_label: string;
  life_score: number | null;
  status: string;
  generated_at: string | null;
  objectives_count: number;
};

type ReviewDetail = {
  id: number;
  year: number;
  quarter: number;
  quarter_label: string;
  life_score: number | null;
  life_area_scores?: Record<string, number>;
  previous_life_score?: number | null;
  objectives_data?: Array<{
    id: number;
    title: string;
    grade_pct: number;
    consistency?: number;
    life_area_id?: number | null;
  }>;
  ai_analysis: string | null;
  highlights: string[] | null;
  challenges: string[] | null;
  suggested_next_quarter?: { focus_areas?: string[]; actions?: string[] };
  user_reflection?: string | null;
  completed_at?: string | null;
  status: string;
  generated_at: string | null;
};

const AREA_COLORS: Record<string, string> = {
  mental: "#9B7EBD",
  physical: "#D85A30",
  character: "#378ADD",
  family: "#1D9E75",
  romance: "#D4537E",
  money: "#EF9F27",
  lifestyle: "#534AB7",
  charity: "#5DA37F",
  spirituality: "#888780",
};

export default function QuarterlyReviewPage() {
  const [list, setList] = useState<ReviewListItem[]>([]);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<ReviewListItem[]>("/api/quarterly-reviews");
      setList(data || []);
      if (data && data.length > 0) {
        const latest = await apiFetch<ReviewDetail>(
          `/api/quarterly-reviews/${data[0].id}`,
        ).catch(() => apiFetch<ReviewDetail>("/api/quarterly-reviews/latest"));
        setDetail(latest);
      }
      setError(null);
    } catch (e) {
      setError("Q-Reviews konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selectReview = async (id: number) => {
    try {
      const d = await apiFetch<ReviewDetail>(`/api/quarterly-reviews/${id}`);
      setDetail(d);
    } catch {
      try {
        const d = await apiFetch<ReviewDetail>("/api/quarterly-reviews/latest");
        setDetail(d);
      } catch {
        setError("Review konnte nicht geladen werden.");
      }
    }
  };

  return (
    <>
      <Header
        title="📊 Quartals-Review"
        subtitle="Life Score + Lebensbereich-Scores"
      />
      <div className="p-4 space-y-4">
        {loading && <LoadingSpinner />}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">
            ❌ {error}
          </div>
        )}

        {!loading && list.length === 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 text-center">
            <p className="text-zinc-400 text-sm">
              Noch kein Quartals-Review generiert. Wird automatisch am Ende jedes Quartals erstellt.
            </p>
          </div>
        )}

        {detail && (
          <>
            {/* Score hero */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex items-center gap-6">
              <div>
                <div className="text-xs text-zinc-500 mb-1">{detail.quarter_label}</div>
                <div className="text-5xl font-bold text-white">{detail.life_score ?? "—"}</div>
                <div className="text-xs text-zinc-500 mt-1">Life Score / 100</div>
              </div>
              {detail.previous_life_score !== null &&
                detail.previous_life_score !== undefined && (
                  <div className="text-sm">
                    <div className="text-zinc-500">Vorheriges Quartal</div>
                    <div className="text-zinc-300">{detail.previous_life_score}</div>
                    <div
                      className={
                        (detail.life_score ?? 0) >= detail.previous_life_score
                          ? "text-green-400"
                          : "text-red-400"
                      }
                    >
                      {(detail.life_score ?? 0) >= detail.previous_life_score ? "↑" : "↓"}{" "}
                      {Math.abs((detail.life_score ?? 0) - detail.previous_life_score)}
                    </div>
                  </div>
                )}
              <div className="ml-auto text-right text-xs text-zinc-500">
                {detail.status}
                {detail.completed_at && (
                  <>
                    <br />
                    abgeschlossen: {new Date(detail.completed_at).toLocaleDateString("de-DE")}
                  </>
                )}
              </div>
            </div>

            {/* Area scores */}
            {detail.life_area_scores && Object.keys(detail.life_area_scores).length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <h3 className="text-white font-semibold mb-3 text-sm">Lebensbereiche</h3>
                <div className="space-y-2">
                  {Object.entries(detail.life_area_scores)
                    .sort((a, b) => b[1] - a[1])
                    .map(([code, score]) => (
                      <div key={code} className="flex items-center gap-3">
                        <div className="w-28 text-xs text-zinc-300 capitalize">{code}</div>
                        <div className="flex-1 bg-zinc-800 rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full"
                            style={{
                              width: `${score}%`,
                              background: AREA_COLORS[code] || "#888780",
                            }}
                          />
                        </div>
                        <div className="w-10 text-right text-xs text-zinc-400">{score}</div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* AI Analysis */}
            {detail.ai_analysis && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <h3 className="text-white font-semibold mb-2 text-sm">AI-Analyse</h3>
                <p className="text-zinc-300 text-sm whitespace-pre-line">{detail.ai_analysis}</p>
              </div>
            )}

            {/* Suggested next quarter */}
            {detail.suggested_next_quarter?.actions &&
              detail.suggested_next_quarter.actions.length > 0 && (
                <div className="bg-indigo-950/40 border border-indigo-800/50 rounded-2xl p-5">
                  <h3 className="text-indigo-300 font-semibold mb-2 text-sm">
                    Vorschläge nächstes Quartal
                  </h3>
                  <ul className="space-y-1">
                    {detail.suggested_next_quarter.actions.map((a, i) => (
                      <li key={i} className="text-sm text-zinc-200">
                        · {a}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
          </>
        )}

        {/* History list */}
        {list.length > 1 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
            <h3 className="text-white font-semibold mb-3 text-sm">History</h3>
            <div className="space-y-1">
              {list.map((r) => (
                <button
                  key={r.id}
                  onClick={() => selectReview(r.id)}
                  className="w-full flex items-center justify-between gap-3 bg-zinc-800 hover:bg-zinc-700 rounded-lg px-3 py-2 text-left"
                >
                  <span className="text-zinc-200 text-sm">{r.quarter_label}</span>
                  <span className="text-zinc-400 text-xs">
                    {r.life_score ?? "—"}/100 · {r.status}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
