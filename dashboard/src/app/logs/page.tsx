"use client";

import { useState } from "react";
import Header from "@/components/Header";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useLogs } from "@/hooks/useApi";
import { LOG_TYPE_EMOJI, getMoodEmoji, formatDateTime, truncate, cn } from "@/lib/utils";
import type { Log } from "@/lib/api";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

const LOG_TYPES = [
  { key: "", label: "Alle" },
  { key: "workout", label: "💪 Workout" },
  { key: "water", label: "💧 Wasser" },
  { key: "mood", label: "😊 Mood" },
  { key: "food", label: "🍽️ Essen" },
  { key: "progress", label: "📈 Fortschritt" },
  { key: "note", label: "📝 Notiz" },
  { key: "general", label: "💬 Allgemein" },
];

const DAYS_OPTIONS = [7, 14, 30, 90];

function formatLogData(log: Log): string {
  const d = log.data;
  switch (log.log_type) {
    case "workout":
      return `${d.exercise ?? "?"} · ${d.weight ?? "?"}kg × ${d.reps ?? "?"} × ${d.sets ?? "?"} Sätze`;
    case "water":
      return `${d.amount ?? "?"}L`;
    case "mood":
      return `${getMoodEmoji(Number(d.score) || 0)} ${d.score}/10${d.note ? ` · "${d.note}"` : ""}`;
    case "food":
      return `${d.meal ?? d.food ?? "?"} ${d.calories ? `· ${d.calories} kcal` : ""}`;
    case "progress":
      return d.description ?? d.value ?? JSON.stringify(d);
    default:
      return d.text ?? d.value ?? d.description ?? JSON.stringify(d);
  }
}

function LogItem({ log }: { log: Log }) {
  const emoji = LOG_TYPE_EMOJI[log.log_type] ?? LOG_TYPE_EMOJI.default;
  return (
    <div className="flex items-start gap-3 py-3 border-b border-zinc-800 last:border-0">
      <div className="text-xl shrink-0 mt-0.5">{emoji}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-white text-sm font-medium">{formatLogData(log)}</span>
          <Badge variant="outline">{log.log_type}</Badge>
        </div>
        {log.raw_input && (
          <p className="text-zinc-500 text-xs mt-0.5 italic">
            &ldquo;{truncate(log.raw_input, 100)}&rdquo;
          </p>
        )}
        <div className="text-zinc-500 text-xs mt-0.5">{formatDateTime(log.logged_at)}</div>
      </div>
    </div>
  );
}

function MoodChart({ logs }: { logs: Log[] }) {
  const moodLogs = logs
    .filter((l) => l.log_type === "mood")
    .map((l) => ({
      date: format(parseISO(l.logged_at), "dd. MMM", { locale: de }),
      score: Number(l.data.score) || 0,
    }))
    .reverse();

  if (moodLogs.length < 2) return null;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <h3 className="text-white font-semibold mb-4">😊 Mood-Verlauf</h3>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={moodLogs}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis domain={[0, 10]} tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
            labelStyle={{ color: "#a1a1aa" }}
            itemStyle={{ color: "#3b82f6" }}
          />
          <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={{ fill: "#3b82f6", r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function WorkoutChart({ logs }: { logs: Log[] }) {
  const workoutLogs = logs.filter((l) => l.log_type === "workout");
  if (workoutLogs.length === 0) return null;

  // Group by day
  const byDay: Record<string, number> = {};
  workoutLogs.forEach((l) => {
    const d = format(parseISO(l.logged_at), "dd. MMM", { locale: de });
    byDay[d] = (byDay[d] ?? 0) + 1;
  });

  const data = Object.entries(byDay)
    .map(([date, count]) => ({ date, count }))
    .slice(-14);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <h3 className="text-white font-semibold mb-4">💪 Workouts pro Tag</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
            labelStyle={{ color: "#a1a1aa" }}
            itemStyle={{ color: "#22c55e" }}
          />
          <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} name="Workouts" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function WaterChart({ logs }: { logs: Log[] }) {
  const waterLogs = logs.filter((l) => l.log_type === "water");
  if (waterLogs.length === 0) return null;

  // Sum by day
  const byDay: Record<string, number> = {};
  waterLogs.forEach((l) => {
    const d = format(parseISO(l.logged_at), "dd. MMM", { locale: de });
    byDay[d] = (byDay[d] ?? 0) + Number(l.data.amount ?? 0);
  });

  const data = Object.entries(byDay)
    .map(([date, total]) => ({ date, total: Math.round(total * 10) / 10 }))
    .slice(-14);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <h3 className="text-white font-semibold mb-4">💧 Wasser pro Tag (Liter)</h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
            labelStyle={{ color: "#a1a1aa" }}
            itemStyle={{ color: "#3b82f6" }}
          />
          <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Liter" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function LogsPage() {
  const [logType, setLogType] = useState<string>("");
  const [days, setDays] = useState(30);
  const { data, error, isLoading } = useLogs(logType || undefined, days);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const logs = data?.logs ?? [];

  const counts: Record<string, number> = {};
  (data?.logs ?? []).forEach((l) => {
    counts[l.log_type] = (counts[l.log_type] ?? 0) + 1;
  });

  // For charts we always want all logs of the period
  const allLogs = data?.logs ?? [];

  return (
    <div>
      <Header
        title="📊 Logs"
        subtitle={`${logs.length} Einträge · letzte ${days} Tage`}
      />

      {/* Charts (only when viewing all or specific types) */}
      {(!logType || logType === "mood") && <MoodChart logs={allLogs} />}
      {(!logType || logType === "workout") && <WorkoutChart logs={allLogs} />}
      {(!logType || logType === "water") && <WaterChart logs={allLogs} />}

      {/* Filters */}
      <div className="flex flex-col gap-3 mb-6">
        {/* Type Filter */}
        <div className="flex gap-2 flex-wrap">
          {LOG_TYPES.map((lt) => (
            <button
              key={lt.key}
              onClick={() => setLogType(lt.key)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm transition-colors",
                logType === lt.key
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:text-white"
              )}
            >
              {lt.label}
              {lt.key && counts[lt.key] ? ` (${counts[lt.key]})` : ""}
            </button>
          ))}
        </div>

        {/* Days */}
        <div className="flex gap-2">
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-3 py-1 rounded text-xs transition-colors",
                days === d
                  ? "bg-zinc-600 text-white"
                  : "bg-zinc-800 text-zinc-500 hover:text-white"
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Log List */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-2">
        {logs.length === 0 ? (
          <EmptyState emoji="📊" message="Keine Logs gefunden" />
        ) : (
          <>
            {logs.map((log) => (
              <LogItem key={log.id} log={log} />
            ))}
            <div className="py-2 text-xs text-zinc-600 text-center">{logs.length} Einträge</div>
          </>
        )}
      </div>
    </div>
  );
}
