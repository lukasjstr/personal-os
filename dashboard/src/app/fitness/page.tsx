"use client";

import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useFitnessSummary, useFitnessExercises, useFitnessPRs } from "@/hooks/useApi";
import { formatDate, cn } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { FitnessExerciseEntry } from "@/lib/api";

const INTENSITY_BG = [
  "bg-zinc-800",
  "bg-blue-900/60",
  "bg-blue-700/60",
  "bg-blue-500/70",
  "bg-blue-400/90",
];

function getIntensity(hasWorkout: boolean): number {
  return hasWorkout ? 3 : 0;
}

function WorkoutCalendar({ workoutDays }: { workoutDays: string[] }) {
  const workoutSet = new Set(workoutDays);
  const today = new Date();

  // Last 10 weeks
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

  const dayLabels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <h3 className="text-white font-semibold mb-4">📅 Workout-Kalender (10 Wochen)</h3>
      <div className="flex gap-1">
        <div className="flex flex-col gap-1 mr-1">
          {dayLabels.map((d) => (
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
  );
}

function SessionCard({ session }: { session: { date: string; exercises: FitnessExerciseEntry[] } }) {
  const uniqueExercises = [...new Set(session.exercises.map((e) => e.exercise))];

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

export default function FitnessPage() {
  const { data: summary, error: summaryError, isLoading } = useFitnessSummary();
  const { data: exercisesData } = useFitnessExercises();
  const { data: prsData } = useFitnessPRs();

  if (isLoading) return <LoadingSpinner />;
  if (summaryError) return <ErrorState message={summaryError.message} />;

  const exercises = exercisesData?.exercises ?? [];
  const prs = prsData?.prs ?? [];
  const volumeData = summary?.volume_by_week ?? [];
  const lastSessions = summary?.last_sessions ?? [];
  const workoutDays = summary?.workout_days ?? [];

  const chartData = volumeData.map((v) => ({
    week: v.week.replace(/\d{4}-W/, "KW"),
    volume: v.volume,
  }));

  return (
    <div>
      <Header
        title="💪 Fitness"
        subtitle={`${summary?.total_workout_days ?? 0} Trainingstage · ${exercises.length} Übungen · ${prs.length} PRs`}
      />

      {/* Workout Calendar Heatmap */}
      {workoutDays.length > 0 && <WorkoutCalendar workoutDays={workoutDays} />}

      {/* Volume Trend Chart */}
      {chartData.length > 1 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <h3 className="text-white font-semibold mb-4">📈 Trainingsvolumen pro Woche (kg)</h3>
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

      {exercises.length === 0 && prs.length === 0 && lastSessions.length === 0 && (
        <EmptyState emoji="💪" message="Noch keine Workouts geloggt — fang an zu trainieren!" />
      )}
    </div>
  );
}
