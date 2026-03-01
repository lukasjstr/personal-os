"use client";

import { format, parseISO, startOfWeek, addDays, isToday } from "date-fns";
import { de } from "date-fns/locale";
import { cn } from "@/lib/utils";
import type { Log } from "@/lib/api";

interface Props {
  logs: Log[];
}

const INTENSITY_BG = [
  "bg-zinc-800",
  "bg-blue-900/70",
  "bg-blue-700/70",
  "bg-blue-500/70",
  "bg-blue-400/90",
];

function getIntensity(count: number): number {
  if (count === 0) return 0;
  if (count <= 2) return 1;
  if (count <= 5) return 2;
  if (count <= 10) return 3;
  return 4;
}

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

export default function WeekHeatmap({ logs }: Props) {
  const today = new Date();
  const weekStart = startOfWeek(today, { weekStartsOn: 1 });
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const logsByDay = new Map<string, number>();
  logs.forEach((log) => {
    const dateKey = format(parseISO(log.logged_at), "yyyy-MM-dd");
    logsByDay.set(dateKey, (logsByDay.get(dateKey) ?? 0) + 1);
  });

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
        <span>🗓</span> Diese Woche
      </h2>
      <div className="grid grid-cols-7 gap-2">
        {days.map((day, i) => {
          const dateKey = format(day, "yyyy-MM-dd");
          const count = logsByDay.get(dateKey) ?? 0;
          const intensity = getIntensity(count);
          const todayDay = isToday(day);
          const isFuture = day > today;

          return (
            <div key={dateKey} className="flex flex-col items-center gap-1.5">
              <span className="text-zinc-500 text-xs">{DAY_NAMES[i]}</span>
              <div
                className={cn(
                  "w-full rounded-lg transition-colors",
                  "aspect-square",
                  isFuture
                    ? "bg-zinc-900 border border-zinc-800/50"
                    : INTENSITY_BG[intensity],
                  todayDay && "ring-2 ring-blue-500 ring-offset-1 ring-offset-zinc-900"
                )}
                title={`${format(day, "d. MMM", { locale: de })}: ${count} Aktivitäten`}
              />
              <span
                className={cn(
                  "text-xs",
                  todayDay ? "text-blue-400 font-bold" : "text-zinc-600"
                )}
              >
                {format(day, "d")}
              </span>
            </div>
          );
        })}
      </div>
      <div className="flex items-center justify-end gap-1.5 mt-3">
        <span className="text-zinc-600 text-xs">Weniger</span>
        {INTENSITY_BG.map((bg, i) => (
          <div key={i} className={cn("w-3 h-3 rounded-sm", bg)} />
        ))}
        <span className="text-zinc-600 text-xs">Mehr</span>
      </div>
    </div>
  );
}
