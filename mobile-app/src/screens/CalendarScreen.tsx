import React, { useCallback, useState } from 'react';
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

type FilterKey = 'today' | 'next7' | 'next30';

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'next7', label: 'Next 7 Days' },
  { key: 'next30', label: 'Next 30 Days' },
];

function filterEvents(events: CalendarEvent[], filter: FilterKey): CalendarEvent[] {
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
    // next30
    const cutoff = new Date(todayStart.getTime() + 30 * 86400_000);
    return start >= todayStart && start < cutoff;
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

// ── Event card ─────────────────────────────────────────────────────────────

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

// ── Event detail modal ─────────────────────────────────────────────────────

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

  // Reset local state when event changes
  React.useEffect(() => {
    setNotes(event?.notes ?? '');
    setSaveError(null);
    setSaveSuccess(false);
  }, [event?.id]);

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

    // Try POST /api/calendar/{id}/notes first, fallback to PUT /api/calendar/{id}
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

            {/* Feedback */}
            {saveSuccess ? (
              <Text style={styles.successText}>Notes saved!</Text>
            ) : null}
            {saveError ? (
              <Text style={styles.errorText}>{saveError}</Text>
            ) : null}

            {/* Save button */}
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
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  // Local overrides for optimistic notes updates
  const [notesOverrides, setNotesOverrides] = useState<Record<number, string>>({});

  const rawEvents: CalendarEvent[] = data?.events ?? [];

  // Merge notes overrides into events
  const mergedEvents = rawEvents.map(ev =>
    notesOverrides[ev.id] !== undefined ? { ...ev, notes: notesOverrides[ev.id] } : ev,
  );

  const filteredEvents = filterEvents(mergedEvents, filter);

  const handleEventPress = useCallback((ev: CalendarEvent) => {
    setSelectedEvent(ev);
  }, []);

  const handleModalClose = useCallback(() => {
    setSelectedEvent(null);
  }, []);

  const handleSaved = useCallback((updated: CalendarEvent) => {
    setNotesOverrides(prev => ({ ...prev, [updated.id]: updated.notes ?? '' }));
    // Update selected event to reflect new notes without closing
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
    maxHeight: '85%',
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
  detailLabel: { fontSize: 11, color: '#6b7280', fontWeight: '600', textTransform: 'uppercase', marginBottom: 4, letterSpacing: 0.5 },
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
});
