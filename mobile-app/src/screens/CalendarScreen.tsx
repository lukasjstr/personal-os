import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiRequest } from '../lib/apiClient';
import { useApi } from '../hooks/useApi';
import { ErrorState } from '../components/ErrorState';

// ── Types ──────────────────────────────────────────────────────────────────

interface CalendarEvent {
  id: number;
  title?: string | null;
  description?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  all_day?: boolean | null;
  event_type?: string | null;
  notes?: string | null;
  linked_task_id?: number | null;
  linked_task_title?: string | null;
}

interface CalendarResponse {
  events?: CalendarEvent[];
}

// ── Filter ─────────────────────────────────────────────────────────────────

type FilterKey = 'today' | 'next7' | 'next30' | 'day';

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'next7', label: '7 Days' },
  { key: 'next30', label: '30 Days' },
  { key: 'day', label: 'Timeline' },
];

function filterEvents(events: CalendarEvent[], filter: FilterKey, dayRef?: Date): CalendarEvent[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todayEnd = new Date(todayStart.getTime() + 86400_000);

  return events.filter(ev => {
    const raw = ev.start_time;
    if (!raw) return false;
    const start = new Date(raw);
    if (isNaN(start.getTime())) return false;

    if (filter === 'today') {
      return start >= todayStart && start < todayEnd;
    }
    if (filter === 'next7') {
      const cutoff = new Date(todayStart.getTime() + 7 * 86400_000);
      return start >= todayStart && start < cutoff;
    }
    if (filter === 'next30') {
      const cutoff = new Date(todayStart.getTime() + 30 * 86400_000);
      return start >= todayStart && start < cutoff;
    }
    if (filter === 'day' && dayRef) {
      const dayStart = new Date(dayRef.getFullYear(), dayRef.getMonth(), dayRef.getDate());
      const dayEnd = new Date(dayStart.getTime() + 86400_000);
      return start >= dayStart && start < dayEnd;
    }
    return false;
  });
}

// ── Formatting helpers ─────────────────────────────────────────────────────

function safeDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

function formatEventTime(
  startIso: string | null | undefined,
  endIso: string | null | undefined,
  allDay: boolean | null | undefined,
): string {
  const start = safeDate(startIso);
  if (!start) return '';
  if (allDay) {
    return start.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  }
  const dateStr = start.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  const timeStr = start.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  const end = safeDate(endIso);
  if (end) {
    const endTime = end.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    return `${dateStr}  ${timeStr} – ${endTime}`;
  }
  return `${dateStr}  ${timeStr}`;
}

function typeColor(type: string | null | undefined): string {
  switch ((type ?? '').toLowerCase()) {
    case 'work': return '#6366f1';
    case 'personal': return '#10b981';
    case 'fitness': return '#f59e0b';
    case 'health': return '#ef4444';
    default: return '#6b7280';
  }
}

/** Format a Date to local ISO datetime string YYYY-MM-DDTHH:MM */
function toLocalISO(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Adjust a Date by ±minutes, returning a new Date */
function shiftMinutes(d: Date, delta: number): Date {
  return new Date(d.getTime() + delta * 60_000);
}

// ── Event card (list view) ─────────────────────────────────────────────────

interface EventItemProps {
  item: CalendarEvent;
  onPress: (item: CalendarEvent) => void;
}

function EventItem({ item, onPress }: EventItemProps) {
  const timeLabel = formatEventTime(item.start_time, item.end_time, item.all_day);
  const dotColor = typeColor(item.event_type);
  const notePreview = item.notes?.trim();

  return (
    <TouchableOpacity style={styles.eventCard} onPress={() => onPress(item)} activeOpacity={0.75}>
      <View style={[styles.eventDot, { backgroundColor: dotColor }]} />
      <View style={styles.eventBody}>
        <Text style={styles.eventTitle} numberOfLines={2}>
          {item.title ?? 'Untitled event'}
        </Text>
        {timeLabel ? <Text style={styles.eventTime}>{timeLabel}</Text> : null}
        <View style={styles.eventMeta}>
          {item.event_type ? (
            <View style={[styles.typePill, { backgroundColor: dotColor + '33' }]}>
              <Text style={[styles.typePillText, { color: dotColor }]}>{item.event_type}</Text>
            </View>
          ) : null}
          {item.linked_task_id ? (
            <View style={styles.taskLinkPill}>
              <Text style={styles.taskLinkPillText} numberOfLines={1}>
                {item.linked_task_title ?? 'Linked task'}
              </Text>
            </View>
          ) : null}
        </View>
        {notePreview ? (
          <Text style={styles.notePreview} numberOfLines={1}>
            {notePreview}
          </Text>
        ) : null}
      </View>
    </TouchableOpacity>
  );
}

// ── Day Timeline ──────────────────────────────────────────────────────────

const TIMELINE_START_HOUR = 6;   // 6:00 AM
const TIMELINE_END_HOUR = 23;    // 11:00 PM
const HOUR_HEIGHT = 64;          // px per hour

function formatDayHeader(d: Date): string {
  const today = new Date();
  const isToday =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();
  const label = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  return isToday ? `Today — ${label}` : label;
}

interface DayTimelineProps {
  events: CalendarEvent[];
  day: Date;
  onDayChange: (d: Date) => void;
  onEventPress: (ev: CalendarEvent) => void;
}

function DayTimeline({ events, day, onDayChange, onEventPress }: DayTimelineProps) {
  const scrollRef = useRef<ScrollView>(null);
  const totalHours = TIMELINE_END_HOUR - TIMELINE_START_HOUR;
  const totalHeight = totalHours * HOUR_HEIGHT;

  // Current time indicator
  const now = new Date();
  const nowFrac = now.getHours() + now.getMinutes() / 60;
  const showNowLine =
    day.toDateString() === now.toDateString() &&
    nowFrac >= TIMELINE_START_HOUR &&
    nowFrac < TIMELINE_END_HOUR;
  const nowTop = (nowFrac - TIMELINE_START_HOUR) * HOUR_HEIGHT;

  // Timed events only
  const timedEvents = useMemo(
    () => events.filter(ev => ev.start_time && !ev.all_day),
    [events],
  );

  // All-day events
  const allDayEvents = useMemo(
    () => events.filter(ev => ev.all_day),
    [events],
  );

  return (
    <View style={styles.timelineWrapper}>
      {/* Day navigation */}
      <View style={styles.dayNav}>
        <TouchableOpacity
          style={styles.dayNavBtn}
          onPress={() => onDayChange(new Date(day.getTime() - 86400_000))}
          hitSlop={8}
        >
          <Text style={styles.dayNavArrow}>‹</Text>
        </TouchableOpacity>
        <Text style={styles.dayNavLabel}>{formatDayHeader(day)}</Text>
        <TouchableOpacity
          style={styles.dayNavBtn}
          onPress={() => onDayChange(new Date(day.getTime() + 86400_000))}
          hitSlop={8}
        >
          <Text style={styles.dayNavArrow}>›</Text>
        </TouchableOpacity>
      </View>

      {/* All-day strip */}
      {allDayEvents.length > 0 && (
        <View style={styles.allDayStrip}>
          <Text style={styles.allDayLabel}>All day</Text>
          <View style={styles.allDayEvents}>
            {allDayEvents.map(ev => (
              <TouchableOpacity
                key={ev.id}
                style={[styles.allDayPill, { backgroundColor: typeColor(ev.event_type) + '33', borderColor: typeColor(ev.event_type) }]}
                onPress={() => onEventPress(ev)}
                activeOpacity={0.75}
              >
                <Text style={[styles.allDayPillText, { color: typeColor(ev.event_type) }]} numberOfLines={1}>
                  {ev.title ?? 'All-day event'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Scrollable timeline */}
      <ScrollView
        ref={scrollRef}
        style={styles.timelineScroll}
        showsVerticalScrollIndicator={false}
        onLayout={() => {
          // Scroll to 1hr before current time or 8am
          const scrollTo = Math.max(0, (Math.max(TIMELINE_START_HOUR, nowFrac - 1) - TIMELINE_START_HOUR) * HOUR_HEIGHT);
          scrollRef.current?.scrollTo({ y: scrollTo, animated: false });
        }}
      >
        <View style={{ height: totalHeight, position: 'relative', marginLeft: 52 }}>
          {/* Hour grid */}
          {Array.from({ length: totalHours + 1 }, (_, i) => i).map(i => {
            const hour = TIMELINE_START_HOUR + i;
            return (
              <View key={hour} style={[styles.hourRow, { top: i * HOUR_HEIGHT }]}>
                <Text style={styles.hourLabel}>
                  {String(hour).padStart(2, '0')}:00
                </Text>
                <View style={styles.hourLine} />
              </View>
            );
          })}

          {/* Current time indicator */}
          {showNowLine && (
            <View style={[styles.nowLine, { top: nowTop }]}>
              <View style={styles.nowDot} />
              <View style={styles.nowLineBar} />
            </View>
          )}

          {/* Event blocks */}
          {timedEvents.map(ev => {
            const start = safeDate(ev.start_time);
            if (!start) return null;
            const startFrac = start.getHours() + start.getMinutes() / 60;
            if (startFrac >= TIMELINE_END_HOUR || startFrac < TIMELINE_START_HOUR) return null;

            const end = safeDate(ev.end_time);
            const durationHrs = end
              ? (end.getTime() - start.getTime()) / 3_600_000
              : 1;
            const clamped = Math.max(0.25, Math.min(durationHrs, TIMELINE_END_HOUR - startFrac));

            const top = (startFrac - TIMELINE_START_HOUR) * HOUR_HEIGHT + 1;
            const height = Math.max(28, clamped * HOUR_HEIGHT - 4);
            const color = typeColor(ev.event_type);

            return (
              <TouchableOpacity
                key={ev.id}
                style={[
                  styles.eventBlock,
                  {
                    top,
                    height,
                    borderLeftColor: color,
                    backgroundColor: color + '22',
                  },
                ]}
                onPress={() => onEventPress(ev)}
                activeOpacity={0.75}
              >
                <Text style={[styles.eventBlockTitle, { color }]} numberOfLines={1}>
                  {ev.title ?? 'Untitled'}
                </Text>
                {height > 40 && (
                  <Text style={styles.eventBlockTime} numberOfLines={1}>
                    {start.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    {end ? ` – ${end.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}` : ''}
                  </Text>
                )}
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

// ── Event detail / reschedule modal ────────────────────────────────────────

interface EventModalProps {
  event: CalendarEvent | null;
  onClose: () => void;
  onSaved: (updated: CalendarEvent) => void;
}

function EventModal({ event, onClose, onSaved }: EventModalProps) {
  const [notes, setNotes] = useState(event?.notes ?? '');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [unlinking, setUnlinking] = useState(false);

  // Reschedule state
  const [editStart, setEditStart] = useState<Date | null>(() => safeDate(event?.start_time ?? null));
  const [editEnd, setEditEnd] = useState<Date | null>(() => safeDate(event?.end_time ?? null));
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);
  const [rescheduleSuccess, setRescheduleSuccess] = useState(false);

  React.useEffect(() => {
    setNotes(event?.notes ?? '');
    setSaveError(null);
    setSaveSuccess(false);
    setEditStart(safeDate(event?.start_time ?? null));
    setEditEnd(safeDate(event?.end_time ?? null));
    setRescheduleError(null);
    setRescheduleSuccess(false);
  }, [event?.id]);

  const adjustTime = useCallback((
    setter: React.Dispatch<React.SetStateAction<Date | null>>,
    delta: number,
  ) => {
    setter(prev => prev ? shiftMinutes(prev, delta) : null);
    setRescheduleError(null);
    setRescheduleSuccess(false);
  }, []);

  const handleReschedule = useCallback(async () => {
    if (!event || !editStart) return;

    if (editEnd && editEnd <= editStart) {
      setRescheduleError('End time must be after start time');
      return;
    }

    setRescheduling(true);
    setRescheduleError(null);
    setRescheduleSuccess(false);

    try {
      const body: Record<string, string> = { start_time: toLocalISO(editStart) };
      if (editEnd) body.end_time = toLocalISO(editEnd);

      const updated = await apiRequest<CalendarEvent>(`/api/calendar/${event.id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      setRescheduleSuccess(true);
      onSaved(updated);
    } catch (err) {
      setRescheduleError(err instanceof Error ? err.message : 'Failed to reschedule');
    } finally {
      setRescheduling(false);
    }
  }, [event, editStart, editEnd, onSaved]);

  const handleUnlinkTask = useCallback(async () => {
    if (!event) return;
    setUnlinking(true);
    try {
      await apiRequest(`/api/calendar/${event.id}/link-task`, {
        method: 'POST',
        body: JSON.stringify({ task_id: null }),
      });
      onSaved({ ...event, linked_task_id: null, linked_task_title: null });
    } catch {
      // ignore — UI still reflects previous state
    } finally {
      setUnlinking(false);
    }
  }, [event, onSaved]);

  const handleSave = useCallback(async () => {
    if (!event) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      await apiRequest(`/api/calendar/${event.id}/notes`, {
        method: 'POST',
        body: JSON.stringify({ notes }),
      });
      setSaveSuccess(true);
      onSaved({ ...event, notes });
    } catch {
      try {
        await apiRequest(`/api/calendar/${event.id}`, {
          method: 'PUT',
          body: JSON.stringify({ notes }),
        });
        setSaveSuccess(true);
        onSaved({ ...event, notes });
      } catch (err2: unknown) {
        const msg = err2 instanceof Error ? err2.message : 'Failed to save notes';
        setSaveError(msg);
      }
    } finally {
      setSaving(false);
    }
  }, [event, notes, onSaved]);

  if (!event) return null;

  const timeLabel = formatEventTime(event.start_time, event.end_time, event.all_day);
  const dotColor = typeColor(event.event_type);
  const showReschedule = !event.all_day && !!editStart;

  return (
    <Modal visible={!!event} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <SafeAreaView style={styles.modalSheet} edges={['bottom']}>
          {/* Header */}
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle} numberOfLines={2}>
              {event.title ?? 'Untitled event'}
            </Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} hitSlop={8}>
              <Text style={styles.closeBtnText}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody} keyboardShouldPersistTaps="handled">
            {/* Meta row */}
            <View style={styles.metaRow}>
              {event.event_type ? (
                <View style={[styles.typePill, { backgroundColor: dotColor + '33' }]}>
                  <Text style={[styles.typePillText, { color: dotColor }]}>{event.event_type}</Text>
                </View>
              ) : null}
            </View>

            {/* Time */}
            {timeLabel ? (
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>When</Text>
                <Text style={styles.detailValue}>{timeLabel}</Text>
              </View>
            ) : null}

            {/* ── Quick Reschedule ────────────────────────────────────── */}
            {showReschedule && (
              <View style={styles.rescheduleSection}>
                <Text style={styles.rescheduleSectionTitle}>Quick Reschedule</Text>

                {/* Start time row */}
                <View style={styles.rescheduleRow}>
                  <Text style={styles.rescheduleRowLabel}>Start</Text>
                  <View style={styles.timeAdjustRow}>
                    <TouchableOpacity
                      style={styles.timeAdjBtn}
                      onPress={() => adjustTime(setEditStart, -15)}
                    >
                      <Text style={styles.timeAdjBtnText}>−15m</Text>
                    </TouchableOpacity>
                    <Text style={styles.timeDisplay}>
                      {editStart.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </Text>
                    <TouchableOpacity
                      style={styles.timeAdjBtn}
                      onPress={() => adjustTime(setEditStart, 15)}
                    >
                      <Text style={styles.timeAdjBtnText}>+15m</Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* End time row */}
                {editEnd && (
                  <View style={styles.rescheduleRow}>
                    <Text style={styles.rescheduleRowLabel}>End</Text>
                    <View style={styles.timeAdjustRow}>
                      <TouchableOpacity
                        style={styles.timeAdjBtn}
                        onPress={() => adjustTime(setEditEnd, -15)}
                      >
                        <Text style={styles.timeAdjBtnText}>−15m</Text>
                      </TouchableOpacity>
                      <Text style={styles.timeDisplay}>
                        {editEnd.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                      </Text>
                      <TouchableOpacity
                        style={styles.timeAdjBtn}
                        onPress={() => adjustTime(setEditEnd, 15)}
                      >
                        <Text style={styles.timeAdjBtnText}>+15m</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                )}

                {rescheduleSuccess && (
                  <Text style={styles.successText}>Rescheduled!</Text>
                )}
                {rescheduleError && (
                  <Text style={styles.errorText}>{rescheduleError}</Text>
                )}

                <TouchableOpacity
                  style={[styles.rescheduleBtn, rescheduling && styles.saveBtnDisabled]}
                  onPress={handleReschedule}
                  disabled={rescheduling}
                >
                  {rescheduling ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <Text style={styles.rescheduleBtnText}>Save Time</Text>
                  )}
                </TouchableOpacity>
              </View>
            )}

            {/* Description */}
            {event.description ? (
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Description</Text>
                <Text style={styles.detailValue}>{event.description}</Text>
              </View>
            ) : null}

            {/* Linked task */}
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Linked Task</Text>
              {event.linked_task_id ? (
                <View style={styles.linkedTaskRow}>
                  <Text style={styles.linkedTaskTitle} numberOfLines={1}>
                    {event.linked_task_title ?? `Task #${event.linked_task_id}`}
                  </Text>
                  <TouchableOpacity
                    style={styles.unlinkBtn}
                    onPress={handleUnlinkTask}
                    disabled={unlinking}
                  >
                    <Text style={styles.unlinkBtnText}>{unlinking ? '…' : 'Unlink'}</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <Text style={styles.detailValue}>None</Text>
              )}
            </View>

            {/* Notes editor */}
            <View style={styles.notesSection}>
              <Text style={styles.detailLabel}>Notes</Text>
              <TextInput
                style={styles.notesInput}
                value={notes}
                onChangeText={val => {
                  setNotes(val);
                  setSaveError(null);
                  setSaveSuccess(false);
                }}
                placeholder="Add your notes here…"
                placeholderTextColor="#4b5563"
                multiline
                textAlignVertical="top"
              />
            </View>

            {saveSuccess ? (
              <Text style={styles.successText}>Notes saved!</Text>
            ) : null}
            {saveError ? (
              <Text style={styles.errorText}>{saveError}</Text>
            ) : null}

            <TouchableOpacity
              style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={saving}
            >
              {saving ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Text style={styles.saveBtnText}>Save Notes</Text>
              )}
            </TouchableOpacity>
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

// ── Main screen ────────────────────────────────────────────────────────────

export default function CalendarScreen() {
  const { data, loading, error, refetch } = useApi<CalendarResponse>('/api/calendar');
  const [filter, setFilter] = useState<FilterKey>('next7');
  const [selectedDay, setSelectedDay] = useState<Date>(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [overrides, setOverrides] = useState<Record<number, Partial<CalendarEvent>>>({});

  const rawEvents: CalendarEvent[] = data?.events ?? [];

  // Merge local overrides (notes, reschedule) into events
  const mergedEvents = useMemo(
    () => rawEvents.map(ev => overrides[ev.id] ? { ...ev, ...overrides[ev.id] } : ev),
    [rawEvents, overrides],
  );

  const filteredEvents = useMemo(
    () => filterEvents(mergedEvents, filter, selectedDay),
    [mergedEvents, filter, selectedDay],
  );

  const handleEventPress = useCallback((ev: CalendarEvent) => setSelectedEvent(ev), []);
  const handleModalClose = useCallback(() => setSelectedEvent(null), []);

  const handleSaved = useCallback((updated: CalendarEvent) => {
    setOverrides(prev => ({ ...prev, [updated.id]: updated }));
    setSelectedEvent(updated);
  }, []);

  if (loading && rawEvents.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      </SafeAreaView>
    );
  }

  if (error && rawEvents.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <ErrorState error={error} onRetry={refetch} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Segmented filter */}
      <View style={styles.filterRow}>
        {FILTERS.map(f => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterBtn, filter === f.key && styles.filterBtnActive]}
            onPress={() => setFilter(f.key)}
          >
            <Text style={[styles.filterBtnText, filter === f.key && styles.filterBtnTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {filter === 'day' ? (
        <DayTimeline
          events={filteredEvents}
          day={selectedDay}
          onDayChange={d => {
            const clean = new Date(d);
            clean.setHours(0, 0, 0, 0);
            setSelectedDay(clean);
          }}
          onEventPress={handleEventPress}
        />
      ) : (
        <FlatList
          data={filteredEvents}
          keyExtractor={item => String(item.id)}
          renderItem={({ item }) => <EventItem item={item} onPress={handleEventPress} />}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={refetch} tintColor="#6366f1" />
          }
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.emptyText}>No events for this period.</Text>
            </View>
          }
        />
      )}

      <EventModal
        event={selectedEvent}
        onClose={handleModalClose}
        onSaved={handleSaved}
      />
    </SafeAreaView>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },

  // Filter bar
  filterRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 4,
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 3,
    gap: 2,
  },
  filterBtn: {
    flex: 1,
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: 'center',
  },
  filterBtnActive: {
    backgroundColor: '#6366f1',
  },
  filterBtnText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#6b7280',
  },
  filterBtnTextActive: {
    color: '#f9fafb',
    fontWeight: '600',
  },

  // List
  list: { padding: 16, gap: 10, flexGrow: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 48 },

  // Event card
  eventCard: {
    flexDirection: 'row',
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 14,
    gap: 12,
    alignItems: 'flex-start',
  },
  eventDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#6366f1',
    marginTop: 4,
  },
  eventBody: { flex: 1 },
  eventTitle: { fontSize: 15, fontWeight: '600', color: '#f9fafb', marginBottom: 4 },
  eventTime: { fontSize: 12, color: '#9ca3af', marginBottom: 6 },
  eventMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  typePill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
  },
  typePillText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  notePreview: { fontSize: 12, color: '#6b7280', marginTop: 6, fontStyle: 'italic' },

  // Feedback
  errorText: { color: '#f87171', fontSize: 13, textAlign: 'center', marginBottom: 8 },
  successText: { color: '#10b981', fontSize: 13, marginBottom: 8, textAlign: 'center' },
  emptyText: { color: '#6b7280', fontSize: 14 },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#1f2937',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#374151',
    gap: 12,
  },
  modalTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '700',
    color: '#f9fafb',
  },
  closeBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#374151',
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeBtnText: { color: '#9ca3af', fontSize: 13, fontWeight: '600' },

  modalBody: { padding: 20 },
  metaRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  detailRow: { marginBottom: 14 },
  detailLabel: {
    fontSize: 11,
    color: '#6b7280',
    fontWeight: '600',
    textTransform: 'uppercase',
    marginBottom: 4,
    letterSpacing: 0.5,
  },
  detailValue: { fontSize: 14, color: '#d1d5db' },

  notesSection: { marginBottom: 12 },
  notesInput: {
    backgroundColor: '#111827',
    borderRadius: 8,
    padding: 12,
    color: '#f9fafb',
    fontSize: 14,
    minHeight: 110,
    marginTop: 6,
    borderWidth: 1,
    borderColor: '#374151',
  },

  saveBtn: {
    backgroundColor: '#6366f1',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 20,
  },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },

  // Task link pill (event card)
  taskLinkPill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
    backgroundColor: '#1e1b4b',
    borderWidth: 1,
    borderColor: '#4338ca',
    maxWidth: 160,
  },
  taskLinkPillText: { fontSize: 11, fontWeight: '600', color: '#818cf8' },

  // Linked task row (modal)
  linkedTaskRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 2,
  },
  linkedTaskTitle: { flex: 1, fontSize: 14, color: '#818cf8', fontWeight: '500' },
  unlinkBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: '#374151',
  },
  unlinkBtnText: { fontSize: 12, fontWeight: '600', color: '#9ca3af' },

  // ── Day Timeline ──────────────────────────────────────────────────────────
  timelineWrapper: { flex: 1 },

  dayNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1f2937',
  },
  dayNavBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#1f2937',
    borderRadius: 8,
  },
  dayNavArrow: { fontSize: 22, color: '#9ca3af', lineHeight: 26 },
  dayNavLabel: { fontSize: 14, fontWeight: '600', color: '#f9fafb' },

  allDayStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: '#1f2937',
    gap: 8,
  },
  allDayLabel: { fontSize: 10, color: '#6b7280', fontWeight: '600', width: 40 },
  allDayEvents: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  allDayPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  allDayPillText: { fontSize: 11, fontWeight: '600' },

  timelineScroll: { flex: 1 },

  hourRow: {
    position: 'absolute',
    left: -52,
    right: 0,
    flexDirection: 'row',
    alignItems: 'flex-start',
    height: HOUR_HEIGHT,
  },
  hourLabel: {
    width: 44,
    fontSize: 10,
    color: '#4b5563',
    textAlign: 'right',
    paddingRight: 8,
    lineHeight: 14,
  },
  hourLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#1f2937',
    marginTop: 6,
  },

  nowLine: {
    position: 'absolute',
    left: 0,
    right: 8,
    flexDirection: 'row',
    alignItems: 'center',
    zIndex: 10,
  },
  nowDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#ef4444',
    marginLeft: -4,
  },
  nowLineBar: {
    flex: 1,
    height: 1.5,
    backgroundColor: '#ef4444',
  },

  eventBlock: {
    position: 'absolute',
    left: 4,
    right: 8,
    borderLeftWidth: 3,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
    overflow: 'hidden',
  },
  eventBlockTitle: {
    fontSize: 11,
    fontWeight: '700',
    lineHeight: 15,
  },
  eventBlockTime: {
    fontSize: 10,
    color: '#9ca3af',
    lineHeight: 14,
  },

  // ── Reschedule section ────────────────────────────────────────────────────
  rescheduleSection: {
    backgroundColor: '#111827',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#374151',
  },
  rescheduleSectionTitle: {
    fontSize: 11,
    color: '#6b7280',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  rescheduleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  rescheduleRowLabel: {
    width: 40,
    fontSize: 12,
    color: '#9ca3af',
    fontWeight: '600',
  },
  timeAdjustRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  timeAdjBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#1f2937',
    borderWidth: 1,
    borderColor: '#374151',
  },
  timeAdjBtnText: { fontSize: 12, color: '#d1d5db', fontWeight: '600' },
  timeDisplay: {
    flex: 1,
    textAlign: 'center',
    fontSize: 15,
    fontWeight: '700',
    color: '#f9fafb',
  },
  rescheduleBtn: {
    backgroundColor: '#059669',
    borderRadius: 8,
    paddingVertical: 11,
    alignItems: 'center',
    marginTop: 4,
  },
  rescheduleBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
});
