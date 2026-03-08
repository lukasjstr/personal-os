import { Ionicons } from '@expo/vector-icons';
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ErrorState } from '../components/ErrorState';
import { useApi } from '../hooks/useApi';
import { apiRequest } from '../lib/apiClient';

// ── Types ───────────────────────────────────────────────────────────────────

interface AutopilotNotification {
  id: number;
  notification_type: string;
  title: string;
  body: string | null;
  status: string;
  snoozed_until: string | null;
  source: string | null;
  linked_task_id: number | null;
  created_at: string;
}

interface NotificationsResponse {
  notifications: AutopilotNotification[];
  pending_count: number;
  latest: AutopilotNotification | null;
}

interface ActionQueueItem {
  id: number;
  item_type: string;
  title: string;
  description: string | null;
  reason: string | null;
  state: string;
  linked_task_id: number | null;
  snoozed_until: string | null;
  created_at: string;
}

interface ActionQueueResponse {
  items: ActionQueueItem[];
  counts: Record<string, number>;
  total_active: number;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

type FilterTab = 'pending' | 'snoozed' | 'all';

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function typeLabel(raw: string): string {
  return raw.replace(/_/g, ' ');
}

// ── Sub-components ───────────────────────────────────────────────────────────

function TypeBadge({ label, color }: { label: string; color: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: color + '33', borderColor: color + '66' }]}>
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

interface NotificationCardProps {
  item: AutopilotNotification;
  onAcknowledge: (id: number) => void;
  onSnooze: (id: number) => void;
  busy: boolean;
}

function NotificationCard({ item, onAcknowledge, onSnooze, busy }: NotificationCardProps) {
  const isPending = item.status === 'pending';
  const isSnoozed = item.status === 'snoozed';

  const badgeColor =
    item.notification_type === 'warning'
      ? '#f59e0b'
      : item.notification_type === 'suggestion'
        ? '#6366f1'
        : item.notification_type === 'reminder'
          ? '#10b981'
          : '#60a5fa';

  return (
    <View style={[styles.card, !isPending && styles.cardDimmed]}>
      <View style={styles.cardHeader}>
        <TypeBadge label={typeLabel(item.notification_type)} color={badgeColor} />
        <Text style={styles.cardTime}>{relativeTime(item.created_at)}</Text>
      </View>
      <Text style={styles.cardTitle}>{item.title}</Text>
      {item.body ? <Text style={styles.cardBody}>{item.body}</Text> : null}
      {isSnoozed && item.snoozed_until ? (
        <Text style={styles.snoozeLabel}>
          Snoozed until {new Date(item.snoozed_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Text>
      ) : null}
      {(isPending || isSnoozed) && (
        <View style={styles.cardActions}>
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnPrimary]}
            onPress={() => onAcknowledge(item.id)}
            disabled={busy}
            activeOpacity={0.75}
          >
            <Ionicons name="checkmark" size={14} color="#f9fafb" />
            <Text style={styles.actionBtnText}>Dismiss</Text>
          </TouchableOpacity>
          {isPending && (
            <TouchableOpacity
              style={[styles.actionBtn, styles.actionBtnSecondary]}
              onPress={() => onSnooze(item.id)}
              disabled={busy}
              activeOpacity={0.75}
            >
              <Ionicons name="time-outline" size={14} color="#9ca3af" />
              <Text style={styles.actionBtnSecondaryText}>Snooze 1h</Text>
            </TouchableOpacity>
          )}
        </View>
      )}
    </View>
  );
}

interface QueueCardProps {
  item: ActionQueueItem;
  onAccept: (id: number) => void;
  onSnooze: (id: number) => void;
  onComplete: (id: number) => void;
  busy: boolean;
}

function QueueCard({ item, onAccept, onSnooze, onComplete, busy }: QueueCardProps) {
  const isSuggested = item.state === 'suggested';
  const isAccepted = item.state === 'accepted';
  const isSnoozed = item.state === 'snoozed';

  return (
    <View style={[styles.card, styles.cardQueue]}>
      <View style={styles.cardHeader}>
        <TypeBadge label={typeLabel(item.item_type)} color="#a78bfa" />
        <View style={[styles.statePill, { backgroundColor: STATE_COLORS[item.state] ?? '#374151' }]}>
          <Text style={styles.stateText}>{item.state}</Text>
        </View>
      </View>
      <Text style={styles.cardTitle}>{item.title}</Text>
      {item.description ? <Text style={styles.cardBody}>{item.description}</Text> : null}
      {item.reason ? (
        <Text style={styles.reasonText}>Reason: {item.reason}</Text>
      ) : null}
      {isSnoozed && item.snoozed_until ? (
        <Text style={styles.snoozeLabel}>
          Snoozed until {new Date(item.snoozed_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Text>
      ) : null}
      <View style={styles.cardActions}>
        {isSuggested && (
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnAccept]}
            onPress={() => onAccept(item.id)}
            disabled={busy}
            activeOpacity={0.75}
          >
            <Ionicons name="checkmark-circle-outline" size={14} color="#4ade80" />
            <Text style={[styles.actionBtnText, { color: '#4ade80' }]}>Approve</Text>
          </TouchableOpacity>
        )}
        {isAccepted && (
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnAccept]}
            onPress={() => onComplete(item.id)}
            disabled={busy}
            activeOpacity={0.75}
          >
            <Ionicons name="checkmark-done-outline" size={14} color="#4ade80" />
            <Text style={[styles.actionBtnText, { color: '#4ade80' }]}>Complete</Text>
          </TouchableOpacity>
        )}
        {(isSuggested || isAccepted) && (
          <TouchableOpacity
            style={[styles.actionBtn, styles.actionBtnSecondary]}
            onPress={() => onSnooze(item.id)}
            disabled={busy}
            activeOpacity={0.75}
          >
            <Ionicons name="time-outline" size={14} color="#9ca3af" />
            <Text style={styles.actionBtnSecondaryText}>Snooze</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const STATE_COLORS: Record<string, string> = {
  planned: '#1e3a5f',
  suggested: '#3b2f6b',
  accepted: '#14532d',
  snoozed: '#44403c',
  completed: '#1f2937',
};

// ── Main Screen ──────────────────────────────────────────────────────────────

export default function NotificationsScreen() {
  const [filter, setFilter] = useState<FilterTab>('pending');
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());

  const notifStatus = filter === 'all' ? 'all' : filter;
  const {
    data: notifData,
    loading: notifLoading,
    error: notifError,
    refetch: refetchNotifs,
  } = useApi<NotificationsResponse>(`/api/notifications?status=${notifStatus}&limit=50`);

  const {
    data: queueData,
    loading: queueLoading,
    error: queueError,
    refetch: refetchQueue,
  } = useApi<ActionQueueResponse>(
    filter === 'snoozed'
      ? '/api/autopilot/action-queue?state=snoozed'
      : filter === 'all'
        ? '/api/autopilot/action-queue?state=all'
        : '/api/autopilot/action-queue',
  );

  const refetchAll = useCallback(() => {
    refetchNotifs();
    refetchQueue();
  }, [refetchNotifs, refetchQueue]);

  // ── Mutation helpers ──────────────────────────────────────────────────────

  async function withBusy(key: string, fn: () => Promise<void>) {
    setBusyIds(prev => new Set(prev).add(key));
    try {
      await fn();
    } catch {
      // silent — refetch will reflect real state
    } finally {
      setBusyIds(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      refetchAll();
    }
  }

  const acknowledgeNotif = (id: number) =>
    withBusy(`notif-${id}`, () =>
      apiRequest(`/api/notifications/${id}/acknowledge`, { method: 'POST' }),
    );

  const snoozeNotif = (id: number) =>
    withBusy(`notif-snooze-${id}`, () =>
      apiRequest(`/api/notifications/${id}/snooze`, {
        method: 'POST',
        body: JSON.stringify({ minutes: 60 }),
      }),
    );

  const updateQueueItem = (id: number, state: string) =>
    withBusy(`queue-${id}`, () =>
      apiRequest(`/api/autopilot/action-queue/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ state }),
      }),
    );

  // ── Render helpers ────────────────────────────────────────────────────────

  const notifications = notifData?.notifications ?? [];
  const queueItems = queueData?.items ?? [];
  const pendingCount = notifData?.pending_count ?? 0;
  const activeQueueCount = queueData?.total_active ?? 0;

  const loading = notifLoading || queueLoading;
  // Full error only when BOTH fetches fail
  const bothFailed = !!(notifError && queueError);

  // Section list data: flatten notifications + queue items with section headers
  type SectionRow =
    | { kind: 'section-header'; label: string; count: number }
    | { kind: 'notif'; item: AutopilotNotification }
    | { kind: 'queue'; item: ActionQueueItem }
    | { kind: 'empty'; label: string };

  const rows: SectionRow[] = [];

  // Notifications section — show unless still loading with no data yet
  if (!notifLoading || notifData) {
    rows.push({ kind: 'section-header', label: 'Notifications', count: pendingCount });
    if (notifError && notifications.length === 0) {
      rows.push({ kind: 'empty', label: 'Could not load notifications' });
    } else if (notifications.length === 0) {
      rows.push({ kind: 'empty', label: 'No notifications' });
    } else {
      notifications.forEach(n => rows.push({ kind: 'notif', item: n }));
    }
  }

  // Action queue section — show unless still loading with no data yet
  if (!queueLoading || queueData) {
    rows.push({ kind: 'section-header', label: 'Action Queue', count: activeQueueCount });
    if (queueError && queueItems.length === 0) {
      rows.push({ kind: 'empty', label: 'Could not load action queue' });
    } else if (queueItems.length === 0) {
      rows.push({ kind: 'empty', label: 'No pending approvals' });
    } else {
      queueItems.forEach(q => rows.push({ kind: 'queue', item: q }));
    }
  }

  if (loading && rows.length === 0) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#6366f1" style={styles.loader} />
      </SafeAreaView>
    );
  }

  // Full error state only when both failed and nothing to show
  if (bothFailed && rows.length === 0) {
    return (
      <SafeAreaView style={styles.container}>
        <ErrorState error={notifError!} onRetry={refetchAll} />
      </SafeAreaView>
    );
  }

  const renderRow = ({ item: row }: { item: SectionRow }) => {
    if (row.kind === 'section-header') {
      return (
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{row.label}</Text>
          {row.count > 0 && (
            <View style={styles.countBubble}>
              <Text style={styles.countText}>{row.count}</Text>
            </View>
          )}
        </View>
      );
    }
    if (row.kind === 'empty') {
      return (
        <View style={styles.emptyRow}>
          <Text style={styles.emptyText}>{row.label}</Text>
        </View>
      );
    }
    if (row.kind === 'notif') {
      return (
        <NotificationCard
          item={row.item}
          onAcknowledge={acknowledgeNotif}
          onSnooze={snoozeNotif}
          busy={busyIds.has(`notif-${row.item.id}`) || busyIds.has(`notif-snooze-${row.item.id}`)}
        />
      );
    }
    // queue
    return (
      <QueueCard
        item={row.item}
        onAccept={id => updateQueueItem(id, 'accepted')}
        onSnooze={id => updateQueueItem(id, 'snoozed')}
        onComplete={id => updateQueueItem(id, 'completed')}
        busy={busyIds.has(`queue-${row.item.id}`)}
      />
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Filter tabs */}
      <View style={styles.filterRow}>
        {(['pending', 'snoozed', 'all'] as FilterTab[]).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[styles.filterTab, filter === tab && styles.filterTabActive]}
            onPress={() => setFilter(tab)}
            activeOpacity={0.75}
          >
            <Text style={[styles.filterTabText, filter === tab && styles.filterTabTextActive]}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {notifError && !queueError ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText} numberOfLines={1}>
            Notifications unavailable
          </Text>
          <TouchableOpacity onPress={refetchNotifs} activeOpacity={0.75}>
            <Text style={styles.errorBannerRetry}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : queueError && !notifError ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText} numberOfLines={1}>
            Action queue unavailable
          </Text>
          <TouchableOpacity onPress={refetchQueue} activeOpacity={0.75}>
            <Text style={styles.errorBannerRetry}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : bothFailed ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText} numberOfLines={1}>
            Load error — pull to retry
          </Text>
          <TouchableOpacity onPress={refetchAll} activeOpacity={0.75}>
            <Text style={styles.errorBannerRetry}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      <FlatList
        data={rows}
        keyExtractor={(row, i) => {
          if (row.kind === 'notif') return `notif-${row.item.id}`;
          if (row.kind === 'queue') return `queue-${row.item.id}`;
          return `${row.kind}-${i}`;
        }}
        renderItem={renderRow}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={refetchAll}
            tintColor="#6366f1"
            colors={['#6366f1']}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyCenter}>
            <Ionicons name="notifications-off-outline" size={40} color="#4b5563" />
            <Text style={styles.emptyCenterText}>Nothing here</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111827',
  },
  loader: {
    marginTop: 60,
  },

  // Filter tabs
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 8,
  },
  filterTab: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#1f2937',
    borderWidth: 1,
    borderColor: '#374151',
  },
  filterTabActive: {
    backgroundColor: '#4338ca',
    borderColor: '#6366f1',
  },
  filterTabText: {
    fontSize: 13,
    color: '#9ca3af',
    fontWeight: '500',
  },
  filterTabTextActive: {
    color: '#f9fafb',
  },

  // Error banner
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1c1917',
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderLeftWidth: 3,
    borderLeftColor: '#f87171',
    gap: 8,
  },
  errorBannerText: {
    flex: 1,
    fontSize: 12,
    color: '#fca5a5',
  },
  errorBannerRetry: {
    fontSize: 12,
    color: '#d1d5db',
    fontWeight: '600',
  },

  // List
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 16,
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  countBubble: {
    backgroundColor: '#6366f1',
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  countText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#f9fafb',
  },
  emptyRow: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 13,
    color: '#6b7280',
  },
  emptyCenter: {
    alignItems: 'center',
    paddingTop: 48,
    gap: 12,
  },
  emptyCenterText: {
    fontSize: 15,
    color: '#4b5563',
  },

  // Cards
  card: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#374151',
  },
  cardDimmed: {
    opacity: 0.65,
  },
  cardQueue: {
    borderColor: '#3b2f6b',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  cardTime: {
    fontSize: 11,
    color: '#6b7280',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#f9fafb',
    marginBottom: 4,
  },
  cardBody: {
    fontSize: 13,
    color: '#9ca3af',
    lineHeight: 18,
    marginBottom: 6,
  },
  reasonText: {
    fontSize: 12,
    color: '#6b7280',
    fontStyle: 'italic',
    marginBottom: 4,
  },
  snoozeLabel: {
    fontSize: 12,
    color: '#f59e0b',
    marginBottom: 6,
  },

  // Badges
  badge: {
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  statePill: {
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  stateText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#d1d5db',
    textTransform: 'capitalize',
  },

  // Card actions
  cardActions: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  actionBtnPrimary: {
    backgroundColor: '#374151',
  },
  actionBtnAccept: {
    backgroundColor: '#14532d44',
    borderWidth: 1,
    borderColor: '#4ade8044',
  },
  actionBtnSecondary: {
    backgroundColor: '#1f2937',
    borderWidth: 1,
    borderColor: '#374151',
  },
  actionBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#f9fafb',
  },
  actionBtnSecondaryText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#9ca3af',
  },
});
