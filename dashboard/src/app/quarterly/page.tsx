"use client";

import { useState, useEffect, useCallback } from "react";
import { BarChart3, RefreshCw, ChevronDown, Award, AlertTriangle } from "lucide-react";

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
  if (res.status === 404) return null as T;
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

interface ObjectiveData {
  id: number;
  title: string;
  category: string;
  status: string;
  grade: number;
  grade_pct: number;
  kr_count: number;
}

interface QuarterlyReview {
  id: number;
  year: number;
  quarter: number;
  quarter_label: string;
  life_score: number | null;
  objectives_data: ObjectiveData[] | null;
  ai_analysis: string | null;
  highlights: string[] | null;
  challenges: string[] | null;
  status: string;
  generated_at: string | null;
}

function gradeColor(grade: number): string {
  if (grade >= 0.8) return "bg-green-500";
  if (grade >= 0.5) return "bg-yellow-500";
  return "bg-red-500";
}

function scoreColor(score: number): string {
  if (score >= 75) return "text-green-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

const CATEGORY_LABELS: Record<string, string> = {
  health: "Gesundheit",
  business: "Business",
  personal: "Persönlich",
  fitness: "Fitness",
  finance: "Finanzen",
  learning: "Lernen",
};

export default function QuarterlyPage() {
  const [review, setReview] = useState<QuarterlyReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadReview = useCallback(async () => {
    try {
      const data = await apiFetch<QuarterlyReview>("/api/quarterly-reviews/latest");
      setReview(data);
    } catch (e) {
      setError("Fehler beim Laden des Quartals-Reviews");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReview();
  }, [loadReview]);

  const generateReview = async () => {
    setGenerating(true);
    setError("");
    try {
      const data = await apiFetch<QuarterlyReview>("/api/quarterly-reviews/generate", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setReview(data);
    } catch (e) {
      setError("Fehler beim Generieren des Reviews");
    } finally {
      setGenerating(false);
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
          <BarChart3 size={28} className="text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Quartals-Review</h1>
            <p className="text-zinc-400 text-sm">
              {review ? review.quarter_label : "Noch kein Review vorhanden"}
            </p>
          </div>
        </div>
        <button
          onClick={generateReview}
          disabled={generating}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
        >
          <RefreshCw size={16} className={generating ? "animate-spin" : ""} />
          {generating ? "Generiert..." : "Jetzt generieren"}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">{error}</div>
      )}

      {!review ? (
        <div className="text-center py-16 text-zinc-500">
          <BarChart3 size={48} className="mx-auto mb-4 opacity-30" />
          <p>Noch kein Quartals-Review. Klicke auf &ldquo;Jetzt generieren&rdquo;.</p>
        </div>
      ) : (
        <>
          {/* Life Score */}
          <div className="bg-gradient-to-br from-indigo-900/40 to-purple-900/40 border border-indigo-700/50 rounded-2xl p-6 text-center">
            <div className={`text-7xl font-black mb-2 ${scoreColor(review.life_score ?? 0)}`}>
              {review.life_score ?? "—"}
            </div>
            <div className="text-zinc-300 text-lg font-medium">Life Score</div>
            <div className="text-zinc-500 text-sm mt-1">{review.quarter_label}</div>
            {review.generated_at && (
              <div className="text-zinc-600 text-xs mt-2">
                Generiert: {new Date(review.generated_at).toLocaleDateString("de-DE")}
              </div>
            )}
          </div>

          {/* Highlights & Challenges */}
          {(review.highlights?.length || review.challenges?.length) ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {review.highlights?.length ? (
                <div className="bg-green-900/20 border border-green-700/40 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Award size={18} className="text-green-400" />
                    <h3 className="text-green-300 font-semibold">Highlights</h3>
                  </div>
                  <ul className="space-y-2">
                    {review.highlights.map((h, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                        <span className="text-green-400 mt-0.5">✓</span>
                        {h}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {review.challenges?.length ? (
                <div className="bg-orange-900/20 border border-orange-700/40 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle size={18} className="text-orange-400" />
                    <h3 className="text-orange-300 font-semibold">Herausforderungen</h3>
                  </div>
                  <ul className="space-y-2">
                    {review.challenges.map((c, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                        <span className="text-orange-400 mt-0.5">→</span>
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}

          {/* Objectives Grading */}
          {review.objectives_data?.length ? (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
              <h2 className="text-white font-semibold mb-4">Objectives ({review.objectives_data.length})</h2>
              <div className="space-y-3">
                {review.objectives_data.map((obj) => (
                  <div key={obj.id}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs bg-zinc-700 text-zinc-300 px-2 py-0.5 rounded flex-shrink-0">
                          {CATEGORY_LABELS[obj.category] || obj.category}
                        </span>
                        <span className="text-sm text-zinc-200 truncate">{obj.title}</span>
                      </div>
                      <span className={`text-sm font-bold flex-shrink-0 ml-2 ${
                        obj.grade >= 0.8 ? "text-green-400" :
                        obj.grade >= 0.5 ? "text-yellow-400" :
                        "text-red-400"
                      }`}>
                        {obj.grade_pct}%
                      </span>
                    </div>
                    <div className="w-full bg-zinc-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${gradeColor(obj.grade)}`}
                        style={{ width: `${obj.grade_pct}%` }}
                      />
                    </div>
                    <div className="text-xs text-zinc-500 mt-0.5">{obj.kr_count} KRs</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {/* AI Analysis */}
          {review.ai_analysis && (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4">
              <h2 className="text-white font-semibold mb-3">KI-Analyse</h2>
              <p className="text-zinc-300 text-sm leading-relaxed whitespace-pre-wrap">
                {review.ai_analysis}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
