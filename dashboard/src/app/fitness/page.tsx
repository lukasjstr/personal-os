"use client";

import { useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import {
  useFitnessSummary,
  useFitnessExercises,
  useFitnessPRs,
  useFitnessSplits,
  useFitnessProgression,
} from "@/hooks/useApi";
import { formatDate, cn } from "@/lib/utils";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import type { FitnessExerciseEntry, FitnessSplit } from "@/lib/api";

const INTENSITY_BG = [
  "bg-zinc-800",
  "bg-blue-900/60",
  "bg-blue-700/60",
  "bg-blue-500/70",
  "bg-blue-400/90",
];

const DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

function getIntensity(hasWorkout: boolean): number {
  return hasWorkout ? 3 : 0;
}

function WorkoutCalendar({ workoutDays }: { workoutDays: string[] }) {
  const workoutSet = new Set(workoutDays);
  const today = new Date();

  const weeks: { days: { date: string; hasWorkout: boolean; isToday: boolean; isFuture: boolean }[] }[] = [];

  const endDate = new Date(today);
  endDate.setDate(endDate.getDate() - endDate.getDay() + 7);

  for (let w = 9; w >= 0; w--) {
    const week = { days: [] as { date: string; hasWorkout: boolean; isToday: boolean; isFuture: boolean }[] };
    for (let d = 1; d <= 7; d++) {
      const date = new Date(endDate);
      date.setDate(date.getDate() - w * 7 - (7 - d));
      const dateStr = date.toISOString().slice(0, 10);
      const isToday = dateStr === today.toISOString().slice(0, 10);
      const isFuture = date > today;
      week.days.push({ date: dateStr, hasWorkout: workoutSet.has(dateStr), isToday, isFuture });
    }
    weeks.push(week);
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <h3 className="text-white font-semibold mb-4">📅 Workout-Kalender (10 Wochen)</h3>
      <div className="overflow-x-auto">
        <div className="flex gap-1 min-w-max">
          <div className="flex flex-col gap-1 mr-1">
            {DAYS_DE.map((d) => (
              <div key={d} className="text-zinc-600 text-xs h-5 flex items-center">{d}</div>
            ))}
          </div>
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-1">
              {week.days.map((day) => (
                <div
                  key={day.date}
                  className={cn(
                    "w-5 h-5 rounded-sm",
                    day.isFuture ? "bg-zinc-900 border border-zinc-800/30" : INTENSITY_BG[getIntensity(day.hasWorkout)],
                    day.isToday && "ring-2 ring-blue-500 ring-offset-1 ring-offset-zinc-900"
                  )}
                  title={`${day.date}${day.hasWorkout ? " 💪" : ""}`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SessionCard({ session }: { session: { date: string; exercises: FitnessExerciseEntry[] } }) {
  const uniqueExercises = Array.from(new Set(session.exercises.map((e) => e.exercise)));

  return (
    <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
      <div className="text-white font-medium text-sm mb-2">
        📅 {formatDate(session.date + "T00:00:00")}
      </div>
      <div className="space-y-1.5">
        {uniqueExercises.map((ex) => {
          const sets = session.exercises.filter((e) => e.exercise === ex);
          const maxWeight = Math.max(...sets.map((e) => Number(e.weight ?? 0)));
          const totalSets = sets.length;

          return (
            <div key={ex} className="flex items-center gap-3">
              <span className="text-green-400 text-sm font-medium flex-1 min-w-0 truncate">{ex}</span>
              <div className="flex gap-1.5 shrink-0">
                {maxWeight > 0 && (
                  <span className="text-xs bg-zinc-700 text-zinc-300 px-1.5 py-0.5 rounded">
                    {maxWeight}kg
                  </span>
                )}
                {totalSets > 0 && (
                  <span className="text-xs bg-zinc-700 text-zinc-300 px-1.5 py-0.5 rounded">
                    {totalSets} sets
                  </span>
                )}
                {sets[0]?.duration_min && (
                  <span className="text-xs bg-zinc-700 text-zinc-300 px-1.5 py-0.5 rounded">
                    {sets[0].duration_min} min
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function NextWorkoutBanner({ split }: { split: FitnessSplit }) {
  const exList = (split.exercises || []).slice(0, 5);
  const dayLabel = split.day_of_week !== null ? ` (${["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][split.day_of_week]})` : "";

  return (
    <div className="bg-gradient-to-r from-blue-600/20 to-blue-500/10 border border-blue-500/40 rounded-xl p-5 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-blue-400 text-lg">💪</span>
        <span className="text-white font-bold text-lg">Nächstes Workout: {split.name}{dayLabel}</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {exList.map((ex) => (
          <div key={ex.name} className="flex items-center gap-2 bg-zinc-900/50 rounded-lg px-3 py-2">
            <span className="text-zinc-400 text-xs">☐</span>
            <span className="text-white text-sm flex-1 min-w-0 truncate">{ex.name}</span>
            <div className="flex gap-1 shrink-0">
              {ex.sets && ex.reps && (
                <span className="text-xs text-blue-400">{ex.sets}×{ex.reps}</span>
              )}
              {ex.target_weight && (
                <span className="text-xs text-zinc-500">@ {ex.target_weight}kg</span>
              )}
            </div>
          </div>
        ))}
        {split.exercises.length > 5 && (
          <div className="flex items-center justify-center text-zinc-500 text-xs">
            +{split.exercises.length - 5} weitere Übungen
          </div>
        )}
      </div>
    </div>
  );
}

function SplitCard({ split }: { split: FitnessSplit }) {
  const dayLabel = split.day_of_week !== null
    ? ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][split.day_of_week]
    : null;

  return (
    <div className={cn(
      "bg-zinc-900 border rounded-xl p-4",
      split.is_next ? "border-blue-500/50" : "border-zinc-800"
    )}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            {split.order_in_rotation && (
              <span className="text-xs bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded font-mono">
                #{split.order_in_rotation}
              </span>
            )}
            <h4 className="text-white font-semibold">{split.name}</h4>
            {split.is_next && (
              <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">
                Nächstes
              </span>
            )}
          </div>
          {dayLabel && (
            <div className="text-zinc-500 text-xs mt-0.5">{dayLabel}</div>
          )}
        </div>
        <div className="text-right shrink-0 ml-3">
          <div className="text-white text-sm font-medium">{split.workout_count}×</div>
          {split.last_used && (
            <div className="text-zinc-600 text-xs">{formatDate(split.last_used + "T00:00:00")}</div>
          )}
        </div>
      </div>
      <div className="space-y-1">
        {(split.exercises || []).map((ex) => (
          <div key={ex.name} className="flex items-center gap-2 text-sm">
            <span className="text-zinc-600 text-xs w-3">·</span>
            <span className="text-zinc-300 flex-1 min-w-0 truncate">{ex.name}</span>
            {ex.sets && ex.reps && (
              <span className="text-xs text-zinc-500 shrink-0">{ex.sets}×{ex.reps}</span>
            )}
            {ex.target_weight && (
              <span className="text-xs text-zinc-600 shrink-0">{ex.target_weight}kg</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ProgressionChart({ exercises }: { exercises: { name: string }[] }) {
  const [selected, setSelected] = useState<string>(exercises[0]?.name ?? "");
  const { data: prog } = useFitnessProgression(selected || undefined);

  const chartData = (prog?.data_points ?? []).map((p) => ({
    date: p.date.slice(5), // MM-DD
    weight: p.weight,
    label: `${p.date}: ${p.weight}kg${p.reps ? ` ×${p.reps}` : ""}`,
  }));

  const maxWeight = chartData.length > 0 ? Math.max(...chartData.map((d) => d.weight)) : 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold">📈 Progression</h3>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="bg-zinc-800 text-zinc-300 text-sm border border-zinc-700 rounded-lg px-3 py-1.5 focus:outline-none focus:border-blue-500"
        >
          {exercises.map((ex) => (
            <option key={ex.name} value={ex.name}>{ex.name}</option>
          ))}
        </select>
      </div>

      {chartData.length < 2 ? (
        <div className="text-zinc-600 text-sm text-center py-8">
          Nicht genug Daten für {selected || "diese Übung"}
        </div>
      ) : (
        <>
          <div className="text-zinc-400 text-xs mb-3">
            {chartData.length} Einheiten · Max: <span className="text-yellow-400 font-bold">{maxWeight}kg</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} />
              <YAxis tick={{ fill: "#71717a", fontSize: 11 }} domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
                labelStyle={{ color: "#a1a1aa" }}
                itemStyle={{ color: "#3b82f6" }}
                formatter={(val: number) => [`${val}kg`, "Gewicht"]}
              />
              <ReferenceLine y={maxWeight} stroke="#eab308" strokeDasharray="4 4" strokeOpacity={0.5} />
              <Line
                type="monotone"
                dataKey="weight"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: "#3b82f6", r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}

export default function FitnessPage() {
  const { data: summary, error: summaryError, isLoading } = useFitnessSummary();
  const { data: exercisesData } = useFitnessExercises();
  const { data: prsData } = useFitnessPRs();
  const { data: splitsData } = useFitnessSplits();

  if (isLoading) return <LoadingSpinner />;
  if (summaryError) return <ErrorState message={summaryError.message} />;
  if (!summary) return <LoadingSpinner />;

  const exercises = exercisesData?.exercises ?? [];
  const prs = prsData?.prs ?? [];
  const splits = splitsData?.splits ?? [];
  const volumeData = summary?.volume_by_week ?? [];
  const lastSessions = summary?.last_sessions ?? [];
  const workoutDays = summary?.workout_days ?? [];

  const nextSplit = splits.find((s) => s.is_next);

  const chartData = volumeData.map((v) => ({
    week: v.week.replace(/\d{4}-W/, "KW"),
    volume: v.volume,
  }));

  const isEmpty = exercises.length === 0 && prs.length === 0 && lastSessions.length === 0 && splits.length === 0;

  return (
    <div>
      <Header
        title="💪 Fitness"
        subtitle={`${summary?.total_workout_days ?? 0} Trainingstage · ${exercises.length} Übungen · ${splits.length} Splits · ${prs.length} PRs`}
      />

      {/* Next workout recommendation */}
      {nextSplit && <NextWorkoutBanner split={nextSplit} />}

      {/* Workout Calendar Heatmap */}
      {workoutDays.length > 0 && <WorkoutCalendar workoutDays={workoutDays} />}

      {/* Volume Trend Chart */}
      {chartData.length > 1 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <h3 className="text-white font-semibold mb-4">📊 Trainingsvolumen pro Woche (kg)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="week" tick={{ fill: "#71717a", fontSize: 11 }} />
              <YAxis tick={{ fill: "#71717a", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
                labelStyle={{ color: "#a1a1aa" }}
                itemStyle={{ color: "#22c55e" }}
              />
              <Bar dataKey="volume" fill="#22c55e" radius={[4, 4, 0, 0]} name="Volumen (kg)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Splits Overview */}
      {splits.length > 0 && (
        <div className="mb-6">
          <h3 className="text-white font-semibold mb-4">🏋️ Split-Rotation</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {splits.map((split) => (
              <SplitCard key={split.id} split={split} />
            ))}
          </div>
        </div>
      )}

      {/* Progression Chart */}
      {exercises.length > 0 && <ProgressionChart exercises={exercises} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* PR Board */}
        {prs.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-white font-semibold mb-4">🏆 Personal Records</h3>
            <div className="space-y-2">
              {prs.slice(0, 10).map((pr, i) => (
                <div key={pr.exercise} className="flex items-center gap-3 py-2 border-b border-zinc-800/60 last:border-0">
                  <span className="text-zinc-500 text-xs w-5 text-center shrink-0">
                    {i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}.`}
                  </span>
                  <span className="text-white text-sm flex-1 min-w-0 truncate">{pr.exercise}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-yellow-400 font-bold text-sm">{pr.weight}kg</span>
                    {pr.reps && (
                      <span className="text-zinc-500 text-xs">× {pr.reps}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Exercise Library */}
        {exercises.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-white font-semibold mb-4">📚 Übungs-Library</h3>
            <div className="space-y-2">
              {exercises.slice(0, 10).map((ex) => (
                <div key={ex.name} className="flex items-center gap-3 py-2 border-b border-zinc-800/60 last:border-0">
                  <div className="flex-1 min-w-0">
                    <div className="text-white text-sm truncate">{ex.name}</div>
                    <div className="text-zinc-500 text-xs mt-0.5">
                      {ex.count}× trainiert
                      {ex.max_weight > 0 && ` · max ${ex.max_weight}kg`}
                    </div>
                  </div>
                  <div className="text-xs text-zinc-600 shrink-0">
                    {formatDate(ex.last_done)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Last Sessions */}
      {lastSessions.length > 0 && (
        <div>
          <h3 className="text-white font-semibold mb-4">🗓 Letzte Sessions</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {lastSessions.map((session) => (
              <SessionCard key={session.date} session={session} />
            ))}
          </div>
        </div>
      )}

      {isEmpty && (
        <EmptyState emoji="💪" message="Noch keine Workouts geloggt — fang an zu trainieren!" />
      )}
    </div>
  );
}
