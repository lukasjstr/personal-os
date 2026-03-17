"use client";

import { useState } from "react";
import { RefreshCw, TrendingUp, TrendingDown, Minus } from "lucide-react";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { CorrelationInsight } from "@/lib/api";

function strengthColor(strength: string): string {
  if (strength === "stark") return "text-green-400";
  if (strength === "moderat") return "text-yellow-400";
  return "text-zinc-400";
}

function strengthBg(strength: string): string {
  if (strength === "stark") return "bg-green-500/20 border-green-500/30";
  if (strength === "moderat") return "bg-yellow-500/15 border-yellow-500/30";
  return "bg-zinc-500/10 border-zinc-500/30";
}

function CorrelationIcon({ r }: { r: number }) {
  if (r > 0.3) return <TrendingUp className="h-4 w-4 text-green-400" />;
  if (r < -0.3) return <TrendingDown className="h-4 w-4 text-red-400" />;
  return <Minus className="h-4 w-4 text-zinc-500" />;
}

function RBar({ r }: { r: number }) {
  const width = Math.min(Math.abs(r) * 100, 100);
  const color = r > 0 ? "bg-green-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-zinc-700 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
      <span className="text-xs text-zinc-500 font-mono">{r > 0 ? "+" : ""}{r.toFixed(2)}</span>
    </div>
  );
}

export default function CorrelationCard() {
  const { data, isLoading, mutate } = useSWR("correlations", () => api.correlations());
  const [refreshing, setRefreshing] = useState(false);

  const correlations: CorrelationInsight[] = data?.correlations ?? [];

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshCorrelations();
      await mutate();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <span className="text-lg">🔗</span>
          Korrelationen
        </h3>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-50"
          title="Korrelationen neu berechnen"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        </div>
      ) : correlations.length === 0 ? (
        <p className="text-zinc-500 text-sm py-4 text-center">
          Noch keine Korrelationen gefunden. Mehr Daten loggen (Mood, Schlaf, Training, Wasser) und erneut analysieren.
        </p>
      ) : (
        <div className="space-y-3">
          {correlations.map((c, i) => (
            <div
              key={i}
              className={`rounded-lg border p-3 ${strengthBg(c.data.strength)}`}
            >
              <div className="flex items-start gap-2">
                <CorrelationIcon r={c.data.correlation_r} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-white font-medium truncate">{c.title}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${strengthColor(c.data.strength)}`}>
                      {c.data.strength}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 leading-relaxed">{c.description}</p>
                  <div className="mt-2 flex items-center gap-3">
                    <RBar r={c.data.correlation_r} />
                    <span className="text-xs text-zinc-600">{c.data.n_pairs} Datenpunkte</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-zinc-600 mt-3">
        Basierend auf {data?.analysis_days ?? 30} Tagen Daten
      </p>
    </div>
  );
}
