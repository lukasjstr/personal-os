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
} from "date-fns";
import { de } from "date-fns/locale";
import { ChevronLeft, ChevronRight, X, Save, Clock, Tag, FileText, Pencil, Trash2, RefreshCw } from "lucide-react";
import type { CalendarEvent } from "@/lib/api";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";

// ─── Constants ──────────────────────────────────────────────────────────────

const EVENT_TYPE_BADGE: Record<string, string> = {
  training: "bg-green-900/60 text-green-300 border-green-800/60",
  meeting: "bg-blue-900/60 text-blue-300 border-blue-800/60",
  routine: "bg-purple-900/60 text-purple-300 border-purple-800/60",
  deadline: "bg-red-900/60 text-red-300 border-red-800/60",
  reminder: "bg-yellow-900/60 text-yellow-300 border-yellow-800/60",
  wellness: "bg-teal-900/60 text-teal-300 border-teal-800/60",
  fokus: "bg-indigo-900/60 text-indigo-300 border-indigo-800/60",
  social: "bg-pink-900/60 text-pink-300 border-pink-800/60",
  gesundheit: "bg-rose-900/60 text-rose-300 border-rose-800/60",
  reise: "bg-sky-900/60 text-sky-300 border-sky-800/60",
  errand: "bg-orange-900/60 text-orange-300 border-orange-800/60",
};

const EVENT_TYPE_DOT: Record<string, string> = {
  training: "bg-green-500",
  meeting: "bg-blue-500",
  routine: "bg-purple-500",
  deadline: "bg-red-500",
  reminder: "bg-yellow-500",
  wellness: "bg-teal-500",
  fokus: "bg-indigo-500",
  social: "bg-pink-500",
  gesundheit: "bg-rose-500",
  reise: "bg-sky-500",
  errand: "bg-orange-500",
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  training: "Training",
  meeting: "Meeting",
  routine: "Routine",
  deadline: "Deadline",
  reminder: "Erinnerung",
  wellness: "Wellness",
  fokus: "Fokuszeit",
  social: "Social",
  gesundheit: "Gesundheit",
  reise: "Reise",
  errand: "Besorgung",
};

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const HOUR_HEIGHT = 60; // px per hour

type ViewMode = "month" | "week" | "day";

// ─── Day Time Settings ────────────────────────────────────────────────────────

interface DayTimeSettings {
  wakeHour: number;   // first visible hour (e.g. 5 = 05:00)
  sleepHour: number;  // last visible hour (e.g. 23 = 23:00)
}

const DEFAULT_SETTINGS: DayTimeSettings = { wakeHour: 6, sleepHour: 23 };

function loadDaySettings(): DayTimeSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem("cal_day_settings");
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {}
  return DEFAULT_SETTINGS;
}

function saveDaySettings(s: DayTimeSettings) {
  if (typeof window === "undefined") return;
  localStorage.setItem("cal_day_settings", JSON.stringify(s));
}

function DaySettingsPanel({
  settings,
  onChange,
  onClose,
}: {
  settings: DayTimeSettings;
  onChange: (s: DayTimeSettings) => void;
  onClose: () => void;
}) {
  const [wake, setWake] = useState(settings.wakeHour);
  const [sleep, setSleep] = useState(settings.sleepHour);

  const save = () => {
    const s = { wakeHour: wake, sleepHour: Math.max(wake + 1, sleep) };
    onChange(s);
    saveDaySettings(s);
    onClose();
  };

  return (
    <div className="absolute top-full right-0 z-50 mt-1 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl p-4 w-64">
      <h3 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">⚙️ Tageszeiten</h3>
      <div className="space-y-3 mb-4">
        <div>
          <label className="text-zinc-400 text-xs mb-1.5 block">🌅 Aufstehen (erste Stunde)</label>
          <div className="flex gap-1 flex-wrap">
            {[4, 5, 6, 7, 8].map((h) => (
              <button key={h} onClick={() => setWake(h)}
                className={cn("px-2.5 py-1 rounded-lg text-xs border transition-colors",
                  wake === h ? "bg-blue-600/20 border-blue-500 text-blue-300" : "border-zinc-700 text-zinc-400 hover:border-zinc-600")}>
                {String(h).padStart(2, "0")}:00
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-zinc-400 text-xs mb-1.5 block">🌙 Schlafen gehen (letzte Stunde)</label>
          <div className="flex gap-1 flex-wrap">
            {[21, 22, 23, 24].map((h) => (
              <button key={h} onClick={() => setSleep(h)}
                className={cn("px-2.5 py-1 rounded-lg text-xs border transition-colors",
                  sleep === h ? "bg-blue-600/20 border-blue-500 text-blue-300" : "border-zinc-700 text-zinc-400 hover:border-zinc-600")}>
                {h === 24 ? "00:00" : `${String(h).padStart(2, "0")}:00`}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="text-zinc-600 text-xs mb-3">
        Sichtbarer Bereich: {String(wake).padStart(2,"0")}:00 – {sleep === 24 ? "00:00" : `${String(sleep).padStart(2,"0")}:00`}
      </div>
      <div className="flex gap-2">
        <button onClick={save} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium py-2 rounded-lg transition-colors">
          Speichern
        </button>
        <button onClick={onClose} className="px-3 py-2 text-zinc-500 hover:text-white text-xs transition-colors">
          Abbrechen
        </button>
      </div>
    </div>
  );
}

// ─── Event Detail Modal ───────────────────────────────────────────────────────

const EVENT_TYPES = Object.keys(EVENT_TYPE_LABEL);

function EventModal({
  event,
  onClose,
  onSaved,
  onDeleted,
}: {
  event: CalendarEvent;
  onClose: () => void;
  onSaved: (updated: CalendarEvent) => void;
  onDeleted: (id: number) => void;
}) {
  const [editMode, setEditMode] = useState(false);
  const [title, setTitle] = useState(event.title);
  const [eventType, setEventType] = useState(event.event_type);
  const [startTime, setStartTime] = useState(
    event.start_time ? event.start_time.slice(0, 16) : ""
  );
  const [endTime, setEndTime] = useState(
    event.end_time ? event.end_time.slice(0, 16) : ""
  );
  const [notes, setNotes] = useState(event.description ?? "");
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await api.updateCalendarEvent(event.id, {
        title: title.trim() || event.title,
        event_type: eventType,
        start_time: startTime || undefined,
        end_time: endTime || undefined,
        description: notes || null,
      });
      onSaved(updated);
      onClose();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }, [event.id, event.title, title, eventType, startTime, endTime, notes, onSaved, onClose]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    try {
      await api.deleteCalendarEvent(event.id);
      onDeleted(event.id);
      onClose();
    } catch {
      // ignore
    } finally {
      setDeleting(false);
    }
  }, [event.id, onDeleted, onClose]);

  return (
    <>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <div className="bg-zinc-900 border border-zinc-700 rounded-xl w-full max-w-md p-5 shadow-2xl">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1 min-w-0">
              {editMode ? (
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-white font-semibold text-base focus:outline-none focus:border-blue-500"
                  autoFocus
                />
              ) : (
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-2xl">{EVENT_TYPE_EMOJI[event.event_type] ?? "📌"}</span>
                  <h2 className="text-white font-semibold text-lg leading-tight">{event.title}</h2>
                </div>
              )}
              {!editMode && (
                <span className={cn("text-xs px-2 py-0.5 rounded border", EVENT_TYPE_BADGE[event.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600")}>
                  {EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0 ml-2">
              <button onClick={() => setEditMode((v) => !v)} className="p-1.5 rounded-lg text-zinc-400 hover:text-blue-400 hover:bg-zinc-800 transition-colors" title="Bearbeiten">
                <Pencil size={15} />
              </button>
              <button onClick={() => setConfirmDelete(true)} className="p-1.5 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-zinc-800 transition-colors" title="Löschen">
                <Trash2 size={15} />
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
                <X size={16} />
              </button>
            </div>
          </div>

          {editMode ? (
            <div className="space-y-3 mb-4">
              <div>
                <label className="text-zinc-400 text-xs mb-1 block">Typ</label>
                <select value={eventType} onChange={(e) => setEventType(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                  {EVENT_TYPES.map((t) => <option key={t} value={t}>{EVENT_TYPE_LABEL[t]}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 text-xs mb-1 block">Start</label>
                  <input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="text-zinc-400 text-xs mb-1 block">Ende</label>
                  <input type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
                </div>
              </div>
              <div>
                <label className="text-zinc-400 text-xs mb-1 block">Notizen</label>
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-zinc-500 resize-none" />
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 text-zinc-400 text-sm mb-3">
                <Clock size={14} />
                <span>
                  {event.all_day
                    ? `${formatDate(event.start_time)} · Ganztägig`
                    : event.end_time && event.event_type === "reminder" && !isSameDay(parseISO(event.start_time), parseISO(event.end_time))
                    ? `${formatDate(event.start_time)} · ${formatTime(event.start_time)} → fällig: ${formatDate(event.end_time)} ${formatTime(event.end_time)}`
                    : `${formatDate(event.start_time)} · ${formatTime(event.start_time)}${event.end_time ? ` – ${formatTime(event.end_time)}` : ""}`}
                </span>
              </div>
              <div className="flex items-center gap-2 text-zinc-400 text-sm mb-4">
                <Tag size={14} />
                <span>{EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}</span>
              </div>
              {event.description && (
                <div className="mb-4">
                  <div className="flex items-center gap-1.5 text-zinc-400 text-xs mb-1.5">
                    <FileText size={12} />
                    <span>Notizen</span>
                  </div>
                  <p className="text-zinc-300 text-sm">{event.description}</p>
                </div>
              )}
            </>
          )}

          {/* Actions */}
          <div className="flex gap-2 justify-end">
            <button onClick={onClose} className="px-3 py-1.5 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
              Abbrechen
            </button>
            {editMode && (
              <button onClick={handleSave} disabled={saving} className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm text-white font-medium transition-colors">
                <Save size={13} />
                {saving ? "Speichern..." : "Speichern"}
              </button>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Event löschen?"
        message={`"${event.title}" wird dauerhaft gelöscht.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
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

  // Priority order for month view: important events first, routines last/hidden
  const EVENT_TYPE_PRIORITY: Record<string, number> = {
    meeting: 0, training: 1, deadline: 2, travel: 3,
    reminder: 4, errand: 5, work_block: 6, routine: 99,
  };
  const sortByPriority = (a: CalendarEvent, b: CalendarEvent) =>
    (EVENT_TYPE_PRIORITY[a.event_type] ?? 50) - (EVENT_TYPE_PRIORITY[b.event_type] ?? 50);

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
          const allDayEvents = eventsByDay.get(key) ?? [];
          // Month grid: hide routines, sort by importance
          const dayEvents = allDayEvents
            .filter((e) => e.event_type !== "routine")
            .sort(sortByPriority);
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
                {allDayEvents.length > 3 && (
                  <div className="text-xs text-zinc-500 px-1">+{allDayEvents.length - 3}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Overlap layout helper ────────────────────────────────────────────────────

interface LayoutEvent {
  event: CalendarEvent;
  col: number;
  totalCols: number;
  topPx: number;
  heightPx: number;
}

function layoutEvents(events: CalendarEvent[], wakeHour: number): LayoutEvent[] {
  // Sort by start time
  const sorted = [...events].sort(
    (a, b) => parseISO(a.start_time).getTime() - parseISO(b.start_time).getTime()
  );

  const getTopPx = (e: CalendarEvent) => {
    const dt = parseISO(e.start_time);
    return Math.max(0, (getHours(dt) - wakeHour) * HOUR_HEIGHT + (getMinutes(dt) / 60) * HOUR_HEIGHT);
  };

  const getHeightPx = (e: CalendarEvent) => {
    if (!e.end_time) return Math.max(24, HOUR_HEIGHT * 0.75);
    const mins = differenceInMinutes(parseISO(e.end_time), parseISO(e.start_time));
    return Math.max(24, (mins / 60) * HOUR_HEIGHT);
  };

  // Assign columns within overlap groups
  const result: LayoutEvent[] = sorted.map((e) => ({
    event: e,
    col: 0,
    totalCols: 1,
    topPx: getTopPx(e),
    heightPx: getHeightPx(e),
  }));

  // Find groups of overlapping events
  for (let i = 0; i < result.length; i++) {
    const a = result[i];
    const aEnd = a.topPx + a.heightPx;

    // Collect all events that overlap with a
    const group = result.filter((b) => {
      const bEnd = b.topPx + b.heightPx;
      return a.topPx < bEnd && aEnd > b.topPx;
    });

    if (group.length <= 1) continue;

    // Assign columns greedily
    const cols: number[][] = [];
    for (const item of group) {
      let placed = false;
      for (let c = 0; c < cols.length; c++) {
        const colEnd = Math.max(...cols[c].map((idx) => result[idx].topPx + result[idx].heightPx));
        if (item.topPx >= colEnd) {
          cols[c].push(result.indexOf(item));
          item.col = c;
          placed = true;
          break;
        }
      }
      if (!placed) {
        item.col = cols.length;
        cols.push([result.indexOf(item)]);
      }
    }
    const totalCols = cols.length;
    group.forEach((item) => (item.totalCols = Math.max(item.totalCols, totalCols)));
  }

  return result;
}

// ─── Time Grid (shared by Week + Day) ────────────────────────────────────────

function TimeGrid({
  days,
  events,
  onSelectEvent,
  settings,
}: {
  days: Date[];
  events: CalendarEvent[];
  onSelectEvent: (e: CalendarEvent) => void;
  settings: DayTimeSettings;
}) {
  const dayHours = Array.from({ length: settings.sleepHour - settings.wakeHour + 1 }, (_, i) => i + settings.wakeHour);
  const dayWidth = `${100 / days.length}%`;
  const totalGridPx = dayHours.length * HOUR_HEIGHT;

  // Group events by day
  const byDay = new Map<string, CalendarEvent[]>();
  events.forEach((e) => {
    const key = format(parseISO(e.start_time), "yyyy-MM-dd");
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(e);
  });

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      {/* Day headers */}
      <div className="flex border-b border-zinc-800">
        <div className="w-14 shrink-0 border-r border-zinc-800" />
        {days.map((d) => (
          <div
            key={d.toISOString()}
            style={{ width: dayWidth }}
            className={cn(
              "text-center py-2.5 text-sm border-r border-zinc-800 last:border-r-0",
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
      <div className="flex overflow-y-auto" style={{ maxHeight: "72vh" }}>
        {/* Hour labels */}
        <div className="w-14 shrink-0 border-r border-zinc-800 select-none">
          {dayHours.map((h) => (
            <div
              key={h}
              style={{ height: HOUR_HEIGHT }}
              className="border-b border-zinc-800/40 flex items-start justify-end pr-2 pt-1"
            >
              <span className="text-zinc-500 text-[11px] font-mono">
                {String(h).padStart(2, "0")}:00
              </span>
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((d) => {
          const key = format(d, "yyyy-MM-dd");
          const dayEvents = (byDay.get(key) ?? []).filter((e) => !e.all_day);
          const allDayEvents = (byDay.get(key) ?? []).filter((e) => e.all_day);
          const laid = layoutEvents(dayEvents, settings.wakeHour);

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
              {dayHours.map((h) => (
                <div
                  key={h}
                  style={{ height: HOUR_HEIGHT }}
                  className={cn(
                    "border-b",
                    h % 2 === 0 ? "border-zinc-800/60" : "border-zinc-800/25"
                  )}
                />
              ))}

              {/* All-day events banner */}
              {allDayEvents.map((e) => (
                <div
                  key={e.id}
                  onClick={() => onSelectEvent(e)}
                  className={cn(
                    "absolute left-1 right-1 top-1 px-2 py-1 rounded-md text-xs truncate border cursor-pointer hover:brightness-125 transition-all z-10",
                    EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
                  )}
                >
                  {EVENT_TYPE_EMOJI[e.event_type] ?? "📌"} {e.title}
                </div>
              ))}

              {/* Timed events with overlap columns */}
              {laid.map(({ event: e, col, totalCols, topPx, heightPx }) => {
                const colWidthPct = 100 / totalCols;
                const leftPct = col * colWidthPct;
                // Small gap between columns
                const gapPx = totalCols > 1 ? 2 : 1;

                return (
                  <div
                    key={e.id}
                    onClick={() => onSelectEvent(e)}
                    style={{
                      position: "absolute",
                      top: `${topPx}px`,
                      height: `${Math.max(heightPx, 22)}px`,
                      left: `calc(${leftPct}% + ${gapPx}px)`,
                      width: `calc(${colWidthPct}% - ${gapPx * 2}px)`,
                      zIndex: 10 + col,
                    }}
                    className={cn(
                      "px-1.5 py-0.5 rounded-md text-xs border cursor-pointer hover:brightness-125 hover:z-20 transition-all overflow-hidden shadow-sm",
                      EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
                    )}
                    title={`${e.title} · ${formatTime(e.start_time)}${e.end_time ? ` – ${formatTime(e.end_time)}` : ""}`}
                  >
                    <div className="font-semibold truncate leading-tight">
                      {EVENT_TYPE_EMOJI[e.event_type] ? `${EVENT_TYPE_EMOJI[e.event_type]} ` : ""}{e.title}
                    </div>
                    {heightPx > 28 && (
                      <div className="opacity-75 text-[10px] leading-tight mt-0.5">
                        {formatTime(e.start_time)}{e.end_time ? ` – ${formatTime(e.end_time)}` : ""}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Current time indicator */}
              {isToday(d) && (() => {
                const now = new Date();
                const nowMins = (getHours(now) - settings.wakeHour) * 60 + getMinutes(now);
                if (nowMins < 0 || nowMins > totalGridPx) return null;
                const topPx = (nowMins / 60) * HOUR_HEIGHT;
                return (
                  <div
                    style={{ top: `${topPx}px` }}
                    className="absolute left-0 right-0 z-20 pointer-events-none"
                  >
                    <div className="relative flex items-center">
                      <div className="w-2 h-2 bg-red-500 rounded-full -ml-1 shrink-0" />
                      <div className="flex-1 h-px bg-red-500/70" />
                    </div>
                  </div>
                );
              })()}
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
  settings,
}: {
  events: CalendarEvent[];
  weekStart: Date;
  onSelectEvent: (e: CalendarEvent) => void;
  settings: DayTimeSettings;
}) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const weekEvents = events.filter((e) => {
    const d = parseISO(e.start_time);
    return d >= days[0] && d <= addDays(days[6], 1);
  });

  return <TimeGrid days={days} events={weekEvents} onSelectEvent={onSelectEvent} settings={settings} />;
}

// ─── Day View ─────────────────────────────────────────────────────────────────

function DayView({
  events,
  currentDay,
  onSelectEvent,
  settings,
}: {
  events: CalendarEvent[];
  currentDay: Date;
  onSelectEvent: (e: CalendarEvent) => void;
  settings: DayTimeSettings;
}) {
  const dayEvents = events.filter((e) => isSameDay(parseISO(e.start_time), currentDay));
  return <TimeGrid days={[currentDay]} events={dayEvents} onSelectEvent={onSelectEvent} settings={settings} />;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [view, setView] = useState<ViewMode>("month");
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [currentWeek, setCurrentWeek] = useState(startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [currentDay, setCurrentDay] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [activeEvent, setActiveEvent] = useState<CalendarEvent | null>(null);
  const [daySettings, setDaySettings] = useState<DayTimeSettings>(loadDaySettings);
  const [showSettings, setShowSettings] = useState(false);
  const { data, error, isLoading, mutate } = useCalendar(90, 30);
  const { toasts, addToast, dismissToast } = useToast();

  const handleEventSaved = useCallback(
    (updated: CalendarEvent) => {
      mutate(
        (prev) =>
          prev
            ? { events: prev.events.map((e) => (e.id === updated.id ? updated : e)) }
            : prev,
        false
      );
      addToast("Event aktualisiert", "success");
    },
    [mutate, addToast]
  );

  const handleEventDeleted = useCallback(
    (id: number) => {
      mutate(
        (prev) => prev ? { events: prev.events.filter((e) => e.id !== id) } : prev,
        false
      );
      addToast("Event gelöscht", "success");
    },
    [mutate, addToast]
  );

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

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
          <button
            onClick={() => mutate()}
            className="p-1 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors shrink-0"
            title="Kalender aktualisieren"
          >
            <RefreshCw size={13} />
          </button>
        </div>
        <button
          onClick={next}
          className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <ChevronRight size={16} />
        </button>

        {/* Day settings gear */}
        {(view === "week" || view === "day") && (
          <div className="relative">
            <button
              onClick={() => setShowSettings((v) => !v)}
              className={cn(
                "p-2 rounded-lg transition-colors",
                showSettings ? "text-blue-400 bg-zinc-800" : "text-zinc-500 hover:text-white hover:bg-zinc-800"
              )}
              title="Tageszeiten einstellen"
            >
              ⚙️
            </button>
            {showSettings && (
              <DaySettingsPanel
                settings={daySettings}
                onChange={setDaySettings}
                onClose={() => setShowSettings(false)}
              />
            )}
          </div>
        )}
      </div>

      {/* Category Legend */}
      <div className="flex flex-wrap gap-2 mb-4">
        {Object.entries(EVENT_TYPE_LABEL).map(([type, label]) => (
          <span
            key={type}
            className={cn(
              "flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full border",
              EVENT_TYPE_BADGE[type] ?? "bg-zinc-800/60 text-zinc-400 border-zinc-700"
            )}
          >
            <span className={cn("w-2 h-2 rounded-full", EVENT_TYPE_DOT[type] ?? "bg-zinc-500")} />
            {EVENT_TYPE_EMOJI[type] ?? "📌"} {label}
          </span>
        ))}
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
            settings={daySettings}
          />
        )}
        {view === "day" && (
          <DayView
            events={events}
            currentDay={currentDay}
            onSelectEvent={setActiveEvent}
            settings={daySettings}
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
                      {e.end_time && e.event_type === "reminder" && !isSameDay(parseISO(e.start_time), parseISO(e.end_time))
                        ? ` → erinnert an ${formatDate(e.end_time)} ${formatTime(e.end_time)}`
                        : e.end_time ? ` – ${formatTime(e.end_time)}` : ""}
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
                    {e.end_time && !e.all_day && e.event_type === "reminder" && !isSameDay(parseISO(e.start_time), parseISO(e.end_time))
                      ? ` → fällig: ${formatDate(e.end_time)} ${formatTime(e.end_time)}`
                      : e.end_time && !e.all_day
                      ? ` – ${formatTime(e.end_time)}`
                      : null}
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
          onDeleted={handleEventDeleted}
        />
      )}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
