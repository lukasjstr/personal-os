"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import type { Objective } from "@/lib/api";
import { CATEGORY_EMOJI, cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

interface GoalGroup {
  area: string;
  emoji: string;
  objectives: number[];
  insight: string;
  momentum_label: string;
}

interface GoalSynergy {
  objective_ids: number[];
  type: "reinforcing" | "sequential" | "shared_habit";
  title: string;
  description: string;
}

interface GoalDependency {
  from_objective_id: number;
  to_objective_id: number;
  description: string;
}

interface CrossObjectiveTask {
  title: string;
  category: string;
  priority: number;
  impacts_objective_ids: number[];
  why: string;
}

interface GoalInsight {
  type: "warning" | "opportunity" | "milestone";
  title: string;
  description: string;
  objective_id?: number;
}

interface GoalAnalysis {
  groups: GoalGroup[];
  synergies: GoalSynergy[];
  dependencies: GoalDependency[];
  cross_objective_tasks: CrossObjectiveTask[];
  insights: GoalInsight[];
  overall_momentum: "growing" | "stable" | "at_risk";
  motivational_message: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SYNERGY_LABEL: Record<string, string> = {
  reinforcing: "Verstärkt sich gegenseitig",
  sequential: "Aufeinander aufbauend",
  shared_habit: "Gemeinsame Gewohnheit",
};

const SYNERGY_STYLE: Record<string, string> = {
  reinforcing: "bg-green-900/30 text-green-400 border border-green-800/50",
  sequential: "bg-blue-900/30 text-blue-400 border border-blue-800/50",
  shared_habit: "bg-purple-900/30 text-purple-400 border border-purple-800/50",
};

const MOMENTUM_STYLE: Record<string, { badge: string; label: string }> = {
  growing: { badge: "bg-green-900/40 text-green-400 border border-green-800/50", label: "Wachsend" },
  stable: { badge: "bg-blue-900/40 text-blue-400 border border-blue-800/50", label: "Stabil" },
  at_risk: { badge: "bg-red-900/40 text-red-400 border border-red-800/50", label: "Gefährdet" },
};

const INSIGHT_CONFIG: Record<string, { icon: string; style: string; headerStyle: string }> = {
  warning: {
    icon: "⚠️",
    style: "bg-orange-900/20 border border-orange-800/40",
    headerStyle: "text-orange-400",
  },
  opportunity: {
    icon: "✨",
    style: "bg-green-900/20 border border-green-800/40",
    headerStyle: "text-green-400",
  },
  milestone: {
    icon: "🏆",
    style: "bg-blue-900/20 border border-blue-800/40",
    headerStyle: "text-blue-400",
  },
};

function avgKrProgress(obj: Objective): number {
  if (!obj.key_results || obj.key_results.length === 0) return 0;
  const total = obj.key_results.reduce((s, kr) => s + (kr.progress_pct ?? 0), 0);
  return Math.round(total / obj.key_results.length);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="text-white font-semibold text-sm">{title}</span>
      <div className="flex-1 h-px bg-zinc-800" />
    </div>
  );
}

function SynergyCard({
  synergy,
  objectives,
}: {
  synergy: GoalSynergy;
  objectives: Objective[];
}) {
  const objMap = new Map(objectives.map((o) => [o.id, o]));
  const involvedObjs = synergy.objective_ids.map((id) => objMap.get(id)).filter(Boolean) as Objective[];

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-white font-medium text-sm">{synergy.title}</span>
        <span className={cn("text-xs px-2 py-0.5 rounded-full shrink-0", SYNERGY_STYLE[synergy.type])}>
          {SYNERGY_LABEL[synergy.type] ?? synergy.type}
        </span>
      </div>
      <p className="text-zinc-400 text-xs leading-relaxed">{synergy.description}</p>
      {involvedObjs.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {involvedObjs.map((obj) => (
            <span
              key={obj.id}
              className="text-xs bg-zinc-800 text-zinc-300 border border-zinc-700 rounded-md px-2 py-0.5"
            >
              {CATEGORY_EMOJI[obj.category] ?? "🎯"} {obj.title}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function GroupCard({
  group,
  objectives,
}: {
  group: GoalGroup;
  objectives: Objective[];
}) {
  const objMap = new Map(objectives.map((o) => [o.id, o]));
  const groupObjs = group.objectives.map((id) => objMap.get(id)).filter(Boolean) as Objective[];

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{group.emoji}</span>
          <span className="text-white font-medium text-sm">{group.area}</span>
        </div>
        <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full border border-zinc-700">
          {group.momentum_label}
        </span>
      </div>
      {group.insight && (
        <p className="text-zinc-400 text-xs leading-relaxed">{group.insight}</p>
      )}
      {groupObjs.length > 0 && (
        <div className="space-y-2 pt-1">
          {groupObjs.map((obj) => {
            const progress = avgKrProgress(obj);
            return (
              <div key={obj.id} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-300 text-xs truncate flex-1 pr-2">
                    {CATEGORY_EMOJI[obj.category] ?? "🎯"} {obj.title}
                  </span>
                  <span className="text-zinc-500 text-xs shrink-0">{progress}%</span>
                </div>
                <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all"
                    style={{ width: `${Math.max(2, progress)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CrossTaskCard({
  task,
  objectives,
  onAdd,
  adding,
}: {
  task: CrossObjectiveTask;
  objectives: Objective[];
  onAdd: () => void;
  adding: boolean;
}) {
  const objMap = new Map(objectives.map((o) => [o.id, o]));
  const impacted = task.impacts_objective_ids
    .map((id) => objMap.get(id))
    .filter(Boolean) as Objective[];

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-white font-medium text-sm">{task.title}</div>
          {task.category && (
            <span className="text-xs text-zinc-500 mt-0.5">{task.category}</span>
          )}
        </div>
        <button
          onClick={onAdd}
          disabled={adding}
          className={cn(
            "shrink-0 px-3 py-1 rounded-lg text-xs font-medium transition-colors",
            adding
              ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 text-white"
          )}
        >
          {adding ? "…" : "Hinzufügen"}
        </button>
      </div>
      <p className="text-zinc-400 text-xs leading-relaxed">{task.why}</p>
      {impacted.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {impacted.map((obj) => (
            <span
              key={obj.id}
              className="text-xs bg-zinc-800/80 text-zinc-400 border border-zinc-700 rounded-md px-2 py-0.5"
            >
              {CATEGORY_EMOJI[obj.category] ?? "🎯"} {obj.title}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function InsightCard({ insight }: { insight: GoalInsight }) {
  const config = INSIGHT_CONFIG[insight.type] ?? INSIGHT_CONFIG.opportunity;
  return (
    <div className={cn("rounded-xl p-4 space-y-1", config.style)}>
      <div className="flex items-center gap-2">
        <span className="text-base">{config.icon}</span>
        <span className={cn("font-medium text-sm", config.headerStyle)}>{insight.title}</span>
      </div>
      <p className="text-zinc-300 text-xs leading-relaxed pl-6">{insight.description}</p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ObjectivesAnalysisPage() {
  const [analysis, setAnalysis] = useState<GoalAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addingTaskIdx, setAddingTaskIdx] = useState<number | null>(null);
  const [addedTasks, setAddedTasks] = useState<Set<number>>(new Set());
  const [taskError, setTaskError] = useState<string | null>(null);

  const { data: objectivesData } = useSWR("objectives", () => api.objectives(), {
    refreshInterval: 0,
  });

  const objectives: Objective[] = objectivesData?.objectives ?? [];

  const handleRunAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetch(
        `${typeof window !== "undefined" ? window.location.origin : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")}/api/goals/analysis`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("api_token") ?? "" : ""}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (!result.ok) {
        throw new Error(`Fehler ${result.status}: ${await result.text()}`);
      }
      const data: GoalAnalysis = await result.json();
      setAnalysis(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  };

  const handleAddTask = async (task: CrossObjectiveTask, idx: number) => {
    setAddingTaskIdx(idx);
    setTaskError(null);
    try {
      await api.createTask({
        title: task.title,
        category: task.category || null,
        priority: task.priority ?? 3,
      });
      setAddedTasks((prev) => new Set(prev).add(idx));
    } catch (e: unknown) {
      setTaskError(e instanceof Error ? e.message : "Task konnte nicht erstellt werden");
    } finally {
      setAddingTaskIdx(null);
    }
  };

  const momentumStyle = analysis ? MOMENTUM_STYLE[analysis.overall_momentum] : null;

  // Group insights by type for ordered display
  const warnings = analysis?.insights.filter((i) => i.type === "warning") ?? [];
  const opportunities = analysis?.insights.filter((i) => i.type === "opportunity") ?? [];
  const milestones = analysis?.insights.filter((i) => i.type === "milestone") ?? [];

  const objMap = new Map(objectives.map((o) => [o.id, o]));

  return (
    <div>
      <Header
        title="🔍 KI Zielanalyse"
        subtitle="GPT-gestützte Analyse deiner Ziele, Synergien und nächsten Schritte"
        action={
          <button
            onClick={handleRunAnalysis}
            disabled={loading}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              loading
                ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 text-white"
            )}
          >
            {loading ? "Analysiere…" : "Analyse aktualisieren"}
          </button>
        }
      />

      {/* Back link */}
      <div className="mb-5">
        <Link
          href="/objectives"
          className="text-zinc-500 hover:text-zinc-300 text-sm transition-colors inline-flex items-center gap-1"
        >
          ← Zurück zu Objectives
        </Link>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-4 py-3 mb-5 text-red-400 text-sm">
          {error}
        </div>
      )}

      {taskError && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-4 py-3 mb-5 text-red-400 text-sm">
          {taskError}
        </div>
      )}

      {/* Empty state */}
      {!analysis && !loading && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-10 text-center space-y-4">
          <div className="text-4xl">🔍</div>
          <div>
            <div className="text-white font-semibold text-base">Analyse starten</div>
            <div className="text-zinc-500 text-sm mt-1 max-w-sm mx-auto">
              Die KI analysiert deine Ziele auf Synergien, Gruppen, Abhängigkeiten und schlägt neue Tasks vor.
            </div>
          </div>
          <button
            onClick={handleRunAnalysis}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
          >
            🚀 Analyse starten
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-10 text-center space-y-3">
          <div className="flex justify-center">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
          <div className="text-zinc-400 text-sm">GPT analysiert deine Ziele…</div>
        </div>
      )}

      {/* Analysis results */}
      {analysis && !loading && (
        <div className="space-y-6">
          {/* Overall Momentum */}
          {momentumStyle && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-white font-semibold text-sm">Gesamt-Momentum</span>
                <span className={cn("text-xs px-2.5 py-1 rounded-full font-medium", momentumStyle.badge)}>
                  {momentumStyle.label}
                </span>
              </div>
              {analysis.motivational_message && (
                <p className="text-zinc-300 text-sm leading-relaxed italic">
                  &ldquo;{analysis.motivational_message}&rdquo;
                </p>
              )}
            </div>
          )}

          {/* Synergies */}
          {analysis.synergies.length > 0 && (
            <div>
              <SectionHeader title={`🔗 Synergien (${analysis.synergies.length})`} />
              <div className="grid gap-3 sm:grid-cols-2">
                {analysis.synergies.map((syn, i) => (
                  <SynergyCard key={i} synergy={syn} objectives={objectives} />
                ))}
              </div>
            </div>
          )}

          {/* Goal Groups */}
          {analysis.groups.length > 0 && (
            <div>
              <SectionHeader title={`📦 Ziel-Gruppen (${analysis.groups.length})`} />
              <div className="grid gap-3 sm:grid-cols-2">
                {analysis.groups.map((group, i) => (
                  <GroupCard key={i} group={group} objectives={objectives} />
                ))}
              </div>
            </div>
          )}

          {/* Cross-objective tasks */}
          {analysis.cross_objective_tasks.length > 0 && (
            <div>
              <SectionHeader title={`✅ Neue Task-Vorschläge (${analysis.cross_objective_tasks.length})`} />
              <div className="space-y-3">
                {analysis.cross_objective_tasks.map((task, i) => (
                  <CrossTaskCard
                    key={i}
                    task={task}
                    objectives={objectives}
                    onAdd={() => handleAddTask(task, i)}
                    adding={addingTaskIdx === i}
                  />
                ))}
              </div>
              {addedTasks.size > 0 && (
                <div className="mt-2 text-xs text-green-400">
                  {addedTasks.size} Task{addedTasks.size > 1 ? "s" : ""} hinzugefügt
                </div>
              )}
            </div>
          )}

          {/* Insights */}
          {(warnings.length > 0 || opportunities.length > 0 || milestones.length > 0) && (
            <div>
              <SectionHeader title={`💡 Insights (${analysis.insights.length})`} />
              <div className="space-y-2">
                {warnings.map((ins, i) => (
                  <InsightCard key={`w-${i}`} insight={ins} />
                ))}
                {milestones.map((ins, i) => (
                  <InsightCard key={`m-${i}`} insight={ins} />
                ))}
                {opportunities.map((ins, i) => (
                  <InsightCard key={`o-${i}`} insight={ins} />
                ))}
              </div>
            </div>
          )}

          {/* Dependencies */}
          {analysis.dependencies.length > 0 && (
            <div>
              <SectionHeader title={`🔀 Abhängigkeiten (${analysis.dependencies.length})`} />
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                {analysis.dependencies.map((dep, i) => {
                  const fromObj = objMap.get(dep.from_objective_id);
                  const toObj = objMap.get(dep.to_objective_id);
                  return (
                    <div
                      key={i}
                      className={cn(
                        "px-4 py-3 flex items-start gap-3",
                        i !== analysis.dependencies.length - 1 && "border-b border-zinc-800"
                      )}
                    >
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center gap-1.5 flex-wrap text-sm">
                          <span className="text-zinc-200">
                            {CATEGORY_EMOJI[fromObj?.category ?? ""] ?? "🎯"}{" "}
                            {fromObj?.title ?? `Ziel #${dep.from_objective_id}`}
                          </span>
                          <span className="text-zinc-600">→</span>
                          <span className="text-zinc-200">
                            {CATEGORY_EMOJI[toObj?.category ?? ""] ?? "🎯"}{" "}
                            {toObj?.title ?? `Ziel #${dep.to_objective_id}`}
                          </span>
                        </div>
                        <p className="text-zinc-500 text-xs">{dep.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
