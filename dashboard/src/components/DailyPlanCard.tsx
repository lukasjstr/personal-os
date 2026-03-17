"use client";

import React, { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { DailyContext } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useSWRConfig } from "swr";

const ENERGY_COLOR: Record<string, string> = {
  low: "text-zinc-400 bg-zinc-800/60 border-zinc-700",
  medium: "text-yellow-400 bg-yellow-900/20 border-yellow-800/40",
  high: "text-emerald-400 bg-emerald-900/20 border-emerald-800/40",
};

const ENERGY_LABEL: Record<string, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
};

const ENERGY_ICON: Record<string, string> = {
  low: "😴",
  medium: "⚙️",
  high: "⚡",
};

interface DailyPlanCardProps {
  context: DailyContext | undefined;
  onRegenerate?: () => void;
}

export default function DailyPlanCard({ context, onRegenerate }: DailyPlanCardProps) {
  const { mutate } = useSWRConfig();
  const [generating, setGenerating] = useState(false);
  const plan = context?.daily_plan;

  async function handleRegenerate() {
    setGenerating(true);
    try {
      await api.generateDailyPlan();
      await mutate("daily-context");
      onRegenerate?.();
    } catch {
      // silently fail
    } finally {
      setGenerating(false);
    }
  }

  if (!plan) {
    return (
      <div className="text-zinc-500 text-sm italic">
        Noch kein Tagesplan generiert.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Motivational kickoff */}
      {plan.motivational_kickoff && (
        <p className="text-zinc-300 text-sm italic border-l-2 border-blue-500 pl-3">
          {plan.motivational_kickoff}
        </p>
      )}

      {/* Top tasks */}
      <div className="space-y-2">
        {plan.top_tasks.map((task, idx) => (
          <div
            key={task.task_id}
            className="flex items-start gap-3 bg-zinc-800/50 rounded-lg px-3 py-2.5 border border-zinc-700/50"
          >
            <span className="text-zinc-600 font-bold text-sm shrink-0 mt-0.5 w-5 text-center">
              {idx + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-white text-sm font-medium truncate">{task.title}</div>
              {task.objective_title && (
                <div className="text-zinc-500 text-xs mt-0.5 truncate">
                  {task.kr_title ? `${task.objective_title} › ${task.kr_title}` : task.objective_title}
                </div>
              )}
              {task.reason && (
                <div className="text-zinc-600 text-xs mt-1 line-clamp-1">{task.reason}</div>
              )}
            </div>
            <div className="shrink-0 flex items-center gap-2">
              {task.estimated_minutes > 0 && (
                <span className="text-zinc-500 text-xs whitespace-nowrap">
                  {task.estimated_minutes}min
                </span>
              )}
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded border",
                  ENERGY_COLOR[task.energy_required] ?? ENERGY_COLOR.medium
                )}
              >
                {ENERGY_ICON[task.energy_required]} {ENERGY_LABEL[task.energy_required] ?? task.energy_required}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Focus block */}
      {plan.focus_block && (
        <div className="bg-blue-950/30 border border-blue-800/30 rounded-lg px-3 py-2.5">
          <div className="text-blue-400 text-xs font-semibold uppercase tracking-wider mb-1">
            🎯 Focus Block
          </div>
          <div className="text-blue-200 text-sm">
            {plan.focus_block.suggested_start} · {plan.focus_block.duration_minutes} min
          </div>
          {plan.focus_block.description && (
            <div className="text-blue-300/70 text-xs mt-0.5">{plan.focus_block.description}</div>
          )}
        </div>
      )}

      {/* Footer actions */}
      <div className="flex items-center justify-between pt-1">
        <Link
          href="/tasks"
          className="text-blue-400 hover:text-blue-300 text-xs transition-colors"
        >
          Alle Tasks ansehen →
        </Link>
        <button
          onClick={handleRegenerate}
          disabled={generating}
          className="text-zinc-500 hover:text-zinc-300 text-xs transition-colors disabled:opacity-50"
        >
          {generating ? "Generiert…" : "↺ Plan neu generieren"}
        </button>
      </div>
    </div>
  );
}
