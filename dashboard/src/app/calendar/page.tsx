"use client";

import { useState } from "react";
import Header from "@/components/Header";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useCalendar } from "@/hooks/useApi";
import { EVENT_TYPE_EMOJI, formatDate, formatTime, cn } from "@/lib/utils";
import {
  format,
  parseISO,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  addMonths,
  subMonths,
  isToday,
  startOfWeek,
  endOfWeek,
} from "date-fns";
import { de } from "date-fns/locale";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { CalendarEvent } from "@/lib/api";

const EVENT_TYPE_BADGE: Record<string, "blue" | "green" | "yellow" | "red" | "purple" | "outline"> = {
  training: "green",
  meeting: "blue",
  routine: "purple",
  deadline: "red",
  reminder: "yellow",
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  training: "Training",
  meeting: "Meeting",
  routine: "Routine",
  deadline: "Deadline",
  reminder: "Reminder",
};

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

function MonthCalendar({
  events,
  currentMonth,
}: {
  events: CalendarEvent[];
  currentMonth: Date;
}) {
  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const eventsByDay = new Map<string, CalendarEvent[]>();
  events.forEach((e) => {
    const d = format(parseISO(e.start_time), "yyyy-MM-dd");
    if (!eventsByDay.has(d)) eventsByDay.set(d, []);
    eventsByDay.get(d)!.push(e);
  });

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      {/* Day headers */}
      <div className="grid grid-cols-7 border-b border-zinc-800">
        {DAY_NAMES.map((d) => (
          <div key={d} className="text-center text-xs text-zinc-500 py-2 font-medium">
            {d}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7">
        {days.map((day) => {
          const key = format(day, "yyyy-MM-dd");
          const dayEvents = eventsByDay.get(key) ?? [];
          const inMonth = isSameMonth(day, currentMonth);
          const today = isToday(day);

          return (
            <div
              key={key}
              className={cn(
                "min-h-[80px] p-1.5 border-r border-b border-zinc-800/50 last:border-r-0",
                !inMonth && "opacity-30"
              )}
            >
              <div
                className={cn(
                  "w-6 h-6 flex items-center justify-center rounded-full text-xs mb-1 mx-auto",
                  today ? "bg-blue-600 text-white font-bold" : "text-zinc-400"
                )}
              >
                {format(day, "d")}
              </div>
              <div className="space-y-0.5">
                {dayEvents.slice(0, 3).map((e) => (
                  <div
                    key={e.id}
                    className={cn(
                      "text-xs px-1 py-0.5 rounded truncate",
                      e.event_type === "training" ? "bg-green-900 text-green-300" :
                      e.event_type === "meeting" ? "bg-blue-900 text-blue-300" :
                      e.event_type === "deadline" ? "bg-red-900 text-red-300" :
                      e.event_type === "routine" ? "bg-purple-900 text-purple-300" :
                      "bg-zinc-700 text-zinc-300"
                    )}
                    title={e.title}
                  >
                    {EVENT_TYPE_EMOJI[e.event_type] ?? "📌"} {e.title}
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className="text-xs text-zinc-500 px-1">+{dayEvents.length - 3}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const { data, error, isLoading } = useCalendar(90);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const events = data?.events ?? [];

  // Upcoming events (next 30 days)
  const now = new Date();
  const upcoming = events
    .filter((e) => parseISO(e.start_time) >= now)
    .slice(0, 10);

  // Filter events for current month view
  const monthEvents = events.filter((e) =>
    isSameMonth(parseISO(e.start_time), currentMonth)
  );

  return (
    <div>
      <Header
        title="📅 Kalender"
        subtitle={`${events.length} Events · ${upcoming.length} bevorstehend`}
      />

      {/* Month Navigation */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <h2 className="text-white font-semibold">
          {format(currentMonth, "MMMM yyyy", { locale: de })}
        </h2>
        <button
          onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Month view */}
      <div className="mb-6">
        <MonthCalendar events={monthEvents} currentMonth={currentMonth} />
      </div>

      {/* Upcoming Events List */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
          <span>⏰</span> Bevorstehende Events
        </h2>
        {upcoming.length === 0 ? (
          <EmptyState emoji="📅" message="Keine bevorstehenden Events" />
        ) : (
          <div className="space-y-3">
            {upcoming.map((e) => (
              <div
                key={e.id}
                className="flex items-start gap-4 py-3 border-b border-zinc-800 last:border-0"
              >
                <span className="text-2xl mt-0.5">{EVENT_TYPE_EMOJI[e.event_type] ?? "📌"}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white font-medium">{e.title}</span>
                    <Badge variant={EVENT_TYPE_BADGE[e.event_type] ?? "outline"}>
                      {EVENT_TYPE_LABEL[e.event_type] ?? e.event_type}
                    </Badge>
                  </div>
                  <div className="text-zinc-500 text-xs mt-1">
                    📅 {formatDate(e.start_time)}
                    {!e.all_day && ` · ⏰ ${formatTime(e.start_time)}`}
                    {e.end_time && !e.all_day && ` – ${formatTime(e.end_time)}`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
