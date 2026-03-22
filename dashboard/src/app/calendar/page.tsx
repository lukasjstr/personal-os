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
  isTomorrow,
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

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Detect midnight-to-midnight events that are effectively all-day. */
function isEffectivelyAllDay(e: { start_time: string; end_time?: string | null; all_day: boolean }): boolean {
  if (e.all_day) return true;
  const s = parseISO(e.start_time);
  if (getHours(s) !== 0 || getMinutes(s) !== 0) return false;
  if (!e.end_time) return true;
  const en = parseISO(e.end_time);
  return getHours(en) === 0 && getMinutes(en) === 0;
}

function eventTimeStr(e: { start_time: string; end_time?: string | null; all_day: boolean; event_type: string }): string {
  if (isEffectivelyAllDay(e)) return "Ganztägig";
  const start = formatTime(e.start_time);
  if (e.event_type === "reminder") {
    if (e.end_time && !isSameDay(parseISO(e.start_time), parseISO(e.end_time))) {
      return `${start} → fällig: ${formatDate(e.end_time)} ${formatTime(e.end_time)}`;
    }
    return start;
  }
  if (e.end_time) return `${start} – ${formatTime(e.end_time)}`;
  return start;
}

/** Strip HTML tags, convert <br>/<p> to newlines, decode basic entities. */
function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Format event duration (e.g. "30 min", "1h 30min"). Returns null if indeterminate. */
function eventDuration(e: { start_time: string; end_time?: string | null; all_day: boolean; event_type: string }): string | null {
  if (isEffectivelyAllDay(e) || !e.end_time) return null;
  const mins = differenceInMinutes(parseISO(e.end_time), parseISO(e.start_time));
  if (mins <= 0) return null;
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

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
  wakeHour: number;
  sleepHour: number;
}

/** 0=Mo, 1=Di, 2=Mi, 3=Do, 4=Fr, 5=Sa, 6=So */
type WeekSettings = Record<number, DayTimeSettings>;

const DAY_LABELS_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

const DEFAULT_WEEK_SETTINGS: WeekSettings = {
  0: { wakeHour: 6, sleepHour: 23 },
  1: { wakeHour: 6, sleepHour: 23 },
  2: { wakeHour: 6, sleepHour: 23 },
  3: { wakeHour: 6, sleepHour: 23 },
  4: { wakeHour: 6, sleepHour: 23 },
  5: { wakeHour: 8, sleepHour: 22 },
  6: { wakeHour: 9, sleepHour: 22 },
};

/** Convert JS getDay() (0=Sun) to 0=Mon…6=Sun index */
function getDayIdx(d: Date): number {
  const dow = d.getDay();
  return dow === 0 ? 6 : dow - 1;
}

/** Get settings for a specific calendar day */
function settingsForDay(ws: WeekSettings, d: Date): DayTimeSettings {
  return ws[getDayIdx(d)] ?? DEFAULT_WEEK_SETTINGS[0];
}

/** Compute the overall grid range (min wake, max sleep) across all days */
function gridRange(ws: WeekSettings): DayTimeSettings {
  const vals = Object.values(ws);
  return {
    wakeHour: Math.min(...vals.map((s) => s.wakeHour)),
    sleepHour: Math.max(...vals.map((s) => s.sleepHour)),
  };
}

function loadDaySettings(): WeekSettings {
  if (typeof window === "undefined") return DEFAULT_WEEK_SETTINGS;
  try {
    const raw = localStorage.getItem("cal_week_settings");
    if (raw) {
      const parsed = JSON.parse(raw);
      // Merge with defaults so new keys are filled
      return { ...DEFAULT_WEEK_SETTINGS, ...parsed };
    }
    // Migrate old single-setting format
    const old = localStorage.getItem("cal_day_settings");
    if (old) {
      const s = JSON.parse(old) as DayTimeSettings;
      return Object.fromEntries([0,1,2,3,4,5,6].map((i) => [i, s])) as WeekSettings;
    }
  } catch {}
  return DEFAULT_WEEK_SETTINGS;
}

function saveDaySettings(s: WeekSettings) {
  if (typeof window === "undefined") return;
  localStorage.setItem("cal_week_settings", JSON.stringify(s));
}

function DaySettingsPanel({
  settings,
  onChange,
  onClose,
}: {
  settings: WeekSettings;
  onChange: (s: WeekSettings) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<WeekSettings>({ ...settings });
  const [activeDay, setActiveDay] = useState(0); // 0=Mo

  const setWake = (h: number) =>
    setDraft((prev) => ({ ...prev, [activeDay]: { ...prev[activeDay], wakeHour: h } }));
  const setSleep = (h: number) =>
    setDraft((prev) => ({ ...prev, [activeDay]: { ...prev[activeDay], sleepHour: Math.max(h, prev[activeDay].wakeHour + 1) } }));

  const applyToAll = () => {
    const s = draft[activeDay];
    setDraft(Object.fromEntries([0,1,2,3,4,5,6].map((i) => [i, { ...s }])) as WeekSettings);
  };

  const save = () => {
    // Ensure sleepHour > wakeHour for every day
    const fixed: WeekSettings = Object.fromEntries(
      Object.entries(draft).map(([k, v]) => [k, { wakeHour: v.wakeHour, sleepHour: Math.max(v.sleepHour, v.wakeHour + 1) }])
    ) as WeekSettings;
    onChange(fixed);
    saveDaySettings(fixed);
    onClose();
  };

  const cur = draft[activeDay];

  return (
    <div className="absolute top-full right-0 z-50 mt-1 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl p-4 w-72">
      <h3 className="text-white font-semibold text-sm mb-3">⚙️ Tageszeiten pro Wochentag</h3>

      {/* Day tabs */}
      <div className="grid grid-cols-7 gap-0.5 mb-3">
        {DAY_LABELS_SHORT.map((label, i) => (
          <button
            key={i}
            onClick={() => setActiveDay(i)}
            className={cn(
              "py-1.5 rounded text-xs font-medium transition-colors flex flex-col items-center gap-0.5",
              activeDay === i ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white"
            )}
          >
            <span>{label}</span>
            <span className={cn("text-[9px] font-mono leading-none", activeDay === i ? "text-blue-200" : "text-zinc-600")}>
              {String(draft[i].wakeHour).padStart(2,"0")}
            </span>
          </button>
        ))}
      </div>

      {/* Wake hour */}
      <div className="mb-3">
        <label className="text-zinc-400 text-xs mb-1.5 block">🌅 Aufstehen</label>
        <div className="flex gap-1 flex-wrap">
          {[4, 5, 6, 7, 8, 9, 10].map((h) => (
            <button key={h} onClick={() => setWake(h)}
              className={cn("px-2 py-1 rounded-lg text-xs border transition-colors",
                cur.wakeHour === h ? "bg-blue-600/20 border-blue-500 text-blue-300" : "border-zinc-700 text-zinc-400 hover:border-zinc-600")}>
              {String(h).padStart(2,"0")}:00
            </button>
          ))}
        </div>
      </div>

      {/* Sleep hour */}
      <div className="mb-3">
        <label className="text-zinc-400 text-xs mb-1.5 block">🌙 Schlafen</label>
        <div className="flex gap-1 flex-wrap">
          {[20, 21, 22, 23, 24].map((h) => (
            <button key={h} onClick={() => setSleep(h)}
              className={cn("px-2 py-1 rounded-lg text-xs border transition-colors",
                cur.sleepHour === h ? "bg-blue-600/20 border-blue-500 text-blue-300" : "border-zinc-700 text-zinc-400 hover:border-zinc-600")}>
              {h === 24 ? "00:00" : `${String(h).padStart(2,"0")}:00`}
            </button>
          ))}
        </div>
      </div>

      <div className="text-zinc-600 text-xs mb-3">
        {DAY_LABELS_SHORT[activeDay]}: {String(cur.wakeHour).padStart(2,"0")}:00 – {cur.sleepHour === 24 ? "00:00" : `${String(cur.sleepHour).padStart(2,"0")}:00`}
      </div>

      <button onClick={applyToAll} className="w-full mb-2 py-1.5 rounded-lg text-xs border border-zinc-700 text-zinc-400 hover:border-zinc-600 hover:text-white transition-colors">
        Auf alle Tage anwenden
      </button>

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
  const [saveError, setSaveError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
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
      setSaveError("Speichern fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setSaving(false);
    }
  }, [event.id, event.title, title, eventType, startTime, endTime, notes, onSaved, onClose]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    setSaveError(null);
    try {
      await api.deleteCalendarEvent(event.id);
      onDeleted(event.id);
      onClose();
    } catch {
      setSaveError("Löschen fehlgeschlagen. Bitte erneut versuchen.");
      setConfirmDelete(false);
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
              <div className="flex items-center gap-2 text-zinc-400 text-sm mb-4">
                <Clock size={14} className="shrink-0" />
                <span>
                  {isEffectivelyAllDay(event)
                    ? `${formatDate(event.start_time)} · Ganztägig`
                    : `${formatDate(event.start_time)} · ${eventTimeStr(event)}`}
                </span>
                {parseISO(event.start_time) < new Date() && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/60 text-zinc-500 border border-zinc-700 ml-1">
                    Vergangen
                  </span>
                )}
              </div>
              {event.description && (
                <div className="mb-4">
                  <div className="flex items-center gap-1.5 text-zinc-400 text-xs mb-1.5">
                    <FileText size={12} />
                    <span>Notizen</span>
                  </div>
                  <p className="text-zinc-300 text-sm whitespace-pre-wrap leading-relaxed">
                    {stripHtml(event.description)}
                  </p>
                </div>
              )}
            </>
          )}

          {/* Error message */}
          {saveError && (
            <div className="mb-3 px-3 py-2 bg-red-900/30 border border-red-800/60 rounded-lg text-red-300 text-xs">
              {saveError}
            </div>
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
                {dayEvents.length > 3 && (
                  <div className="text-xs text-zinc-500 px-1">+{dayEvents.length - 3} weitere</div>
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
  weekSettings,
}: {
  days: Date[];
  events: CalendarEvent[];
  onSelectEvent: (e: CalendarEvent) => void;
  weekSettings: WeekSettings;
}) {
  const range = gridRange(weekSettings);
  const dayHours = Array.from({ length: range.sleepHour - range.wakeHour + 1 }, (_, i) => i + range.wakeHour);
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
          const daySetting = settingsForDay(weekSettings, d);
          const dayEvents = (byDay.get(key) ?? []).filter((e) => !e.all_day);
          const allDayEvents = (byDay.get(key) ?? []).filter((e) => e.all_day);
          const laid = layoutEvents(dayEvents, range.wakeHour);

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
                      EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600",
                      parseISO(e.start_time) < new Date() && "opacity-40"
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

              {/* Grey out hours outside this day's configured range */}
              {daySetting.wakeHour > range.wakeHour && (
                <div
                  className="absolute left-0 right-0 top-0 bg-zinc-950/60 pointer-events-none z-5"
                  style={{ height: `${(daySetting.wakeHour - range.wakeHour) * HOUR_HEIGHT}px` }}
                />
              )}
              {daySetting.sleepHour < range.sleepHour && (
                <div
                  className="absolute left-0 right-0 bottom-0 bg-zinc-950/60 pointer-events-none z-5"
                  style={{ height: `${(range.sleepHour - daySetting.sleepHour) * HOUR_HEIGHT}px` }}
                />
              )}

              {/* Current time indicator */}
              {isToday(d) && (() => {
                const now = new Date();
                const nowMins = (getHours(now) - range.wakeHour) * 60 + getMinutes(now);
                const totalGridMins = (range.sleepHour - range.wakeHour) * 60;
                if (nowMins < 0 || nowMins > totalGridMins) return null;
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
  weekSettings,
}: {
  events: CalendarEvent[];
  weekStart: Date;
  onSelectEvent: (e: CalendarEvent) => void;
  weekSettings: WeekSettings;
}) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const weekEvents = events.filter((e) => {
    const d = parseISO(e.start_time);
    return d >= days[0] && d <= addDays(days[6], 1);
  });

  return <TimeGrid days={days} events={weekEvents} onSelectEvent={onSelectEvent} weekSettings={weekSettings} />;
}

// ─── Day View ─────────────────────────────────────────────────────────────────

function DayView({
  events,
  currentDay,
  onSelectEvent,
  weekSettings,
}: {
  events: CalendarEvent[];
  currentDay: Date;
  onSelectEvent: (e: CalendarEvent) => void;
  weekSettings: WeekSettings;
}) {
  const dayEvents = events.filter((e) => isSameDay(parseISO(e.start_time), currentDay));
  return <TimeGrid days={[currentDay]} events={dayEvents} onSelectEvent={onSelectEvent} weekSettings={weekSettings} />;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [view, setView] = useState<ViewMode>("month");
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [currentWeek, setCurrentWeek] = useState(startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [currentDay, setCurrentDay] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [activeEvent, setActiveEvent] = useState<CalendarEvent | null>(null);
  const [daySettings, setDaySettings] = useState<WeekSettings>(loadDaySettings);
  const [showSettings, setShowSettings] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("");
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
  // Include events from start of today so past-today events appear greyed out
  const startOfToday = new Date(now); startOfToday.setHours(0, 0, 0, 0);
  const upcoming = events
    .filter((e) => parseISO(e.start_time) >= startOfToday)
    .filter((e) => !searchQuery || e.title.toLowerCase().includes(searchQuery.toLowerCase()))
    .filter((e) => !filterType || e.event_type === filterType)
    .slice(0, 50);

  // Group upcoming by day
  const upcomingByDay = upcoming.reduce<{ label: string; date: Date; events: typeof upcoming }[]>((acc, e) => {
    const d = parseISO(e.start_time);
    const key = format(d, "yyyy-MM-dd");
    let group = acc.find((g) => format(g.date, "yyyy-MM-dd") === key);
    if (!group) {
      const label = isToday(d) ? "Heute" : isTomorrow(d) ? "Morgen" : format(d, "EEEE, dd. MMM", { locale: de });
      group = { label, date: d, events: [] };
      acc.push(group);
    }
    group.events.push(e);
    return acc;
  }, []);
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

        {/* Day settings — always visible */}
        <div className="relative">
          <button
            onClick={() => setShowSettings((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-colors",
              showSettings
                ? "bg-zinc-800 border-zinc-600 text-blue-400"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-600 hover:text-white"
            )}
            title="Tageszeiten einstellen"
          >
            ⚙️ Zeiten
          </button>
          {showSettings && (
            <DaySettingsPanel
              settings={daySettings}
              onChange={setDaySettings}
              onClose={() => setShowSettings(false)}
            />
          )}
        </div>
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
            weekSettings={daySettings}
          />
        )}
        {view === "day" && (
          <DayView
            events={events}
            currentDay={currentDay}
            onSelectEvent={setActiveEvent}
            weekSettings={daySettings}
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
                      ⏰ {eventTimeStr(e)}
                    </div>
                  )}
                  {e.description && (
                    <div className="text-zinc-500 text-xs mt-0.5 truncate">
                      📝 {stripHtml(e.description)}
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
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="text-white font-semibold flex items-center gap-2">
            <span>⏰</span> Bevorstehende Events
          </h2>
          <input
            type="text"
            placeholder="Suchen..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-blue-500 w-40"
          />
        </div>
        {/* Type filter pills */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          <button
            onClick={() => setFilterType("")}
            className={cn(
              "text-xs px-2.5 py-1 rounded-full border transition-colors",
              !filterType ? "bg-zinc-700 border-zinc-600 text-white" : "border-zinc-700 text-zinc-500 hover:border-zinc-600 hover:text-zinc-300"
            )}
          >
            Alle
          </button>
          {Object.entries(EVENT_TYPE_LABEL).map(([type, label]) => (
            <button
              key={type}
              onClick={() => setFilterType(filterType === type ? "" : type)}
              className={cn(
                "text-xs px-2.5 py-1 rounded-full border transition-colors",
                filterType === type
                  ? cn(EVENT_TYPE_BADGE[type] ?? "bg-zinc-700 border-zinc-600 text-white")
                  : "border-zinc-700 text-zinc-500 hover:border-zinc-600 hover:text-zinc-300"
              )}
            >
              {EVENT_TYPE_EMOJI[type] ?? "📌"} {label}
            </button>
          ))}
        </div>
        {upcomingByDay.length === 0 ? (
          <EmptyState emoji="📅" message="Keine bevorstehenden Events" />
        ) : (
          <div className="space-y-4">
            {upcomingByDay.map((group) => (
              <div key={group.label}>
                {/* Day header */}
                <div className="flex items-center gap-2 mb-2">
                  <span className={cn(
                    "text-xs font-semibold uppercase tracking-wider",
                    isToday(group.date) ? "text-blue-400" : "text-zinc-500"
                  )}>
                    {group.label}
                  </span>
                  <div className="flex-1 h-px bg-zinc-800" />
                </div>
                {/* Events for this day */}
                <div className="space-y-0.5">
                  {group.events.map((e) => {
                    const isPast = parseISO(e.start_time) < now;
                    const minsUntil = differenceInMinutes(parseISO(e.start_time), now);
                    const isImminent = minsUntil >= 0 && minsUntil <= 60;
                    return (
                      <button
                        key={e.id}
                        onClick={() => setActiveEvent(e)}
                        className={cn(
                          "w-full flex items-start gap-3 py-2.5 px-2 rounded-lg text-left transition-colors",
                          isPast ? "opacity-40 hover:opacity-60" : "hover:bg-zinc-800/40"
                        )}
                      >
                        <div className={cn(
                          "w-2 h-2 rounded-full mt-1.5 shrink-0",
                          EVENT_TYPE_DOT[e.event_type] ?? "bg-zinc-500"
                        )} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={cn("text-sm font-medium", isPast ? "text-zinc-400 line-through" : "text-white")}>
                              {e.title}
                            </span>
                            <span className={cn("text-xs px-1.5 py-0.5 rounded border", EVENT_TYPE_BADGE[e.event_type] ?? "bg-zinc-700 text-zinc-300 border-zinc-600")}>
                              {EVENT_TYPE_LABEL[e.event_type] ?? e.event_type}
                            </span>
                            {isImminent && (
                              <span className="text-xs px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300 border border-orange-500/30 font-medium">
                                {minsUntil === 0 ? "Jetzt" : `in ${minsUntil} Min.`}
                              </span>
                            )}
                          </div>
                          {!isEffectivelyAllDay(e) && (
                            <div className="text-zinc-500 text-xs mt-0.5 flex items-center gap-2">
                              <span>⏰ {eventTimeStr(e)}</span>
                              {eventDuration(e) && (
                                <span className="text-zinc-600">· {eventDuration(e)}</span>
                              )}
                            </div>
                          )}
                          {e.description && (
                            <div className="text-zinc-500 text-xs mt-0.5 truncate">📝 {stripHtml(e.description)}</div>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
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
