"use client";

import { useState } from "react";
import useSWR from "swr";
import Header from "@/components/Header";
import { api, Log } from "@/lib/api";
import { cn } from "@/lib/utils";

const LOG_TYPE_LABELS: Record<string, string> = {
  morning_checkin: "Morning Check-in",
  evening_review: "Evening Review",
  workout: "Workout",
  water: "Wasser",
  food: "Ernährung",
  mood: "Stimmung",
  progress: "Fortschritt",
  note: "Notiz",
  general: "Allgemein",
  brain_dump: "Brain Dump",
  task_complete: "Task abgeschlossen",
};

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  dashboard: { label: "Dashboard", color: "text-blue-400 bg-blue-950/40 border-blue-900/50" },
  telegram: { label: "Telegram", color: "text-indigo-400 bg-indigo-950/40 border-indigo-900/50" },
  text: { label: "Text", color: "text-zinc-400 bg-zinc-800/60 border-zinc-700/50" },
  image: { label: "Bild", color: "text-purple-400 bg-purple-950/40 border-purple-900/50" },
  voice: { label: "Sprache", color: "text-green-400 bg-green-950/40 border-green-900/50" },
  autopilot: { label: "Autopilot", color: "text-amber-400 bg-amber-950/40 border-amber-900/50" },
};

const DAY_OPTIONS = [7, 14, 30, 90];
const LOG_TYPES = ["", "morning_checkin", "evening_review", "workout", "mood", "progress", "note", "brain_dump"];

function summarizeData(data: Record<string, unknown>): string {
  if (!data || typeof data !== "object") return "";
  const entries = Object.entries(data)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .slice(0, 3)
    .map(([k, v]) => {
      const label = k.replace(/_/g, " ");
      if (Array.isArray(v)) return `${label}: ${(v as unknown[]).join(", ")}`;
      return `${label}: ${String(v).slice(0, 60)}`;
    });
  return entries.join(" · ");
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AuditPage() {
  const [days, setDays] = useState(30);
  const [logType, setLogType] = useState("");

  const { data, error, isLoading } = useSWR(
    `audit-${days}-${logType}`,
    () => api.logs(logType || undefined, days),
    { refreshInterval: 60_000 }
  );

  const logs: Log[] = data?.logs ?? [];

  return (
    <div>
      <Header title="Audit Log" subtitle="Alle Aktionen mit Quelle und Zeitstempel" />

      {/* Filters */}
      <div className="flex gap-3 mb-5 flex-wrap">
        <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-3 py-1 rounded-md text-sm transition-colors",
                days === d
                  ? "bg-zinc-700 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              {d}d
            </button>
          ))}
        </div>
        <select
          value={logType}
          onChange={(e) => setLogType(e.target.value)}
          className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-zinc-600 transition-colors"
        >
          <option value="">Alle Typen</option>
          {LOG_TYPES.filter(Boolean).map((t) => (
            <option key={t} value={t}>
              {LOG_TYPE_LABELS[t] ?? t}
            </option>
          ))}
        </select>
        <span className="ml-auto text-zinc-600 text-sm self-center">
          {isLoading ? "Laden…" : `${logs.length} Einträge`}
        </span>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-4 py-3 mb-4 text-red-400 text-sm">
          Audit-Log konnte nicht geladen werden.
        </div>
      )}

      {!isLoading && logs.length === 0 && !error && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500 text-sm">
          Keine Einträge für den gewählten Zeitraum.
        </div>
      )}

      <div className="space-y-2">
        {logs.map((log) => {
          const src = SOURCE_LABELS[log.source] ?? SOURCE_LABELS["text"];
          const summary = summarizeData(log.data);
          return (
            <div
              key={log.id}
              className="bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 flex items-start gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-white text-sm font-medium">
                    {LOG_TYPE_LABELS[log.log_type] ?? log.log_type}
                  </span>
                  <span
                    className={cn(
                      "text-xs px-1.5 py-0.5 rounded border",
                      src.color
                    )}
                  >
                    {src.label}
                  </span>
                </div>
                {summary && (
                  <p className="text-zinc-500 text-xs mt-1 truncate">{summary}</p>
                )}
                {log.raw_input && (
                  <p className="text-zinc-600 text-xs mt-0.5 truncate italic">
                    &ldquo;{log.raw_input.slice(0, 120)}&rdquo;
                  </p>
                )}
              </div>
              <span className="text-zinc-600 text-xs shrink-0 mt-0.5">
                {formatDate(log.logged_at)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
