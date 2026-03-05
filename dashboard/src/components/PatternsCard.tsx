"use client";

import useSWR from "swr";
import { api, BehavioralPatterns } from "@/lib/api";
import { cn } from "@/lib/utils";

function MoodArrow({ direction }: { direction: "up" | "down" | "stable" }) {
  if (direction === "up") return <span className="text-emerald-400">↑</span>;
  if (direction === "down") return <span className="text-red-400">↓</span>;
  return <span className="text-zinc-500">→</span>;
}

export default function PatternsCard() {
  const { data, error } = useSWR<BehavioralPatterns>(
    "autopilot-patterns",
    api.autopilotPatterns,
    { refreshInterval: 600_000 }
  );

  if (error || !data) return null;

  const { missed_routines, drifting_objectives, mood_trend } = data;
  const hasPatterns =
    missed_routines.length > 0 || drifting_objectives.length > 0 || mood_trend !== null;

  if (!hasPatterns) return null;

  return (
    <div className="bg-zinc-900 border border-amber-500/20 rounded-xl p-5 mb-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-amber-400 font-semibold text-sm">🔍 Erkannte Muster</span>
        <span className="text-xs text-zinc-600">Automatische Analyse</span>
      </div>

      <div className="space-y-4">
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
