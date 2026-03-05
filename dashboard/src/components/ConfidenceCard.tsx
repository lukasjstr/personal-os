"use client";

import useSWR from "swr";
import { api, AutopilotConfidence } from "@/lib/api";
import { cn } from "@/lib/utils";

const SCORE_DIMS = [
  { key: "data_recency", label: "Aktivität" },
  { key: "objective_coverage", label: "Ziele" },
  { key: "routine_adherence", label: "Routinen" },
  { key: "reflection_freshness", label: "Reflexion" },
] as const;

const SEVERITY_COLOR: Record<string, string> = {
  high: "text-red-400 bg-red-950/40 border-red-900/50",
  medium: "text-orange-400 bg-orange-950/40 border-orange-900/50",
  low: "text-yellow-400 bg-yellow-950/40 border-yellow-900/50",
};

const LEVEL_COLOR: Record<string, string> = {
  high: "text-emerald-400",
  medium: "text-yellow-400",
  low: "text-red-400",
};

const LEVEL_BG: Record<string, string> = {
  high: "border-emerald-500/30 bg-emerald-500/5",
  medium: "border-yellow-500/30 bg-yellow-500/5",
  low: "border-red-500/30 bg-red-500/5",
};

export default function ConfidenceCard() {
  const { data, error } = useSWR<AutopilotConfidence>(
    "autopilot-confidence",
    api.autopilotConfidence,
    { refreshInterval: 300_000 }
  );

  if (error || !data) return null;

  const { confidence, level, scores, escalations } = data;

  return (
    <div className={cn("border rounded-xl p-5 mb-4", LEVEL_BG[level])}>
      <div className="flex items-center justify-between mb-4">
        <span className="text-white font-semibold text-sm">Autopilot Confidence</span>
        <div className="flex items-center gap-2">
          <span className={cn("text-2xl font-bold", LEVEL_COLOR[level])}>{confidence}</span>
          <span className="text-zinc-500 text-sm">/100</span>
        </div>
      </div>

      {/* Dimension bars */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {SCORE_DIMS.map(({ key, label }) => (
          <div key={key} className="text-center">
            <div className="text-zinc-500 text-xs mb-1">{label}</div>
            <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  scores[key] >= 20 ? "bg-emerald-500" :
                  scores[key] >= 10 ? "bg-yellow-500" : "bg-red-500"
                )}
                style={{ width: `${(scores[key] / 25) * 100}%` }}
              />
            </div>
            <div className="text-zinc-600 text-xs mt-0.5">{scores[key]}/25</div>
          </div>
        ))}
      </div>

      {/* Escalations */}
      {escalations.length > 0 && (
        <div className="space-y-1.5">
          {escalations.map((e, i) => (
            <div
              key={i}
              className={cn(
                "flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-lg border",
                SEVERITY_COLOR[e.severity]
              )}
            >
              <span className="shrink-0">
                {e.severity === "high" ? "🔴" : e.severity === "medium" ? "🟡" : "🟢"}
              </span>
              <span>{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
