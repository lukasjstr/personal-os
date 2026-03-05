import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApi } from '../hooks/useApi';
import { apiRequest } from '../lib/apiClient';
import type { TabParamList } from '../navigation/TabNavigator';
import { ErrorState } from '../components/ErrorState';

interface Task {
  id: number;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  category: string | null;
  due_date: string | null;
  is_overdue: boolean;
  parent_task_id: number | null;
  blocked_by_task_id: number | null;
  blocker_title: string | null;
  is_unblocked: boolean;
  subtask_count: number;
  objective_title: string | null;
  linked_event_id: number | null;
  linked_event_title: string | null;
  linked_event_start: string | null;
}

interface TasksResponse {
  tasks: Task[];
}

interface TaskSuggestion {
  id: number;
  objective_id: number;
  objective_title: string | null;
  title: string;
  priority: number;
  reason: string | null;
  status: string;
}

interface SuggestionsResponse {
  suggestions: TaskSuggestion[];
  pending_count: number;
}

type FilterKey = 'all' | 'unblocked' | 'blocked' | 'overdue';

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  todo: { bg: '#374151', text: '#d1d5db' },
  in_progress: { bg: '#1e3a5f', text: '#60a5fa' },
  done: { bg: '#14532d', text: '#4ade80' },
  cancelled: { bg: '#1f2937', text: '#6b7280' },
};

function isBlocked(task: Task, allTasks: Task[]): boolean {
  // Prefer server-computed field; fall back to client-side derivation for
  // tasks that pre-date the computed field (backward-compatible).
  if (task.is_unblocked !== undefined) return !task.is_unblocked;
  if (!task.blocked_by_task_id) return false;
  const blocker = allTasks.find(t => t.id === task.blocked_by_task_id);
  return blocker ? blocker.status !== 'done' : false;
}

function StatusChip({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? STATUS_COLORS.todo;
  return (
    <View style={[styles.chip, { backgroundColor: colors.bg }]}>
      <Text style={[styles.chipText, { color: colors.text }]}>
        {status.replace('_', ' ')}
      </Text>
    </View>
  );
}

function BlockedBadge({ blockerTitle }: { blockerTitle?: string | null }) {
  const label = blockerTitle ? `⊘ ${blockerTitle}` : 'Blocked';
  return (
    <View style={styles.blockedBadge}>
      <Text style={styles.blockedBadgeText} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

function SubtaskCountBadge({ count }: { count: number }) {
  return (
    <View style={styles.subtaskCountBadge}>
      <Text style={styles.subtaskCountText}>{count} sub</Text>
    </View>
  );
}

function CalendarBadge({ eventTitle }: { eventTitle?: string | null }) {
  const label = eventTitle ? eventTitle : 'Scheduled';
  return (
    <View style={styles.calendarBadge}>
      <Text style={styles.calendarBadgeText} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

function TaskItem({
  item,
  isSubtask,
  blocked,
}: {
  item: Task;
  isSubtask: boolean;
  blocked: boolean;
}) {
  const subtaskCount = item.subtask_count ?? 0;
  return (
    <View style={[styles.taskCard, isSubtask && styles.subtaskCard]}>
      {isSubtask && <View style={styles.subtaskIndentLine} />}
      <View style={styles.taskInner}>
        <View style={styles.taskHeader}>
          <Text
            style={[styles.taskTitle, isSubtask && styles.subtaskTitle]}
            numberOfLines={2}
          >
            {item.title}
          </Text>
          <View style={styles.badgeRow}>
            {blocked && <BlockedBadge blockerTitle={item.blocker_title} />}
            {!isSubtask && subtaskCount > 0 && (
              <SubtaskCountBadge count={subtaskCount} />
            )}
            {item.linked_event_id ? (
              <CalendarBadge eventTitle={item.linked_event_title} />
            ) : null}
            <StatusChip status={item.status} />
          </View>
        </View>
        <View style={styles.taskMeta}>
          {item.category ? (
            <Text style={styles.metaText}>{item.category}</Text>
          ) : null}
          {item.due_date ? (
            <Text
              style={[
                styles.metaText,
                (item.is_overdue ?? false) && styles.overdueText,
              ]}
            >
              {item.is_overdue ? 'Overdue · ' : ''}
              {item.due_date}
            </Text>
          ) : null}
        </View>
      </View>
    </View>
  );
}

function ObjectiveBadge({ title }: { title: string }) {
  return (
    <View style={styles.objectiveBadge}>
      <Text style={styles.objectiveBadgeText} numberOfLines={1}>
        {title}
      </Text>
    </View>
  );
}

function NextUnblockedBanner({ task }: { task: Task }) {
  return (
    <View style={styles.nextBanner}>
      <Text style={styles.nextLabel}>Next unblocked</Text>
      <Text style={styles.nextTitle} numberOfLines={1}>
        {task.title}
      </Text>
      {task.objective_title ? (
        <ObjectiveBadge title={task.objective_title} />
      ) : null}
    </View>
  );
}

function TaskDoNowBanner({ task }: { task: Task }) {
  return (
    <View style={styles.doNowBanner}>
      <Text style={styles.doNowLabel}>Do this now</Text>
      <Text style={styles.doNowTitle} numberOfLines={2}>
        {task.title}
      </Text>
      {task.objective_title ? (
        <ObjectiveBadge title={task.objective_title} />
      ) : task.category ? (
        <Text style={styles.doNowMeta}>{task.category}</Text>
      ) : null}
    </View>
  );
}

type ListRow =
  | { type: 'header'; group: string }
  | { type: 'task'; task: Task; isSubtask: boolean; blocked: boolean };

function PendingSuggestionsSection({
  onAccepted,
}: {
  onAccepted: () => void;
}) {
  const { data, loading, refetch } = useApi<SuggestionsResponse>('/api/task-suggestions?status=pending');
  const [actioning, setActioning] = useState<number | null>(null);

  const suggestions = data?.suggestions ?? [];

  const handleAccept = useCallback(
    async (id: number) => {
      setActioning(id);
      try {
        await apiRequest(`/api/task-suggestions/${id}/accept`, { method: 'POST' });
        refetch();
        onAccepted();
      } catch {
        // silently ignore; list will refresh
      } finally {
        setActioning(null);
      }
    },
    [refetch, onAccepted],
  );

  const handleReject = useCallback(
    async (id: number) => {
      setActioning(id);
      try {
        await apiRequest(`/api/task-suggestions/${id}/reject`, { method: 'POST' });
        refetch();
      } catch {
        // silently ignore
      } finally {
        setActioning(null);
      }
    },
    [refetch],
  );

  if (loading || suggestions.length === 0) return null;

  return (
    <View style={suggStyles.container}>
      <Text style={suggStyles.header}>
        Suggested Tasks — Review &amp; Accept
      </Text>
      {suggestions.map(s => (
        <View key={s.id} style={suggStyles.card}>
          <View style={suggStyles.cardBody}>
            {s.objective_title ? (
              <Text style={suggStyles.objectiveLabel} numberOfLines={1}>
                {s.objective_title}
              </Text>
            ) : null}
            <Text style={suggStyles.title} numberOfLines={2}>
              {s.title}
            </Text>
            {s.reason ? (
              <Text style={suggStyles.reason} numberOfLines={2}>
                {s.reason}
              </Text>
            ) : null}
          </View>
          <View style={suggStyles.actions}>
            <TouchableOpacity
              style={[suggStyles.btn, suggStyles.btnReject]}
              onPress={() => handleReject(s.id)}
              disabled={actioning === s.id}
            >
              <Text style={suggStyles.btnTextReject}>Reject</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[suggStyles.btn, suggStyles.btnAccept]}
              onPress={() => handleAccept(s.id)}
              disabled={actioning === s.id}
            >
              {actioning === s.id ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={suggStyles.btnTextAccept}>Accept</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      ))}
    </View>
  );
}

export default function TasksScreen() {
  const route = useRoute<RouteProp<TabParamList, 'Tasks'>>();
  const highlightTaskId = route.params?.highlightTaskId ?? null;
  const { data, loading, error, refetch } = useApi<TasksResponse>('/api/tasks');
  const [filter, setFilter] = useState<FilterKey>('all');
  const handleSuggestionAccepted = useCallback(() => refetch(), [refetch]);

  const allTasks: Task[] = data?.tasks ?? [];
  const highlightTask = highlightTaskId != null
    ? (allTasks.find(t => t.id === highlightTaskId) ?? null)
    : null;

  const filteredTasks = useMemo(() => {
    switch (filter) {
      case 'unblocked':
        return allTasks.filter(
          t => t.status !== 'done' && !isBlocked(t, allTasks),
        );
      case 'blocked':
        return allTasks.filter(t => isBlocked(t, allTasks));
      case 'overdue':
        return allTasks.filter(t => t.is_overdue ?? false);
      default:
        return allTasks;
    }
  }, [allTasks, filter]);

  const nextUnblocked = useMemo(() => {
    const open = allTasks.filter(
      t => t.status !== 'done' && t.status !== 'cancelled' && !isBlocked(t, allTasks),
    );
    if (open.length === 0) return null;
    // prefer highest priority (lower number = higher priority)
    return open.reduce((best, t) => (t.priority < best.priority ? t : best));
  }, [allTasks]);

  const listRows = useMemo((): ListRow[] => {
    const groups = new Map<string, Task[]>();
    for (const task of filteredTasks) {
      const key = task.objective_title ?? 'General';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(task);
    }

    const rows: ListRow[] = [];
    for (const [group, tasks] of groups) {
      rows.push({ type: 'header', group });
      // put parent tasks first, then subtasks under their parent
      const parents = tasks.filter(t => !t.parent_task_id);
      const subtasks = tasks.filter(t => !!t.parent_task_id);
      for (const parent of parents) {
        rows.push({
          type: 'task',
          task: parent,
          isSubtask: false,
          blocked: isBlocked(parent, allTasks),
        });
        for (const sub of subtasks.filter(
          s => s.parent_task_id === parent.id,
        )) {
          rows.push({
            type: 'task',
            task: sub,
            isSubtask: true,
            blocked: isBlocked(sub, allTasks),
          });
        }
      }
      // orphan subtasks (parent not in this filtered view)
      const renderedSubIds = new Set(
        subtasks
          .filter(s => parents.some(p => p.id === s.parent_task_id))
          .map(s => s.id),
      );
      for (const sub of subtasks.filter(s => !renderedSubIds.has(s.id))) {
        rows.push({
          type: 'task',
          task: sub,
          isSubtask: true,
          blocked: isBlocked(sub, allTasks),
        });
      }
    }
    return rows;
  }, [filteredTasks, allTasks]);

  if (loading && allTasks.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      </SafeAreaView>
    );
  }

  if (error && allTasks.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <ErrorState error={error} onRetry={refetch} />
      </SafeAreaView>
    );
  }

  const FILTERS: { key: FilterKey; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'unblocked', label: 'Unblocked' },
    { key: 'blocked', label: 'Blocked' },
    { key: 'overdue', label: 'Overdue' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Filter bar */}
      <View style={styles.filterBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {FILTERS.map(f => (
            <TouchableOpacity
              key={f.key}
              style={[
                styles.filterChip,
                filter === f.key && styles.filterChipActive,
              ]}
              onPress={() => setFilter(f.key)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  filter === f.key && styles.filterChipTextActive,
                ]}
              >
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <FlatList
        data={listRows}
        keyExtractor={(row, i) =>
          row.type === 'header'
            ? `header-${row.group}-${i}`
            : `task-${row.task.id}`
        }
        renderItem={({ item: row }) => {
          if (row.type === 'header') {
            return (
              <View style={styles.groupHeader}>
                <Text style={styles.groupHeaderText}>{row.group}</Text>
              </View>
            );
          }
          return (
            <TaskItem
              item={row.task}
              isSubtask={row.isSubtask}
              blocked={row.blocked}
            />
          );
        }}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={refetch}
            tintColor="#6366f1"
          />
        }
        ListHeaderComponent={
          <>
            <PendingSuggestionsSection onAccepted={handleSuggestionAccepted} />
            {highlightTask ? (
              <TaskDoNowBanner task={highlightTask} />
            ) : nextUnblocked && filter === 'all' ? (
              <NextUnblockedBanner task={nextUnblocked} />
            ) : null}
          </>
        }
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>
              {filter === 'all'
                ? "No open tasks — you're all caught up!"
                : `No ${filter} tasks.`}
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  list: { padding: 16, gap: 10, flexGrow: 1 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
  },

  // Filter bar
  filterBar: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1f2937',
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#1f2937',
    marginRight: 8,
  },
  filterChipActive: { backgroundColor: '#6366f1' },
  filterChipText: { fontSize: 13, fontWeight: '500', color: '#9ca3af' },
  filterChipTextActive: { color: '#fff' },

  // Next unblocked banner
  nextBanner: {
    backgroundColor: '#1e3a2f',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#4ade80',
  },
  nextLabel: { fontSize: 11, fontWeight: '600', color: '#4ade80', marginBottom: 2 },
  nextTitle: { fontSize: 14, fontWeight: '600', color: '#f9fafb' },

  // Objective badge (shown in banners + task meta)
  objectiveBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#1e1b4b',
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 2,
    marginTop: 5,
    borderWidth: 1,
    borderColor: '#4338ca',
  },
  objectiveBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#818cf8',
  },

  // Do this now banner (from Execution Pulse handoff)
  doNowBanner: {
    backgroundColor: '#1e1b4b',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#6366f1',
  },
  doNowLabel: { fontSize: 11, fontWeight: '700', color: '#818cf8', marginBottom: 2, textTransform: 'uppercase', letterSpacing: 0.5 },
  doNowTitle: { fontSize: 15, fontWeight: '700', color: '#f9fafb' },
  doNowMeta: { fontSize: 12, color: '#9ca3af', marginTop: 2 },

  // Group header
  groupHeader: { paddingVertical: 6, paddingHorizontal: 2, marginTop: 4 },
  groupHeaderText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6366f1',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },

  // Task card
  taskCard: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 14,
    flexDirection: 'row',
  },
  subtaskCard: {
    marginLeft: 16,
    backgroundColor: '#172032',
    borderRadius: 8,
    padding: 12,
  },
  subtaskIndentLine: {
    width: 2,
    backgroundColor: '#374151',
    borderRadius: 1,
    marginRight: 10,
  },
  taskInner: { flex: 1 },
  taskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  taskTitle: { flex: 1, fontSize: 15, fontWeight: '600', color: '#f9fafb' },
  subtaskTitle: { fontSize: 14, color: '#d1d5db' },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    flexShrink: 0,
  },
  chip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  chipText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  blockedBadge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: '#431407',
    maxWidth: 120,
  },
  blockedBadgeText: { fontSize: 11, fontWeight: '600', color: '#fb923c' },
  subtaskCountBadge: {
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: '#1c2640',
    borderWidth: 1,
    borderColor: '#374151',
  },
  subtaskCountText: { fontSize: 11, fontWeight: '500', color: '#9ca3af' },
  calendarBadge: {
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: '#0c1a2e',
    borderWidth: 1,
    borderColor: '#1d4ed8',
    maxWidth: 100,
  },
  calendarBadgeText: { fontSize: 11, fontWeight: '500', color: '#60a5fa' },
  taskMeta: { flexDirection: 'row', gap: 12, marginTop: 6 },
  metaText: { fontSize: 12, color: '#9ca3af' },
  overdueText: { color: '#f87171' },
  emptyText: { color: '#6b7280', fontSize: 14 },
});

const suggStyles = StyleSheet.create({
  container: {
    backgroundColor: '#1a1a2e',
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#312e81',
  },
  header: {
    fontSize: 11,
    fontWeight: '700',
    color: '#818cf8',
    textTransform: 'uppercase',
    letterSpacing: 0.7,
    marginBottom: 10,
  },
  card: {
    backgroundColor: '#1e1b4b',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  cardBody: { flex: 1 },
  objectiveLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: '#6366f1',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 3,
  },
  title: { fontSize: 14, fontWeight: '600', color: '#f9fafb', lineHeight: 20 },
  reason: { fontSize: 12, color: '#9ca3af', marginTop: 4, lineHeight: 16 },
  actions: { flexDirection: 'column', gap: 6 },
  btn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    alignItems: 'center',
    minWidth: 64,
  },
  btnAccept: { backgroundColor: '#4f46e5' },
  btnReject: { backgroundColor: '#374151' },
  btnTextAccept: { fontSize: 12, fontWeight: '700', color: '#fff' },
  btnTextReject: { fontSize: 12, fontWeight: '600', color: '#9ca3af' },
});
