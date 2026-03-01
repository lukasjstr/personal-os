"use client";

import { useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useBrainDumps } from "@/hooks/useApi";
import { formatDateTime, formatTimeAgo, cn } from "@/lib/utils";
import type { BrainDump } from "@/lib/api";
import { Search } from "lucide-react";

function BrainDumpCard({ dump }: { dump: BrainDump }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = dump.raw_input.length > 200;

  return (
    <div
      className={cn(
        "bg-zinc-900 border rounded-xl overflow-hidden transition-all cursor-pointer",
        dump.processed ? "border-zinc-800 hover:border-zinc-700" : "border-blue-900/60 hover:border-blue-800"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 pt-4 pb-2">
        <span className="text-xl">🧠</span>
        <span className="text-zinc-500 text-xs flex-1">{formatTimeAgo(dump.created_at)}</span>
        <div className="flex items-center gap-2">
          {!dump.processed && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900/60 text-blue-400 border border-blue-800/50">
              Neu
            </span>
          )}
          {dump.processed && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-900/50 text-green-400 border border-green-800/50">
              Verarbeitet
            </span>
          )}
          {dump.linked_objective_id && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-violet-900/50 text-violet-400 border border-violet-800/50">
              🎯 Linked
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-5 pb-4">
        <p className={cn("text-white text-sm leading-relaxed", !expanded && isLong && "line-clamp-3")}>
          {dump.raw_input}
        </p>

        {/* AI interpretation - always show a preview, expand on click */}
        {dump.ai_interpretation && (
          <div className={cn("mt-3 pl-3 border-l-2 border-blue-600/70", !expanded && "line-clamp-2")}>
            <div className="text-xs text-zinc-500 mb-1">🤖 KI-Interpretation</div>
            <p className="text-blue-300 text-sm leading-relaxed">{dump.ai_interpretation}</p>
          </div>
        )}

        {isLong && (
          <button className="text-xs text-zinc-500 mt-2 hover:text-zinc-300 transition-colors">
            {expanded ? "Weniger anzeigen ↑" : "Mehr anzeigen ↓"}
          </button>
        )}

        <div className="text-zinc-600 text-xs mt-2">{formatDateTime(dump.created_at)}</div>
      </div>
    </div>
  );
}

export default function BrainDumpsPage() {
  const { data, error, isLoading } = useBrainDumps();
  const [search, setSearch] = useState("");
  const [filterProcessed, setFilterProcessed] = useState<boolean | null>(null);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  let dumps = data?.brain_dumps ?? [];

  if (filterProcessed !== null) {
    dumps = dumps.filter((d) => d.processed === filterProcessed);
  }

  if (search.trim()) {
    const q = search.toLowerCase();
    dumps = dumps.filter(
      (d) =>
        d.raw_input.toLowerCase().includes(q) ||
        (d.ai_interpretation?.toLowerCase().includes(q) ?? false)
    );
  }

  const all = data?.brain_dumps ?? [];
  const unprocessed = all.filter((d) => !d.processed).length;
  const withLinked = all.filter((d) => d.linked_objective_id).length;

  return (
    <div>
      <Header
        title="🧠 Brain Dumps"
        subtitle={`${all.length} gesamt · ${unprocessed} unverarbeitet · ${withLinked} verknüpft`}
      />

      {/* Search & Filter */}
      <div className="flex flex-col gap-3 mb-6">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Brain Dumps durchsuchen..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-4 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
        <div className="flex gap-2">
          {([
            [null, "Alle", "bg-zinc-800 text-zinc-400"],
            [false, "Unverarbeitet", "bg-blue-900/60 text-blue-400 border-blue-800"],
            [true, "Verarbeitet", "bg-green-900/50 text-green-400 border-green-800"],
          ] as const).map(([val, label, activeStyle]) => (
            <button
              key={String(val)}
              onClick={() => setFilterProcessed(val)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm border transition-colors",
                filterProcessed === val
                  ? `${activeStyle} border-current`
                  : "bg-zinc-900 text-zinc-400 border-zinc-700 hover:text-white hover:border-zinc-600"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {dumps.length === 0 ? (
        <EmptyState emoji="🧠" message="Keine Brain Dumps gefunden" />
      ) : (
        <div className="space-y-4">
          {dumps.map((dump) => (
            <BrainDumpCard key={dump.id} dump={dump} />
          ))}
          <div className="text-center text-xs text-zinc-600 py-2">{dumps.length} Brain Dumps</div>
        </div>
      )}
    </div>
  );
}
