"use client";

import { useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import CircularProgress from "@/components/CircularProgress";
import { useLogs } from "@/hooks/useApi";
import { getMoodEmoji, formatDateTime, cn } from "@/lib/utils";
import type { Log } from "@/lib/api";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { format, parseISO, isSameDay } from "date-fns";
import { de } from "date-fns/locale";

const LOG_TYPES = [
  { key: "", label: "Alle", color: "" },
  { key: "workout", label: "💪 Workout", color: "bg-green-900/60 text-green-400 border-green-800" },
  { key: "water", label: "💧 Wasser", color: "bg-blue-900/60 text-blue-400 border-blue-800" },
  { key: "mood", label: "😊 Mood", color: "bg-yellow-900/60 text-yellow-400 border-yellow-800" },
  { key: "food", label: "🍽️ Essen", color: "bg-orange-900/60 text-orange-400 border-orange-800" },
  { key: "gratitude", label: "🙏 Dankbarkeit", color: "bg-pink-900/60 text-pink-400 border-pink-800" },
  { key: "progress", label: "📈 Fortschritt", color: "bg-purple-900/60 text-purple-400 border-purple-800" },
  { key: "note", label: "📝 Notiz", color: "bg-zinc-800 text-zinc-400 border-zinc-700" },
  { key: "general", label: "💬 Allgemein", color: "bg-zinc-800 text-zinc-400 border-zinc-700" },
];

const DAYS_OPTIONS = [7, 14, 30, 90];

function WorkoutLogCard({ log }: { log: Log }) {
  const d = log.data;
  const exercise = String(d.exercise ?? "Training");
  const chips: string[] = [];
  if (d.weight != null) chips.push(`${d.weight}kg`);
  if (d.reps != null) chips.push(`${d.reps} reps`);
  if (d.sets != null) chips.push(`${d.sets} sets`);
  if (d.duration_min != null) chips.push(`${d.duration_min} min`);

  return (
    <div className="border-l-2 border-l-green-500 bg-green-500/5 rounded-r-lg px-4 py-3 mb-2 last:mb-0">
      <div className="flex items-start gap-3">
        <span className="text-lg shrink-0 mt-0.5">💪</span>
        <div className="flex-1 min-w-0">
          <div className="text-white font-semibold text-sm">{exercise}</div>
          {chips.length > 0 && (
            <div className="flex gap-1.5 mt-1.5 flex-wrap">
              {chips.map((chip, i) => (
                <span key={i} className="bg-green-900/50 text-green-300 text-xs px-2 py-0.5 rounded-full border border-green-800/50">
                  {chip}
                </span>
              ))}
            </div>
          )}
          {d.note && <p className="text-zinc-500 text-xs mt-1 italic">{String(d.note)}</p>}
          <div className="text-zinc-500 text-xs mt-1">{formatDateTime(log.logged_at)}</div>
        </div>
      </div>
    </div>
  );
}

function WaterLogCard({ log, allLogs }: { log: Log; allLogs: Log[] }) {
  const d = log.data;
  const amount = Number(d.amount ?? 0);
  const dayTotal = allLogs
    .filter((l) => l.log_type === "water" && isSameDay(parseISO(l.logged_at), parseISO(log.logged_at)))
    .reduce((sum, l) => sum + Number(l.data.amount ?? 0), 0);

  return (
    <div className="border-l-2 border-l-blue-400 bg-blue-400/5 rounded-r-lg px-4 py-3 mb-2 last:mb-0">
      <div className="flex items-center gap-4">
        <CircularProgress
          value={Math.min(100, (dayTotal / 3) * 100)}
          size={52}
          strokeWidth={5}
          color="#3b82f6"
          label={`${Math.round(dayTotal * 10) / 10}L`}
          sublabel="Heute"
        />
        <div className="flex-1 min-w-0">
          <div className="text-white font-semibold text-sm">+{amount}L Wasser</div>
          <div className="text-zinc-500 text-xs mt-0.5">
            {Math.round(dayTotal * 10) / 10}L / 3L heute · {Math.round((dayTotal / 3) * 100)}%
          </div>
          <div className="text-zinc-500 text-xs mt-1">{formatDateTime(log.logged_at)}</div>
        </div>
      </div>
    </div>
  );
}

function MoodLogCard({ log }: { log: Log }) {
  const score = Number(log.data.score ?? 0);
  const emoji = getMoodEmoji(score);
  const scoreColor = score >= 8 ? "text-green-400" : score >= 5 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="border-l-2 border-l-yellow-400 bg-yellow-400/5 rounded-r-lg px-4 py-3 mb-2 last:mb-0">
      <div className="flex items-center gap-4">
        <span className="text-4xl shrink-0">{emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5">
            <span className={cn("text-2xl font-bold", scoreColor)}>{score}</span>
            <span className="text-zinc-500 text-sm">/10</span>
          </div>
          {log.data.notes && (
            <p className="text-zinc-400 text-sm mt-0.5 italic">&ldquo;{String(log.data.notes)}&rdquo;</p>
          )}
          <div className="text-zinc-500 text-xs mt-1">{formatDateTime(log.logged_at)}</div>
        </div>
      </div>
    </div>
  );
}

function GratitudeLogCard({ log }: { log: Log }) {
  const note = String(log.data.note ?? log.raw_input ?? "");
  return (
    <div className="border-l-2 border-l-pink-400 bg-pink-400/5 rounded-r-lg px-4 py-3 mb-2 last:mb-0">
      <div className="flex items-start gap-2">
        <span className="text-pink-400 text-2xl shrink-0 leading-none mt-0.5">&ldquo;</span>
        <div className="flex-1 min-w-0">
          <p className="text-pink-200 text-sm leading-relaxed italic">{note}</p>
          <div className="text-zinc-500 text-xs mt-1.5">{formatDateTime(log.logged_at)}</div>
        </div>
        <span className="text-pink-400 text-2xl shrink-0 leading-none self-end">&rdquo;</span>
      </div>
    </div>
  );
}

const LOG_TYPE_STYLE: Record<string, { border: string; bg: string }> = {
  food: { border: "border-l-orange-400", bg: "bg-orange-400/5" },
  progress: { border: "border-l-purple-400", bg: "bg-purple-400/5" },
  note: { border: "border-l-zinc-500", bg: "" },
  general: { border: "border-l-zinc-500", bg: "" },
};

function DefaultLogCard({ log }: { log: Log }) {
  const d = log.data;
  const style = LOG_TYPE_STYLE[log.log_type] ?? { border: "border-l-zinc-700", bg: "" };
  let title = "";
  switch (log.log_type) {
    case "food":
      title = `${d.description ?? d.meal ?? d.food ?? "?"}${d.calories ? ` · ${d.calories} kcal` : ""}`;
      break;
    case "progress":
      title = `Fortschritt: +${d.value ?? "?"}${d.description ? ` · ${String(d.description)}` : ""}`;
      break;
    default:
      title = String(d.text ?? d.content ?? log.raw_input ?? log.log_type);
  }
  return (
    <div className={cn("border-l-2 rounded-r-lg px-4 py-3 mb-2 last:mb-0", style.border, style.bg || "bg-zinc-800/30")}>
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-white text-sm font-medium">{title}</span>
            <span className="text-zinc-600 text-xs bg-zinc-800 px-1.5 py-0.5 rounded">{log.log_type}</span>
          </div>
          {log.raw_input && log.log_type !== "food" && (
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

function LogCard({ log, allLogs }: { log: Log; allLogs: Log[] }) {
  switch (log.log_type) {
    case "workout": return <WorkoutLogCard log={log} />;
    case "water": return <WaterLogCard log={log} allLogs={allLogs} />;
    case "mood": return <MoodLogCard log={log} />;
    case "gratitude": return <GratitudeLogCard log={log} />;
    default: return <DefaultLogCard log={log} />;
  }
}

function MoodChart({ logs }: { logs: Log[] }) {
  const moodLogs = logs
    .filter((l) => l.log_type === "mood")
    .map((l) => ({ date: format(parseISO(l.logged_at), "dd. MMM", { locale: de }), score: Number(l.data.score) || 0 }))
    .reverse();
  if (moodLogs.length < 2) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
      <h3 className="text-white font-semibold mb-4">😊 Mood-Verlauf</h3>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={moodLogs}>
          <defs>
            <linearGradient id="moodGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis domain={[0, 10]} tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} labelStyle={{ color: "#a1a1aa" }} itemStyle={{ color: "#22c55e" }} />
          <Area type="monotone" dataKey="score" stroke="#22c55e" strokeWidth={2} fill="url(#moodGrad)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

const EXERCISE_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];

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
  const data = Object.entries(byDay).map(([date, exCounts]) => ({ date, ...exCounts })).slice(-14);
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
      <h3 className="text-white font-semibold mb-4">💪 Workouts pro Tag</h3>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} labelStyle={{ color: "#a1a1aa" }} />
          {exercises.map((ex, i) => (
            <Bar key={ex} dataKey={ex} fill={EXERCISE_COLORS[i % EXERCISE_COLORS.length]} stackId="a" radius={i === exercises.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      {exercises.length > 1 && (
        <div className="flex flex-wrap gap-3 mt-2">
          {exercises.map((ex, i) => (
            <span key={ex} className="text-xs text-zinc-400 flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm inline-block shrink-0" style={{ backgroundColor: EXERCISE_COLORS[i % EXERCISE_COLORS.length] }} />
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
  const data = Object.entries(byDay).map(([date, total]) => ({ date, total: Math.round(total * 10) / 10 })).slice(-14);
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
      <h3 className="text-white font-semibold mb-4">💧 Wasser pro Tag (Liter)</h3>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} labelStyle={{ color: "#a1a1aa" }} itemStyle={{ color: "#3b82f6" }} />
          <ReferenceLine y={3} stroke="#3b82f6" strokeDasharray="4 4" label={{ value: "3L Ziel", fill: "#3b82f6", fontSize: 10, position: "right" }} />
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
  const allLogs = data?.logs ?? [];
  const counts: Record<string, number> = {};
  allLogs.forEach((l) => { counts[l.log_type] = (counts[l.log_type] ?? 0) + 1; });

  return (
    <div>
      <Header title="📊 Logs" subtitle={`${logs.length} Einträge · letzte ${days} Tage`} />

      {(!logType || logType === "mood") && <MoodChart logs={allLogs} />}
      {(!logType || logType === "workout") && <WorkoutChart logs={allLogs} />}
      {(!logType || logType === "water") && <WaterChart logs={allLogs} />}

      {/* Filter Pills */}
      <div className="flex flex-col gap-3 mb-6">
        <div className="flex gap-2 flex-wrap">
          {LOG_TYPES.map((lt) => (
            <button
              key={lt.key}
              onClick={() => setLogType(lt.key)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm border transition-colors",
                logType === lt.key
                  ? lt.color
                    ? `${lt.color} border-current`
                    : "bg-blue-600 text-white border-blue-600"
                  : "bg-zinc-900 text-zinc-400 border-zinc-700 hover:text-white hover:border-zinc-600"
              )}
            >
              {lt.label}
              {lt.key && counts[lt.key] ? <span className="ml-1.5 opacity-70">({counts[lt.key]})</span> : null}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {DAYS_OPTIONS.map((d) => (
            <button key={d} onClick={() => setDays(d)} className={cn("px-3 py-1 rounded text-xs transition-colors", days === d ? "bg-zinc-600 text-white" : "bg-zinc-800 text-zinc-500 hover:text-white")}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        {logs.length === 0 ? (
          <EmptyState emoji="📊" message="Keine Logs gefunden" />
        ) : (
          <>
            {logs.map((log) => <LogCard key={log.id} log={log} allLogs={allLogs} />)}
            <div className="pt-3 text-xs text-zinc-600 text-center">{logs.length} Einträge</div>
          </>
        )}
      </div>
    </div>
  );
}
