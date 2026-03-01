"use client";

import { useState } from "react";
import Header from "@/components/Header";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useLogs } from "@/hooks/useApi";
import { LOG_TYPE_EMOJI, getMoodEmoji, formatDateTime, cn } from "@/lib/utils";
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
  { key: "gratitude", label: "🙏 Dankbarkeit" },
  { key: "note", label: "📝 Notiz" },
  { key: "general", label: "💬 Allgemein" },
];

const DAYS_OPTIONS = [7, 14, 30, 90];

const LOG_TYPE_STYLE: Record<string, { border: string; bg: string }> = {
  workout: { border: "border-l-green-500", bg: "bg-green-500/5" },
  water: { border: "border-l-blue-400", bg: "bg-blue-400/5" },
  mood: { border: "border-l-yellow-400", bg: "bg-yellow-400/5" },
  food: { border: "border-l-orange-400", bg: "bg-orange-400/5" },
  progress: { border: "border-l-purple-400", bg: "bg-purple-400/5" },
  gratitude: { border: "border-l-pink-400", bg: "bg-pink-400/5" },
  note: { border: "border-l-zinc-500", bg: "" },
  general: { border: "border-l-zinc-500", bg: "" },
};

function getLogTitle(log: Log): string {
  const d = log.data;
  switch (log.log_type) {
    case "workout": {
      const exercise = String(d.exercise ?? "?");
      let detail = "";
      if (d.duration_min != null) {
        detail = `${d.duration_min} min`;
      } else if (d.weight != null || d.reps != null) {
        detail = `${d.weight ?? "?"}kg × ${d.reps ?? "?"} × ${d.sets ?? "?"} Sätze`;
      }
      const note = d.note ? ` · ${String(d.note)}` : "";
      return `${exercise}${detail ? ` · ${detail}` : ""}${note}`;
    }
    case "water":
      return `${d.amount ?? "?"}L Wasser`;
    case "mood":
      return `Mood ${d.score}/10${d.notes ? ` · "${String(d.notes)}"` : ""}`;
    case "food":
      return `${d.description ?? d.meal ?? d.food ?? "?"}${d.calories ? ` · ${d.calories} kcal` : ""}`;
    case "progress":
      return `Fortschritt: +${d.value ?? "?"}${d.description ? ` · ${String(d.description)}` : ""}`;
    case "gratitude":
      return String(d.note ?? "?");
    default:
      return String(d.text ?? d.content ?? log.raw_input ?? JSON.stringify(d));
  }
}

function LogCard({ log }: { log: Log }) {
  const emoji = log.log_type === "mood"
    ? getMoodEmoji(Number(log.data.score) || 0)
    : (LOG_TYPE_EMOJI[log.log_type] ?? LOG_TYPE_EMOJI.default);
  const style = LOG_TYPE_STYLE[log.log_type] ?? { border: "border-l-zinc-700", bg: "" };

  return (
    <div
      className={cn(
        "border-l-2 rounded-r-lg px-4 py-3 mb-2 last:mb-0",
        style.border,
        style.bg || "bg-zinc-800/30"
      )}
    >
      <div className="flex items-start gap-3">
        <span className="text-lg shrink-0 mt-0.5">{emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-white text-sm font-medium">{getLogTitle(log)}</span>
            <Badge variant="outline">{log.log_type}</Badge>
          </div>
          {log.raw_input && (
            <p className="text-zinc-500 text-xs mt-0.5 italic">
              &ldquo;{log.raw_input.length > 100 ? log.raw_input.slice(0, 100) + "…" : log.raw_input}&rdquo;
            </p>
          )}
          <div className="text-zinc-500 text-xs mt-0.5">{formatDateTime(log.logged_at)}</div>
        </div>
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

const EXERCISE_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4", "#f97316", "#10b981"];

function WorkoutChart({ logs }: { logs: Log[] }) {
  const workoutLogs = logs.filter((l) => l.log_type === "workout");
  if (workoutLogs.length === 0) return null;

  const exercises = [...new Set(workoutLogs.map((l) => String(l.data.exercise ?? "Unbekannt")))];

  const byDay: Record<string, Record<string, number>> = {};
  workoutLogs.forEach((l) => {
    const d = format(parseISO(l.logged_at), "dd. MMM", { locale: de });
    const ex = String(l.data.exercise ?? "Unbekannt");
    if (!byDay[d]) byDay[d] = {};
    byDay[d][ex] = (byDay[d][ex] ?? 0) + 1;
  });

  const data = Object.entries(byDay)
    .map(([date, exCounts]) => ({ date, ...exCounts }))
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
          />
          {exercises.map((ex, i) => (
            <Bar
              key={ex}
              dataKey={ex}
              fill={EXERCISE_COLORS[i % EXERCISE_COLORS.length]}
              stackId="a"
              radius={i === exercises.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
              name={ex}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      {exercises.length > 1 && (
        <div className="flex flex-wrap gap-3 mt-3">
          {exercises.map((ex, i) => (
            <span key={ex} className="text-xs text-zinc-400 flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm inline-block shrink-0"
                style={{ backgroundColor: EXERCISE_COLORS[i % EXERCISE_COLORS.length] }}
              />
              {ex}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function WaterChart({ logs }: { logs: Log[] }) {
  const waterLogs = logs.filter((l) => l.log_type === "water");
  if (waterLogs.length === 0) return null;

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

  const allLogs = data?.logs ?? [];

  return (
    <div>
      <Header
        title="📊 Logs"
        subtitle={`${logs.length} Einträge · letzte ${days} Tage`}
      />

      {/* Charts */}
      {(!logType || logType === "mood") && <MoodChart logs={allLogs} />}
      {(!logType || logType === "workout") && <WorkoutChart logs={allLogs} />}
      {(!logType || logType === "water") && <WaterChart logs={allLogs} />}

      {/* Filters */}
      <div className="flex flex-col gap-3 mb-6">
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
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        {logs.length === 0 ? (
          <EmptyState emoji="📊" message="Keine Logs gefunden" />
        ) : (
          <>
            {logs.map((log) => (
              <LogCard key={log.id} log={log} />
            ))}
            <div className="pt-3 text-xs text-zinc-600 text-center">{logs.length} Einträge</div>
          </>
        )}
      </div>
    </div>
  );
}
