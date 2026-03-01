"use client";

import { useState } from "react";
import Header from "@/components/Header";
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
  isSameDay,
  startOfWeek,
  endOfWeek,
} from "date-fns";
import { de } from "date-fns/locale";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { CalendarEvent } from "@/lib/api";

const EVENT_TYPE_BADGE: Record<string, string> = {
  training: "bg-green-900/60 text-green-300 border-green-800/60",
  meeting: "bg-blue-900/60 text-blue-300 border-blue-800/60",
  routine: "bg-purple-900/60 text-purple-300 border-purple-800/60",
  deadline: "bg-red-900/60 text-red-300 border-red-800/60",
  reminder: "bg-yellow-900/60 text-yellow-300 border-yellow-800/60",
};

const EVENT_TYPE_DOT: Record<string, string> = {
  training: "bg-green-500",
  meeting: "bg-blue-500",
  routine: "bg-purple-500",
  deadline: "bg-red-500",
  reminder: "bg-yellow-500",
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
  selectedDay,
  onSelectDay,
}: {
  events: CalendarEvent[];
  currentMonth: Date;
  selectedDay: Date | null;
  onSelectDay: (d: Date) => void;
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
      <div className="grid grid-cols-7 border-b border-zinc-800">
        {DAY_NAMES.map((d) => (
          <div key={d} className="text-center text-xs text-zinc-500 py-2.5 font-medium">
            {d}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {days.map((day) => {
          const key = format(day, "yyyy-MM-dd");
          const dayEvents = eventsByDay.get(key) ?? [];
          const inMonth = isSameMonth(day, currentMonth);
          const today = isToday(day);
          const selected = selectedDay && isSameDay(day, selectedDay);

          return (
            <button
              key={key}
              onClick={() => onSelectDay(day)}
              className={cn(
                "min-h-[72px] p-1.5 border-r border-b border-zinc-800/50 last:border-r-0 text-left transition-colors",
                !inMonth && "opacity-30",
                selected && "bg-blue-950/40",
                !selected && "hover:bg-zinc-800/40"
              )}
            >
              <div
                className={cn(
                  "w-6 h-6 flex items-center justify-center rounded-full text-xs mb-1",
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
                      "text-xs px-1 py-0.5 rounded truncate border",
                      EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
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
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const { data, error, isLoading } = useCalendar(90);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const events = data?.events ?? [];
  const now = new Date();
  const upcoming = events.filter((e) => parseISO(e.start_time) >= now).slice(0, 10);
  const monthEvents = events.filter((e) => isSameMonth(parseISO(e.start_time), currentMonth));

  const selectedDayEvents = selectedDay
    ? events.filter((e) => isSameDay(parseISO(e.start_time), selectedDay))
    : [];

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
        <div className="flex items-center gap-3">
          <h2 className="text-white font-semibold">
            {format(currentMonth, "MMMM yyyy", { locale: de })}
          </h2>
          <button
            onClick={() => { setCurrentMonth(new Date()); setSelectedDay(new Date()); }}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            Heute
          </button>
        </div>
        <button
          onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Month Calendar */}
      <div className="mb-4">
        <MonthCalendar
          events={monthEvents}
          currentMonth={currentMonth}
          selectedDay={selectedDay}
          onSelectDay={setSelectedDay}
        />
      </div>

      {/* Selected day details */}
      {selectedDay && selectedDayEvents.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
          <h2 className="text-white font-semibold mb-3">
            {format(selectedDay, "EEEE, d. MMMM", { locale: de })}
          </h2>
          <div className="space-y-2">
            {selectedDayEvents.map((e) => (
              <div key={e.id} className="flex items-start gap-3 py-2 border-b border-zinc-800 last:border-0">
                <span className="text-xl mt-0.5">{EVENT_TYPE_EMOJI[e.event_type] ?? "📌"}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-sm">{e.title}</span>
                    <span className={cn("text-xs px-1.5 py-0.5 rounded border", EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600")}>
                      {EVENT_TYPE_LABEL[e.event_type] ?? e.event_type}
                    </span>
                  </div>
                  {!e.all_day && (
                    <div className="text-zinc-500 text-xs mt-0.5">
                      ⏰ {formatTime(e.start_time)}{e.end_time ? ` – ${formatTime(e.end_time)}` : ""}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upcoming Events */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
          <span>⏰</span> Bevorstehende Events
        </h2>
        {upcoming.length === 0 ? (
          <EmptyState emoji="📅" message="Keine bevorstehenden Events" />
        ) : (
          <div className="space-y-0">
            {upcoming.map((e) => (
              <div key={e.id} className="flex items-start gap-4 py-3 border-b border-zinc-800 last:border-0">
                <div className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", EVENT_TYPE_DOT[e.event_type] ?? "bg-zinc-500")} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white text-sm font-medium">{e.title}</span>
                    <span className={cn("text-xs px-1.5 py-0.5 rounded border", EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600")}>
                      {EVENT_TYPE_LABEL[e.event_type] ?? e.event_type}
                    </span>
                  </div>
                  <div className="text-zinc-500 text-xs mt-0.5">
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
