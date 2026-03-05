"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import Header from "@/components/Header";
import { api, DailySuggestionsHistoryEntry, DailySuggestions } from "@/lib/api";
import { cn } from "@/lib/utils";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "long" });
}

function SuggestionsCard({ date, suggestions }: { date: string; suggestions: DailySuggestions }) {
  const [open, setOpen] = useState(date === new Date().toISOString().split("T")[0]);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-white font-semibold text-sm">{formatDate(date)}</span>
          {date === new Date().toISOString().split("T")[0] && (
            <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded-full">Heute</span>
          )}
        </div>
        <span className="text-zinc-600 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-zinc-800">
          {/* Focus tasks */}
          {suggestions.fokus_heute && suggestions.fokus_heute.length > 0 && (
            <div className="pt-4">
              <div className="text-zinc-500 text-xs uppercase tracking-wide mb-2">Fokus heute</div>
              <div className="space-y-2">
                {suggestions.fokus_heute.map((item, i) => (
                  <div key={i} className="flex gap-3 bg-zinc-800/50 rounded-lg px-3 py-2.5">
                    <span className="text-blue-400 font-bold text-sm shrink-0">{i + 1}.</span>
                    <div>
                      <div className="text-white text-sm font-medium">{item.task}</div>
                      <div className="text-zinc-500 text-xs mt-0.5">{item.begruendung}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tip */}
          {suggestions.tipp && (
            <div>
              <div className="text-zinc-500 text-xs uppercase tracking-wide mb-1.5">Tipp des Tages</div>
              <p className="text-zinc-300 text-sm bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2.5">
                {suggestions.tipp}
              </p>
            </div>
          )}

          {/* Streak warning */}
          {suggestions.streak_warnung && (
            <div>
              <div className="text-zinc-500 text-xs uppercase tracking-wide mb-1.5">Streak-Warnung</div>
              <p className="text-orange-400 text-sm bg-orange-500/10 border border-orange-500/20 rounded-lg px-3 py-2.5">
                {suggestions.streak_warnung}
              </p>
            </div>
          )}

          {/* Dimension check */}
          {suggestions.dimension_check && (
            <div>
              <div className="text-zinc-500 text-xs uppercase tracking-wide mb-1.5">Dimensions-Check</div>
              <p className="text-zinc-300 text-sm bg-purple-500/10 border border-purple-500/20 rounded-lg px-3 py-2.5">
                {suggestions.dimension_check}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SuggestionsPage() {
  const [days, setDays] = useState(14);
  const [regenerating, setRegenerating] = useState(false);

  const { data, error, isLoading } = useSWR(
    `suggestions-history-${days}`,
    () => api.suggestionsHistory(days),
    { refreshInterval: 300_000 }
  );

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      await api.regenerateSuggestions();
      await mutate(`suggestions-history-${days}`);
    } catch {
      // fail silently
    } finally {
      setRegenerating(false);
    }
  };

  const history: DailySuggestionsHistoryEntry[] = data?.history ?? [];

  return (
    <div>
      <Header
        title="AI Suggestions"
        subtitle="Tägliche KI-Empfehlungen für deinen Fokus"
        action={
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 disabled:opacity-50"
            )}
          >
            {regenerating ? "Generiere..." : "🤖 Neu generieren"}
          </button>
        }
      />

      {/* Day filter */}
      <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1 w-fit mb-5">
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={cn(
              "px-3 py-1 rounded-md text-sm transition-colors",
              days === d ? "bg-zinc-700 text-white" : "text-zinc-500 hover:text-zinc-300"
            )}
          >
            {d}d
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-4 py-3 mb-4 text-red-400 text-sm">
          Suggestions konnten nicht geladen werden.
        </div>
      )}

      {isLoading && (
        <div className="text-zinc-500 text-sm">Laden…</div>
      )}

      {!isLoading && history.length === 0 && !error && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500 text-sm">
          Noch keine Suggestions vorhanden. Klicke "Neu generieren" um die heutigen KI-Empfehlungen zu erstellen.
        </div>
      )}

      <div className="space-y-3">
        {history.map((entry) => (
          <SuggestionsCard key={entry.date} date={entry.date} suggestions={entry.suggestions} />
        ))}
      </div>
    </div>
  );
}
