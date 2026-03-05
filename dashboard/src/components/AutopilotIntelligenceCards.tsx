"use client";

import React, { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  useAutopilotDailyPlan,
  useAutopilotActionQueue,
  useAutopilotNextAction,
} from "@/hooks/useApi";
import type { AutopilotActionQueueItem } from "@/lib/api";

// ── Next Action Card ───────────────────────────────────────────────────────

function NextActionCard() {
  const { data, error } = useAutopilotNextAction();
  const [completing, setCompleting] = useState(false);
  const [done, setDone] = useState(false);

  if (error || !data) return null;

  const { task, reason, score } = data;
  const whyText =
    reason ??
    (score != null ? `Priority score: ${score}` : task.is_blocked ? "Task is currently blocked" : "Top unblocked task");

  async function handleComplete() {
    setCompleting(true);
    try {
      await api.completeTask(task.id);
      setDone(true);
    } catch {
      // best-effort
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="bg-zinc-900 border border-indigo-900/50 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">⚡ Next Action</span>
        {task.is_blocked && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/50 text-red-400">Blocked</span>
        )}
      </div>

      {task.objective_title && (
        <div className="text-xs text-zinc-500 mb-1 truncate">{task.objective_title}</div>
      )}

      <div
        className={cn(
          "text-white font-semibold text-base mb-2 leading-snug",
          done && "line-through text-zinc-500"
        )}
      >
        {task.title}
      </div>

      {task.category && (
        <div className="text-xs text-zinc-500 mb-2">{task.category}</div>
      )}

      <div className="text-xs text-zinc-600 mb-4">{whyText}</div>

      {task.blocker_title && (
        <div className="text-xs bg-red-950/40 border border-red-900/40 rounded px-3 py-2 text-red-400 mb-3">
          Blocked by: {task.blocker_title}
        </div>
      )}

      {done ? (
        <div className="text-sm text-green-400 font-medium">✓ Completed</div>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={handleComplete}
            disabled={completing || task.is_blocked}
            className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 transition-colors disabled:opacity-40"
          >
            {completing ? "…" : "Mark Done"}
          </button>
          <Link
            href="/tasks"
            className="px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-300 text-sm hover:bg-zinc-700 transition-colors"
          >
            Open Tasks →
          </Link>
        </div>
      )}
    </div>
  );
}

// ── Daily Plan Card ────────────────────────────────────────────────────────

function DailyPlanCard() {
  const { data, error } = useAutopilotDailyPlan();
  const [expanded, setExpanded] = useState(false);

  if (error || !data) return null;

  const totalItems = data.sections.reduce((n, s) => n + s.items.length, 0);
  const visibleSections = expanded ? data.sections : data.sections.slice(0, 2);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">📅 Today&apos;s Plan</span>
        <div className="flex items-center gap-2">
          {data.generated_by === "ai" && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-900/50 text-indigo-400">AI</span>
          )}
          <span className="text-xs text-zinc-600">{totalItems} items</span>
        </div>
      </div>

      <p className="text-sm text-zinc-300 mb-4">{data.summary}</p>

      {visibleSections.map((section) => (
        <div key={section.id} className="mb-3 last:mb-0">
          <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
            {section.title}
          </div>
          <div className="space-y-1">
            {section.items.slice(0, 3).map((item) => (
              <div key={item.id} className="flex items-start gap-2">
                <span className="text-zinc-600 mt-0.5 text-xs shrink-0">
                  {item.type === "task" ? "▶" : item.type === "routine" ? "↻" : "◈"}
                </span>
                <div className="min-w-0">
                  <span
                    className={cn(
                      "text-sm text-zinc-300 truncate block",
                      item.completed && "line-through text-zinc-600"
                    )}
                  >
                    {item.title}
                  </span>
                  {item.reason && (
                    <span className="text-xs text-zinc-600 truncate block">{item.reason}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {data.sections.length > 2 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-zinc-500 hover:text-zinc-300 mt-2 transition-colors"
        >
          {expanded ? "Show less ↑" : `Show ${data.sections.length - 2} more section${data.sections.length - 2 !== 1 ? "s" : ""} ↓`}
        </button>
      )}
    </div>
  );
}

// ── Action Queue Card ──────────────────────────────────────────────────────

const STATE_COLORS: Record<string, string> = {
  suggested: "bg-blue-900/50 text-blue-400",
  accepted: "bg-green-900/50 text-green-400",
  planned: "bg-zinc-800 text-zinc-400",
  snoozed: "bg-yellow-900/50 text-yellow-500",
  completed: "bg-zinc-800 text-zinc-600",
};

function ActionQueueCard() {
  const { data, error, mutate } = useAutopilotActionQueue();
  const [completing, setCompleting] = useState<number | null>(null);

  if (error || !data || data.total_active === 0) return null;

  const { counts, items } = data;
  const actionable = items.filter(
    (i): i is AutopilotActionQueueItem =>
      i.state === "suggested" || i.state === "accepted"
  ).slice(0, 2);

  async function handleComplete(id: number) {
    setCompleting(id);
    try {
      await api.autopilotCompleteQueueItem(id);
      await mutate();
    } catch {
      // best-effort
    } finally {
      setCompleting(null);
    }
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">🎯 Action Queue</span>
        <span className="text-xs text-zinc-600">{data.total_active} active</span>
      </div>

      {/* State pills */}
      <div className="flex gap-2 flex-wrap mb-4">
        {(["suggested", "accepted", "planned", "snoozed"] as const).map((state) => {
          const n = counts[state];
          if (!n) return null;
          return (
            <div
              key={state}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium",
                STATE_COLORS[state]
              )}
            >
              <span className="font-bold">{n}</span>
              <span className="capitalize">{state}</span>
            </div>
          );
        })}
      </div>

      {/* Actionable items */}
      {actionable.map((item) => (
        <div
          key={item.id}
          className="flex items-start gap-3 py-2.5 border-t border-zinc-800 first:border-t-0"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded capitalize",
                  STATE_COLORS[item.state] ?? "bg-zinc-800 text-zinc-400"
                )}
              >
                {item.state}
              </span>
              {item.item_type !== "task" && (
                <span className="text-xs text-zinc-600">{item.item_type}</span>
              )}
            </div>
            <div className="text-sm text-white truncate">{item.title}</div>
            {item.reason && (
              <div className="text-xs text-zinc-600 truncate mt-0.5">{item.reason}</div>
            )}
          </div>
          {item.state === "accepted" && (
            <button
              onClick={() => handleComplete(item.id)}
              disabled={completing === item.id}
              className="shrink-0 px-2.5 py-1 rounded-lg bg-green-900/50 text-green-400 text-xs font-medium hover:bg-green-900 transition-colors disabled:opacity-40"
            >
              {completing === item.id ? "…" : "Done"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Section Wrapper ────────────────────────────────────────────────────────

export default function AutopilotIntelligenceCards() {
  return (
    <div className="mb-6">
      <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
        <span>🤖</span> Autopilot
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <NextActionCard />
        <DailyPlanCard />
        <ActionQueueCard />
      </div>
    </div>
  );
}
