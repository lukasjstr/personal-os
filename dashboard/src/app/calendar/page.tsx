"use client";

import { useState, useCallback } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useCalendar } from "@/hooks/useApi";
import { api } from "@/lib/api";
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
  addWeeks,
  subWeeks,
  addDays,
  subDays,
  isToday,
  isSameDay,
  startOfWeek,
  endOfWeek,
  getHours,
  getMinutes,
  differenceInMinutes,
  setHours,
  setMinutes,
} from "date-fns";
import { de } from "date-fns/locale";
import { ChevronLeft, ChevronRight, X, Save, Clock, Tag, FileText } from "lucide-react";
import type { CalendarEvent } from "@/lib/api";

// ─── Constants ──────────────────────────────────────────────────────────────

const EVENT_TYPE_BADGE: Record<string, string> = {
  training: "bg-green-900/60 text-green-300 border-green-800/60",
  meeting: "bg-blue-900/60 text-blue-300 border-blue-800/60",
  routine: "bg-purple-900/60 text-purple-300 border-purple-800/60",
  deadline: "bg-red-900/60 text-red-300 border-red-800/60",
  reminder: "bg-yellow-900/60 text-yellow-300 border-yellow-800/60",
  errand: "bg-orange-900/60 text-orange-300 border-orange-800/60",
};

const EVENT_TYPE_DOT: Record<string, string> = {
  training: "bg-green-500",
  meeting: "bg-blue-500",
  routine: "bg-purple-500",
  deadline: "bg-red-500",
  reminder: "bg-yellow-500",
  errand: "bg-orange-500",
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  training: "Training",
  meeting: "Meeting",
  routine: "Routine",
  deadline: "Deadline",
  reminder: "Reminder",
  errand: "Errand",
};

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

const DAY_HOURS = Array.from({ length: 17 }, (_, i) => i + 6); // 06:00–22:00
const HOUR_HEIGHT = 60; // px per hour

type ViewMode = "month" | "week" | "day";

// ─── Event Detail Modal ───────────────────────────────────────────────────────

function EventModal({
  event,
  onClose,
  onSaved,
}: {
  event: CalendarEvent;
  onClose: () => void;
  onSaved: (updated: CalendarEvent) => void;
}) {
  const [notes, setNotes] = useState(event.description ?? "");
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await api.addCalendarNotes(event.id, notes);
      onSaved(updated);
      onClose();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }, [event.id, notes, onClose, onSaved]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl w-full max-w-md p-5 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xl">{EVENT_TYPE_EMOJI[event.event_type] ?? "📌"}</span>
              <h2 className="text-white font-semibold text-lg leading-tight">{event.title}</h2>
            </div>
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded border",
                EVENT_TYPE_BADGE[event.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
              )}
            >
              {EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors shrink-0 ml-2"
          >
            <X size={16} />
          </button>
        </div>

        {/* Time */}
        <div className="flex items-center gap-2 text-zinc-400 text-sm mb-3">
          <Clock size={14} />
          <span>
            {event.all_day
              ? `${formatDate(event.start_time)} · Ganztägig`
              : `${formatDate(event.start_time)} · ${formatTime(event.start_time)}${
                  event.end_time ? ` – ${formatTime(event.end_time)}` : ""
                }`}
          </span>
        </div>

        {/* Type row */}
        <div className="flex items-center gap-2 text-zinc-400 text-sm mb-4">
          <Tag size={14} />
          <span>{EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}</span>
        </div>

        {/* Notes */}
        <div className="mb-4">
          <div className="flex items-center gap-1.5 text-zinc-400 text-xs mb-1.5">
            <FileText size={12} />
            <span>Notizen</span>
          </div>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notizen zum Event..."
            rows={4}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-zinc-500 resize-none"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm text-white font-medium transition-colors"
          >
            <Save size={13} />
            {saving ? "Speichern..." : "Speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Month View ───────────────────────────────────────────────────────────────

function MonthView({
  events,
  currentMonth,
  selectedDay,
  onSelectDay,
  onSelectEvent,
}: {
  events: CalendarEvent[];
  currentMonth: Date;
  selectedDay: Date | null;
  onSelectDay: (d: Date) => void;
  onSelectEvent: (e: CalendarEvent) => void;
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
            <div
              key={key}
              onClick={() => onSelectDay(day)}
              className={cn(
                "min-h-[60px] md:min-h-[80px] p-1 md:p-1.5 border-r border-b border-zinc-800/50 last:border-r-0 cursor-pointer transition-colors",
                !inMonth && "opacity-30",
                selected ? "bg-blue-950/40" : "hover:bg-zinc-800/30"
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
                    onClick={(ev) => { ev.stopPropagation(); onSelectEvent(e); }}
                    className={cn(
                      "text-xs px-1 py-0.5 rounded truncate border cursor-pointer hover:brightness-125 transition-all",
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
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Time Grid (shared by Week + Day) ────────────────────────────────────────

function TimeGrid({
  days,
  events,
  onSelectEvent,
}: {
  days: Date[];
  events: CalendarEvent[];
  onSelectEvent: (e: CalendarEvent) => void;
}) {
  const dayWidth = `${100 / days.length}%`;

  // Group events by day
  const byDay = new Map<string, CalendarEvent[]>();
  events.forEach((e) => {
    const key = format(parseISO(e.start_time), "yyyy-MM-dd");
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(e);
  });

  const getEventTop = (e: CalendarEvent) => {
    const dt = parseISO(e.start_time);
    const mins = (getHours(dt) - 6) * 60 + getMinutes(dt);
    return Math.max(0, mins);
  };

  const getEventHeight = (e: CalendarEvent) => {
    if (!e.end_time) return 45;
    const start = parseISO(e.start_time);
    const end = parseISO(e.end_time);
    const mins = differenceInMinutes(end, start);
    return Math.max(25, mins);
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      {/* Day headers */}
      <div className="flex border-b border-zinc-800">
        <div className="w-12 shrink-0 border-r border-zinc-800" />
        {days.map((d) => (
          <div
            key={d.toISOString()}
            style={{ width: dayWidth }}
            className={cn(
              "text-center py-2 text-sm border-r border-zinc-800 last:border-r-0",
              isToday(d) ? "text-blue-400 font-semibold" : "text-zinc-400"
            )}
          >
            <span className="hidden md:block">
              {format(d, "EEE d. MMM", { locale: de })}
            </span>
            <span className="block md:hidden">
              {format(d, "EEE d", { locale: de })}
            </span>
            {isToday(d) && (
              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full mx-auto mt-0.5" />
            )}
          </div>
        ))}
      </div>

      {/* Time slots */}
      <div className="flex overflow-y-auto" style={{ maxHeight: "70vh" }}>
        {/* Hour labels */}
        <div className="w-12 shrink-0 border-r border-zinc-800">
          {DAY_HOURS.map((h) => (
            <div
              key={h}
              style={{ height: HOUR_HEIGHT }}
              className="border-b border-zinc-800/50 flex items-start pt-1 px-1"
            >
              <span className="text-zinc-600 text-xs">{String(h).padStart(2, "0")}:00</span>
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((d) => {
          const key = format(d, "yyyy-MM-dd");
          const dayEvents = (byDay.get(key) ?? []).filter((e) => !e.all_day);
          const allDayEvents = (byDay.get(key) ?? []).filter((e) => e.all_day);
          const totalMinutes = DAY_HOURS.length * 60;

          return (
            <div
              key={key}
              style={{ width: dayWidth }}
              className={cn(
                "relative border-r border-zinc-800 last:border-r-0",
                isToday(d) && "bg-blue-950/10"
              )}
            >
              {/* Hour grid lines */}
              {DAY_HOURS.map((h) => (
                <div
                  key={h}
                  style={{ height: HOUR_HEIGHT }}
                  className="border-b border-zinc-800/40"
                />
              ))}

              {/* All-day events */}
              {allDayEvents.map((e) => (
                <div
                  key={e.id}
                  onClick={() => onSelectEvent(e)}
                  className={cn(
                    "absolute left-0.5 right-0.5 top-0 px-1 py-0.5 rounded text-xs truncate border cursor-pointer hover:brightness-125 transition-all z-10",
                    EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
                  )}
                >
                  {e.title}
                </div>
              ))}

              {/* Timed events */}
              {dayEvents.map((e) => {
                const topMins = getEventTop(e);
                const heightMins = getEventHeight(e);
                const topPct = (topMins / totalMinutes) * 100;
                const heightPct = (heightMins / totalMinutes) * 100;

                return (
                  <div
                    key={e.id}
                    onClick={() => onSelectEvent(e)}
                    style={{
                      top: `${topPct}%`,
                      height: `${heightPct}%`,
                      minHeight: "20px",
                    }}
                    className={cn(
                      "absolute left-0.5 right-0.5 px-1 py-0.5 rounded text-xs border cursor-pointer hover:brightness-125 transition-all z-10 overflow-hidden",
                      EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
                    )}
                    title={e.title}
                  >
                    <div className="font-medium truncate">{e.title}</div>
                    <div className="opacity-70 text-[10px]">{formatTime(e.start_time)}</div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Week View ────────────────────────────────────────────────────────────────

function WeekView({
  events,
  weekStart,
  onSelectEvent,
}: {
  events: CalendarEvent[];
  weekStart: Date;
  onSelectEvent: (e: CalendarEvent) => void;
}) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const weekEvents = events.filter((e) => {
    const d = parseISO(e.start_time);
    return d >= days[0] && d <= addDays(days[6], 1);
  });

  return <TimeGrid days={days} events={weekEvents} onSelectEvent={onSelectEvent} />;
}

// ─── Day View ─────────────────────────────────────────────────────────────────

function DayView({
  events,
  currentDay,
  onSelectEvent,
}: {
  events: CalendarEvent[];
  currentDay: Date;
  onSelectEvent: (e: CalendarEvent) => void;
}) {
  const dayEvents = events.filter((e) => isSameDay(parseISO(e.start_time), currentDay));
  return <TimeGrid days={[currentDay]} events={dayEvents} onSelectEvent={onSelectEvent} />;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [view, setView] = useState<ViewMode>("month");
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [currentWeek, setCurrentWeek] = useState(startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [currentDay, setCurrentDay] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [activeEvent, setActiveEvent] = useState<CalendarEvent | null>(null);
  const { data, error, isLoading, mutate } = useCalendar(90, 30);

  const handleEventSaved = useCallback(
    (updated: CalendarEvent) => {
      mutate(
        (prev) =>
          prev
            ? {
                events: prev.events.map((e) => (e.id === updated.id ? updated : e)),
              }
            : prev,
        false
      );
    },
    [mutate]
  );

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const events = data?.events ?? [];
  const now = new Date();
  const upcoming = events.filter((e) => parseISO(e.start_time) >= now).slice(0, 8);
  const monthEvents = events.filter((e) => isSameMonth(parseISO(e.start_time), currentMonth));

  const selectedDayEvents = selectedDay
    ? events.filter((e) => isSameDay(parseISO(e.start_time), selectedDay))
    : [];

  // Navigation helpers
  const prev = () => {
    if (view === "month") setCurrentMonth(subMonths(currentMonth, 1));
    else if (view === "week") setCurrentWeek(subWeeks(currentWeek, 1));
    else setCurrentDay(subDays(currentDay, 1));
  };
  const next = () => {
    if (view === "month") setCurrentMonth(addMonths(currentMonth, 1));
    else if (view === "week") setCurrentWeek(addWeeks(currentWeek, 1));
    else setCurrentDay(addDays(currentDay, 1));
  };
  const goToday = () => {
    const today = new Date();
    setCurrentMonth(today);
    setCurrentWeek(startOfWeek(today, { weekStartsOn: 1 }));
    setCurrentDay(today);
    setSelectedDay(today);
  };

  const navLabel = () => {
    if (view === "month") return format(currentMonth, "MMMM yyyy", { locale: de });
    if (view === "week") {
      const end = addDays(currentWeek, 6);
      return `${format(currentWeek, "d. MMM", { locale: de })} – ${format(end, "d. MMM yyyy", { locale: de })}`;
    }
    return format(currentDay, "EEEE, d. MMMM yyyy", { locale: de });
  };

  return (
    <div>
      <Header
        title="📅 Kalender"
        subtitle={`${events.length} Events · ${upcoming.length} bevorstehend`}
      />

      {/* View Tabs + Navigation */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {/* View switcher */}
        <div className="flex bg-zinc-800 rounded-lg p-0.5 gap-0.5">
          {(["month", "week", "day"] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                view === v
                  ? "bg-zinc-700 text-white"
                  : "text-zinc-400 hover:text-white"
              )}
            >
              {v === "month" ? "Monat" : v === "week" ? "Woche" : "Tag"}
            </button>
          ))}
        </div>

        {/* Navigation */}
        <button
          onClick={prev}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <h2 className="text-white font-semibold text-sm truncate">{navLabel()}</h2>
          <button
            onClick={goToday}
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors shrink-0"
          >
            Heute
          </button>
        </div>
        <button
          onClick={next}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Calendar View */}
      <div className="mb-4">
        {view === "month" && (
          <MonthView
            events={monthEvents}
            currentMonth={currentMonth}
            selectedDay={selectedDay}
            onSelectDay={setSelectedDay}
            onSelectEvent={setActiveEvent}
          />
        )}
        {view === "week" && (
          <WeekView
            events={events}
            weekStart={currentWeek}
            onSelectEvent={setActiveEvent}
          />
        )}
        {view === "day" && (
          <DayView
            events={events}
            currentDay={currentDay}
            onSelectEvent={setActiveEvent}
          />
        )}
      </div>

      {/* Selected day details (month view) */}
      {view === "month" && selectedDay && selectedDayEvents.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-4">
          <h2 className="text-white font-semibold mb-3">
            {format(selectedDay, "EEEE, d. MMMM", { locale: de })}
          </h2>
          <div className="space-y-1">
            {selectedDayEvents.map((e) => (
              <button
                key={e.id}
                onClick={() => setActiveEvent(e)}
                className="w-full flex items-start gap-3 py-2 border-b border-zinc-800 last:border-0 text-left hover:bg-zinc-800/30 rounded-lg px-2 transition-colors"
              >
                <span className="text-xl mt-0.5">{EVENT_TYPE_EMOJI[e.event_type] ?? "📌"}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-sm">{e.title}</span>
                    <span
                      className={cn(
                        "text-xs px-1.5 py-0.5 rounded border",
                        EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
                      )}
                    >
                      {EVENT_TYPE_LABEL[e.event_type] ?? e.event_type}
                    </span>
                  </div>
                  {!e.all_day && (
                    <div className="text-zinc-500 text-xs mt-0.5">
                      ⏰ {formatTime(e.start_time)}
                      {e.end_time ? ` – ${formatTime(e.end_time)}` : ""}
                    </div>
                  )}
                  {e.description && (
                    <div className="text-zinc-500 text-xs mt-0.5 truncate">
                      📝 {e.description}
                    </div>
                  )}
                </div>
              </button>
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
          <div>
            {upcoming.map((e) => (
              <button
                key={e.id}
                onClick={() => setActiveEvent(e)}
                className="w-full flex items-start gap-4 py-3 border-b border-zinc-800 last:border-0 text-left hover:bg-zinc-800/30 rounded-lg px-2 transition-colors"
              >
                <div
                  className={cn(
                    "w-2 h-2 rounded-full mt-1.5 shrink-0",
                    EVENT_TYPE_DOT[e.event_type] ?? "bg-zinc-500"
                  )}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white text-sm font-medium">{e.title}</span>
                    <span
                      className={cn(
                        "text-xs px-1.5 py-0.5 rounded border",
                        EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
                      )}
                    >
                      {EVENT_TYPE_LABEL[e.event_type] ?? e.event_type}
                    </span>
                  </div>
                  <div className="text-zinc-500 text-xs mt-0.5">
                    📅 {formatDate(e.start_time)}
                    {!e.all_day && ` · ⏰ ${formatTime(e.start_time)}`}
                    {e.end_time && !e.all_day && ` – ${formatTime(e.end_time)}`}
                  </div>
                  {e.description && (
                    <div className="text-zinc-500 text-xs mt-0.5 truncate">📝 {e.description}</div>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Event Detail Modal */}
      {activeEvent && (
        <EventModal
          event={activeEvent}
          onClose={() => setActiveEvent(null)}
          onSaved={handleEventSaved}
        />
      )}
    </div>
  );
}
