"use client";

import { useState } from "react";
import Header from "@/components/Header";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useBrainDumps } from "@/hooks/useApi";
import { formatDateTime, cn } from "@/lib/utils";
import type { BrainDump } from "@/lib/api";
import { Search } from "lucide-react";

function BrainDumpCard({ dump }: { dump: BrainDump }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "bg-zinc-900 border rounded-xl p-5 cursor-pointer transition-all hover:border-zinc-700",
        dump.processed ? "border-zinc-800" : "border-blue-900"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl mt-0.5">🧠</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-zinc-500 text-xs">{formatDateTime(dump.created_at)}</span>
            {!dump.processed && <Badge variant="blue">Neu</Badge>}
            {dump.processed && <Badge variant="green">Verarbeitet</Badge>}
            {dump.linked_objective_id && (
              <Badge variant="purple">🎯 Objective</Badge>
            )}
          </div>

          <p
            className={cn(
              "text-white text-sm leading-relaxed",
              !expanded && "line-clamp-3"
            )}
          >
            {dump.raw_input}
          </p>

          {dump.ai_interpretation && (
            <div
              className={cn(
                "mt-3 pl-3 border-l-2 border-blue-700",
                !expanded && "hidden"
              )}
            >
              <div className="text-xs text-zinc-500 mb-1">🤖 KI Interpretation:</div>
              <p className="text-blue-300 text-sm">{dump.ai_interpretation}</p>
            </div>
          )}

          {dump.ai_interpretation && !expanded && (
            <div className="mt-2 pl-3 border-l-2 border-blue-700">
              <p className="text-blue-300 text-xs truncate">{dump.ai_interpretation}</p>
            </div>
          )}
        </div>
      </div>

      {dump.raw_input.length > 200 && (
        <button className="text-xs text-zinc-500 mt-2 hover:text-zinc-300 ml-8">
          {expanded ? "Weniger anzeigen ↑" : "Mehr anzeigen ↓"}
        </button>
      )}
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

  return (
    <div>
      <Header
        title="🧠 Brain Dumps"
        subtitle={`${all.length} gesamt · ${unprocessed} unverarbeitet`}
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
            [null, "Alle"],
            [false, "Unverarbeitet"],
            [true, "Verarbeitet"],
          ] as const).map(([val, label]) => (
            <button
              key={String(val)}
              onClick={() => setFilterProcessed(val)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm transition-colors",
                filterProcessed === val
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:text-white"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Dumps List */}
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
