"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, BehavioralPatterns, PatternInsightsResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

function MoodArrow({ direction }: { direction: "up" | "down" | "stable" }) {
  if (direction === "up") return <span className="text-emerald-400">↑</span>;
  if (direction === "down") return <span className="text-red-400">↓</span>;
  return <span className="text-zinc-500">→</span>;
}

function insightIcon(type: string): string {
  const icons: Record<string, string> = {
    kr_risk: "⚠️",
    strength: "💪",
    productivity_pattern: "📈",
    blocker: "🚧",
    habit: "🔄",
    preference: "💡",
  };
  return icons[type] ?? "📊";
}

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-400";
  if (score >= 50) return "text-yellow-400";
  return "text-red-400";
}

function scoreRingColor(score: number): string {
  if (score >= 75) return "stroke-emerald-400";
  if (score >= 50) return "stroke-yellow-400";
  return "stroke-red-400";
}

function ConsistencyRing({ score, label }: { score: number; label: string }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 72 72">
          <circle
            cx="36" cy="36" r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="6"
            className="text-zinc-800"
          />
          <circle
            cx="36" cy="36" r={radius}
            fill="none"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={scoreRingColor(score)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-lg font-bold leading-none", scoreColor(score))}>{score}</span>
          <span className="text-zinc-500 text-[10px]">/ 100</span>
        </div>
      </div>
      <span className={cn("text-xs font-medium", scoreColor(score))}>{label}</span>
    </div>
  );
}

export default function PatternsCard() {
  const [refreshing, setRefreshing] = useState(false);

  const { data: patternInsights, mutate: mutateInsights } = useSWR<PatternInsightsResponse>(
    "autopilot-pattern-insights",
    api.patternInsights,
    { refreshInterval: 600_000 }
  );

  const { data: behavioralData } = useSWR<BehavioralPatterns>(
    "autopilot-patterns",
    api.autopilotPatterns,
    { refreshInterval: 600_000 }
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshPatternInsights();
      await mutateInsights();
    } finally {
      setRefreshing(false);
    }
  };

  const consistency = patternInsights?.consistency_score ?? null;
  const insights = patternInsights?.insights ?? [];
  const { missed_routines = [], drifting_objectives = [], mood_trend = null } = behavioralData ?? {};

  const hasContent =
    insights.length > 0 ||
    missed_routines.length > 0 ||
    drifting_objectives.length > 0 ||
    mood_trend !== null ||
    consistency !== null;

  if (!hasContent) return null;

  return (
    <div className="bg-zinc-900 border border-amber-500/20 rounded-xl p-5 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-amber-400 font-semibold text-sm">🔍 Muster & Analyse</span>
          <span className="text-xs text-zinc-600">Automatische Analyse</span>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1 transition-colors disabled:opacity-50"
        >
          {refreshing ? "Analysiere…" : "Neu analysieren"}
        </button>
      </div>

      <div className="space-y-5">
        {/* Consistency score + components */}
        {consistency && (
          <div className="flex items-start gap-4">
            <ConsistencyRing score={consistency.score} label={consistency.label} />
            <div className="flex-1 space-y-2 pt-1">
              <div className="text-zinc-400 text-xs uppercase tracking-wide mb-2">Konsistenz (30 Tage)</div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Routinen</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-amber-500 rounded-full"
                        style={{ width: `${consistency.components.routine_rate}%` }}
                      />
                    </div>
                    <span className="text-zinc-500 w-8 text-right">{consistency.components.routine_rate}%</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Tasks</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${consistency.components.task_rate}%` }}
                      />
                    </div>
                    <span className="text-zinc-500 w-8 text-right">{consistency.components.task_rate}%</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Logging</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 rounded-full"
                        style={{ width: `${consistency.components.logging_rate}%` }}
                      />
                    </div>
                    <span className="text-zinc-500 w-8 text-right">{consistency.components.logging_rate}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* AI-generated pattern insights */}
        {insights.length > 0 && (
          <div>
            <div className="text-zinc-500 text-xs uppercase tracking-wide mb-2">Erkannte Muster</div>
            <div className="space-y-2">
              {insights.slice(0, 6).map((ins) => (
                <div key={ins.id} className="bg-zinc-800/60 rounded-lg px-3 py-2.5">
                  <div className="flex items-start gap-2">
                    <span className="text-base leading-none mt-0.5">{insightIcon(ins.type)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-zinc-200 text-sm font-medium leading-snug">{ins.title}</div>
                      <div className="text-zinc-400 text-xs mt-0.5 leading-relaxed">{ins.description}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mood trend */}
        {mood_trend && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-400">Stimmung letzte 7 Tage</span>
            <div className="flex items-center gap-1.5">
              <MoodArrow direction={mood_trend.direction} />
              <span className={cn(
                "font-medium",
                mood_trend.direction === "up" ? "text-emerald-400" :
                mood_trend.direction === "down" ? "text-red-400" : "text-zinc-400"
              )}>
                {mood_trend.recent_avg}/10
              </span>
              <span className="text-zinc-600 text-xs">(war {mood_trend.prior_avg})</span>
            </div>
          </div>
        )}

        {/* Missed routines */}
        {missed_routines.length > 0 && (
          <div>
            <div className="text-zinc-500 text-xs uppercase tracking-wide mb-2">Vernachlässigte Routinen</div>
            <div className="space-y-1.5">
              {missed_routines.slice(0, 3).map((r) => (
                <div key={r.id} className="flex items-center justify-between text-sm">
                  <span className="text-zinc-300 truncate mr-3">{r.title}</span>
                  <div className="shrink-0 flex items-center gap-1.5">
                    <div className="w-16 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full",
                          r.completion_rate < 20 ? "bg-red-500" :
                          r.completion_rate < 40 ? "bg-orange-500" : "bg-yellow-500"
                        )}
                        style={{ width: `${r.completion_rate}%` }}
                      />
                    </div>
                    <span className="text-zinc-500 text-xs w-8 text-right">{r.completion_rate}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Drifting objectives */}
        {drifting_objectives.length > 0 && (
          <div>
            <div className="text-zinc-500 text-xs uppercase tracking-wide mb-2">Inaktive Ziele (14+ Tage)</div>
            <div className="flex flex-wrap gap-1.5">
              {drifting_objectives.slice(0, 4).map((obj) => (
                <span
                  key={obj.id}
                  className="text-xs px-2 py-1 bg-zinc-800 border border-zinc-700 rounded-full text-zinc-400"
                >
                  {obj.title}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
