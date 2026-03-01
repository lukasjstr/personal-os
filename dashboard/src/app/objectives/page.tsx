"use client";

import Header from "@/components/Header";
import ProgressBar from "@/components/ProgressBar";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useObjectives } from "@/hooks/useApi";
import { CATEGORY_EMOJI, formatDate, cn } from "@/lib/utils";
import type { Objective } from "@/lib/api";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const STATUS_BADGE: Record<string, "green" | "blue" | "yellow" | "red" | "outline"> = {
  active: "green",
  completed: "blue",
  paused: "yellow",
  abandoned: "red",
};

const CATEGORY_BADGE: Record<string, "green" | "blue" | "yellow" | "purple" | "outline" | "orange"> = {
  health: "green",
  fitness: "blue",
  finance: "yellow",
  learning: "purple",
  personal: "outline",
  business: "orange",
  relationships: "green",
};

const STATUS_LABEL: Record<string, string> = {
  active: "Aktiv",
  completed: "Abgeschlossen",
  paused: "Pausiert",
  abandoned: "Aufgegeben",
};

const KR_TYPE_LABEL: Record<string, string> = {
  percentage: "%",
  number: "#",
  boolean: "✓",
  streak: "🔥",
  checklist: "☑",
};

function ObjectiveCard({ obj }: { obj: Objective }) {
  const [expanded, setExpanded] = useState(obj.status === "active");
  const isLifeArea = obj.key_results.length === 0;

  const avgProgress =
    obj.key_results.length > 0
      ? Math.round(
          obj.key_results.reduce((s, kr) => s + kr.progress_pct, 0) / obj.key_results.length
        )
      : 0;

  const progressColor =
    avgProgress >= 75 ? "green" : avgProgress >= 40 ? "blue" : avgProgress >= 20 ? "yellow" : "red";

  return (
    <div className={cn("bg-zinc-900 border rounded-xl overflow-hidden", isLifeArea ? "border-zinc-700 opacity-80" : "border-zinc-800")}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 p-5 hover:bg-zinc-800/50 transition-colors text-left"
      >
        <span className="text-2xl">{CATEGORY_EMOJI[obj.category] ?? "🎯"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={cn("font-semibold", isLifeArea ? "text-zinc-300" : "text-white")}>{obj.title}</h3>
            <Badge variant={STATUS_BADGE[obj.status] ?? "outline"}>
              {STATUS_LABEL[obj.status] ?? obj.status}
            </Badge>
            <Badge variant={CATEGORY_BADGE[obj.category] ?? "outline"}>
              {obj.category}
            </Badge>
            {isLifeArea && (
              <Badge variant="outline">Life Area</Badge>
            )}
          </div>
          {obj.description && (
            <p className="text-zinc-500 text-sm mt-0.5 truncate">{obj.description}</p>
          )}
          {!isLifeArea && (
            <div className="flex items-center gap-4 mt-2">
              <ProgressBar value={avgProgress} showValue={false} size="sm" color={progressColor} />
              <span className="text-xs text-zinc-400 shrink-0 w-10 text-right">{avgProgress}%</span>
            </div>
          )}
        </div>
        <div className="text-zinc-500 shrink-0">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </button>

      {/* Key Results */}
      {expanded && obj.key_results.length > 0 && (
        <div className="border-t border-zinc-800 divide-y divide-zinc-800/50">
          {obj.key_results.map((kr) => (
            <div key={kr.id} className="px-5 py-3 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                    {KR_TYPE_LABEL[kr.metric_type] ?? kr.metric_type}
                  </span>
                  <span className="text-sm text-zinc-300">{kr.title}</span>
                  {kr.status === "completed" && <span className="text-green-400 text-xs">✓</span>}
                </div>
                <ProgressBar value={kr.progress_pct} size="sm" showValue={false} color="blue" />
              </div>
              <div className="text-right shrink-0 w-32">
                <div className="text-sm text-white font-medium">
                  {kr.current_value}
                  {kr.unit ? ` ${kr.unit}` : ""}
                  {kr.target_value ? (
                    <span className="text-zinc-500 font-normal">
                      {" / "}
                      {kr.target_value}
                      {kr.unit ? ` ${kr.unit}` : ""}
                    </span>
                  ) : null}
                </div>
                <div className="text-xs text-zinc-500">{kr.progress_pct}%</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {expanded && obj.key_results.length === 0 && (
        <div className="border-t border-zinc-800 px-5 py-3">
          <p className="text-zinc-500 text-sm">Keine Key Results</p>
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-zinc-800 px-5 py-2.5 flex items-center gap-4 text-xs text-zinc-500">
        <span>{obj.key_results.length} KRs</span>
        {obj.target_date && <span>📅 Ziel: {formatDate(obj.target_date)}</span>}
        <span className="ml-auto">Erstellt: {formatDate(obj.created_at)}</span>
      </div>
    </div>
  );
}

const FILTERS = ["all", "active", "completed", "paused", "abandoned"] as const;
const FILTER_LABELS: Record<string, string> = {
  all: "Alle",
  active: "Aktiv",
  completed: "Abgeschlossen",
  paused: "Pausiert",
  abandoned: "Aufgegeben",
};

export default function ObjectivesPage() {
  const { data, error, isLoading } = useObjectives();
  const [filter, setFilter] = useState<string>("all");

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const all = data?.objectives ?? [];
  const filtered = filter === "all" ? all : all.filter((o) => o.status === filter);

  const counts = {
    all: all.length,
    active: all.filter((o) => o.status === "active").length,
    completed: all.filter((o) => o.status === "completed").length,
    paused: all.filter((o) => o.status === "paused").length,
    abandoned: all.filter((o) => o.status === "abandoned").length,
  };

  return (
    <div>
      <Header
        title="🎯 Objectives"
        subtitle={`${counts.active} aktiv · ${counts.completed} abgeschlossen`}
      />

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm transition-colors",
              filter === f
                ? "bg-blue-600 text-white"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            )}
          >
            {FILTER_LABELS[f]} ({counts[f]})
          </button>
        ))}
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <EmptyState emoji="🎯" message="Keine Objectives gefunden" />
      ) : (
        <div className="space-y-4">
          {filtered.map((obj) => (
            <ObjectiveCard key={obj.id} obj={obj} />
          ))}
        </div>
      )}
    </div>
  );
}
