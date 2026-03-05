import React, { useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApi } from '../hooks/useApi';
import type { TabParamList } from '../navigation/TabNavigator';

// ── Dashboard ──────────────────────────────────────────────────────────────

interface DashboardStats {
  active_objectives: number;
  open_tasks: number;
  streak_days: number;
  level: number;
  level_title: string;
  xp_progress: number;
  xp_to_next: number;
  workouts_this_week: number;
  routines_done_today: number;
  routines_total: number;
  water_today_liters: number;
  total_xp: number;
}

interface DashboardUser {
  first_name: string;
  timezone: string;
}

interface DashboardResponse {
  user: DashboardUser;
  stats: DashboardStats;
}

interface HealthResponse {
  status: string;
  version: string;
}

// ── Autopilot ──────────────────────────────────────────────────────────────

interface NextActionTask {
  id: number;
  title: string;
  category?: string | null;
  priority?: number;
  score?: number | null;
  objective_title?: string | null;
  is_blocked?: boolean;
  blocker_title?: string | null;
}

interface NextUnblocked {
  id: number;
  title: string;
  category?: string | null;
}

interface NextActionResponse {
  task: NextActionTask;
  reason?: string | null;
  score?: number | null;
  next_unblocked?: NextUnblocked | null;
}

interface PriorityItem {
  id: number;
  title: string;
  category?: string | null;
  priority?: number;
  due_date?: string | null;
  is_overdue?: boolean;
}

interface PrioritiesResponse {
  priorities: PriorityItem[];
}

interface PlanResponse {
  summary?: string | null;
  plan?: string | null;
  task_count?: number | null;
  event_count?: number | null;
}

// ── Shared task / calendar types (for fallback) ────────────────────────────

interface Task {
  id: number;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  category: string | null;
  due_date: string | null;
  is_overdue: boolean;
}

interface TasksResponse {
  tasks: Task[];
}

interface CalendarEvent {
  id: number;
  title: string;
  start_time: string;
  end_time: string | null;
  all_day: boolean;
  event_type: string | null;
}

interface CalendarResponse {
  events: CalendarEvent[];
}

// ── Small helpers ──────────────────────────────────────────────────────────

function SectionLabel({ text }: { text: string }) {
  return <Text style={styles.sectionLabel}>{text}</Text>;
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

// ── Autopilot section cards ────────────────────────────────────────────────

function NextActionCard({
  nextAction,
  tasks,
  loading,
}: {
  nextAction: NextActionResponse | null;
  tasks: Task[];
  loading: boolean;
}) {
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList>>();
  const [started, setStarted] = useState(false);

  if (loading) {
    return (
      <Card>
        <SectionLabel text="Next Action" />
        <ActivityIndicator size="small" color="#6366f1" style={{ alignSelf: 'flex-start' }} />
      </Card>
    );
  }

  // Prefer autopilot payload, fall back to derived
  const task = nextAction?.task ?? deriveNextTask(tasks);
  const reason = nextAction?.reason ?? null;
  const score = nextAction?.score ?? nextAction?.task?.score ?? null;
  const objectiveTitle = nextAction?.task?.objective_title ?? null;
  const isBlocked = nextAction?.task?.is_blocked === true;
  const blockerTitle = nextAction?.task?.blocker_title ?? null;
  const nextUnblocked = nextAction?.next_unblocked ?? null;

  if (!task) {
    return (
      <Card>
        <SectionLabel text="Next Action" />
        <Text style={styles.emptySubtext}>Nothing pending — nice work!</Text>
      </Card>
    );
  }

  // "Why this now?" — use API fields first, then heuristic
  let whyText: string;
  if (reason && reason.length > 0) {
    whyText = reason;
  } else if (score != null) {
    whyText = `Priority score: ${score}`;
  } else if ('is_overdue' in task && task.is_overdue) {
    whyText = 'This task is overdue';
  } else if ((task.priority ?? 0) >= 3) {
    whyText = 'High-priority unblocked task';
  } else {
    whyText = 'Top unblocked task right now';
  }

  return (
    <Card>
      <SectionLabel text="Next Action" />

      {/* Objective context */}
      {objectiveTitle != null && (
        <Text style={styles.objectiveContext}>{objectiveTitle}</Text>
      )}

      <Text style={styles.nextActionTitle} numberOfLines={3}>
        {task.title}
      </Text>
      {task.category != null && (
        <Text style={styles.metaText}>{task.category}</Text>
      )}

      {/* Blocker hint */}
      {isBlocked && (
        <View style={styles.blockerBox}>
          <Text style={styles.blockerLabel}>
            Blocked{blockerTitle ? ` by: ${blockerTitle}` : ''}
          </Text>
          {nextUnblocked != null && (
            <Text style={styles.nextUnblockedText}>
              Next unblocked: {nextUnblocked.title}
            </Text>
          )}
        </View>
      )}

      {/* Why this now? */}
      <View style={styles.whyRow}>
        <Text style={styles.whyLabel}>Why this now?</Text>
        <Text style={styles.whyText}>{whyText}</Text>
      </View>

      {/* CTAs */}
      <View style={styles.ctaRow}>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaStart, started && styles.ctaStarted]}
          onPress={() => setStarted(s => !s)}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaStartText}>{started ? 'In progress' : 'Start now'}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaOpen]}
          onPress={() => navigation.navigate('Tasks')}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaOpenText}>Open in Tasks</Text>
        </TouchableOpacity>
      </View>
    </Card>
  );
}

function PriorityListCard({
  priorities,
  tasks,
  loading,
}: {
  priorities: PriorityItem[] | null;
  tasks: Task[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card>
        <SectionLabel text="Top Priorities" />
        <ActivityIndicator size="small" color="#6366f1" style={{ alignSelf: 'flex-start' }} />
      </Card>
    );
  }

  const items: PriorityItem[] = priorities ?? deriveTopTasks(tasks);

  if (items.length === 0) {
    return (
      <Card>
        <SectionLabel text="Top Priorities" />
        <Text style={styles.emptySubtext}>No open priorities found.</Text>
      </Card>
    );
  }

  return (
    <Card>
      <SectionLabel text="Top Priorities" />
      {items.map((item, idx) => (
        <View key={item.id} style={[styles.priorityRow, idx > 0 && styles.priorityRowBorder]}>
          <Text style={styles.priorityIndex}>{idx + 1}</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.priorityTitle} numberOfLines={2}>
              {item.title}
            </Text>
            {item.category != null && (
              <Text style={styles.metaText}>{item.category}</Text>
            )}
          </View>
          {item.is_overdue === true && (
            <Text style={styles.overdueTag}>overdue</Text>
          )}
        </View>
      ))}
    </Card>
  );
}

function TodayPlanCard({
  plan,
  tasks,
  events,
  loading,
}: {
  plan: PlanResponse | null;
  tasks: Task[];
  events: CalendarEvent[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card>
        <SectionLabel text="Today's Plan" />
        <ActivityIndicator size="small" color="#6366f1" style={{ alignSelf: 'flex-start' }} />
      </Card>
    );
  }

  const summaryText =
    plan?.summary ?? plan?.plan ?? derivePlanSummary(tasks, events);

  return (
    <Card>
      <SectionLabel text="Today's Plan" />
      <Text style={styles.planText}>{summaryText}</Text>
    </Card>
  );
}

// ── Fallback derivation helpers ────────────────────────────────────────────

function deriveNextTask(tasks: Task[]): (NextActionTask & { is_overdue?: boolean }) | null {
  const open = tasks.filter(t => t.status !== 'done' && t.status !== 'cancelled');
  if (open.length === 0) return null;
  // Prefer overdue first, then by priority desc
  const sorted = [...open].sort((a, b) => {
    if (a.is_overdue !== b.is_overdue) return a.is_overdue ? -1 : 1;
    return (b.priority ?? 0) - (a.priority ?? 0);
  });
  return sorted[0];
}

function deriveTopTasks(tasks: Task[]): PriorityItem[] {
  const open = tasks.filter(t => t.status !== 'done' && t.status !== 'cancelled');
  const sorted = [...open].sort((a, b) => {
    if (a.is_overdue !== b.is_overdue) return a.is_overdue ? -1 : 1;
    return (b.priority ?? 0) - (a.priority ?? 0);
  });
  return sorted.slice(0, 5).map(t => ({
    id: t.id,
    title: t.title,
    category: t.category,
    priority: t.priority,
    due_date: t.due_date,
    is_overdue: t.is_overdue,
  }));
}

function derivePlanSummary(tasks: Task[], events: CalendarEvent[]): string {
  const openCount = tasks.filter(t => t.status !== 'done' && t.status !== 'cancelled').length;
  const overdueCount = tasks.filter(t => t.is_overdue).length;
  const today = new Date();
  const todayStr = today.toISOString().split('T')[0];
  const todayEvents = events.filter(e => e.start_time.startsWith(todayStr));

  const parts: string[] = [];
  if (openCount > 0) {
    parts.push(`${openCount} open task${openCount !== 1 ? 's' : ''}`);
  }
  if (overdueCount > 0) {
    parts.push(`${overdueCount} overdue`);
  }
  if (todayEvents.length > 0) {
    parts.push(`${todayEvents.length} event${todayEvents.length !== 1 ? 's' : ''} today`);
  }

  if (parts.length === 0) return 'No tasks or events scheduled today.';
  return parts.join(' · ');
}

// ── Main screen ────────────────────────────────────────────────────────────

export default function HomeScreen() {
  const health = useApi<HealthResponse>('/health');
  const dashboard = useApi<DashboardResponse>('/api/dashboard');

  // Autopilot endpoints (may 404 on older backends)
  const nextAction = useApi<NextActionResponse>('/api/autopilot/next-action');
  const prioritiesApi = useApi<PrioritiesResponse>('/api/priorities');
  const planApi = useApi<PlanResponse>('/api/autopilot/plan');

  // Fallback data sources
  const tasksApi = useApi<TasksResponse>('/api/tasks');
  const calendarApi = useApi<CalendarResponse>('/api/calendar');

  const isDashboardLoading = health.loading || dashboard.loading;
  const isAutopilotLoading = nextAction.loading || prioritiesApi.loading || planApi.loading;
  const isFallbackLoading = tasksApi.loading || calendarApi.loading;
  const isAnyLoading = isDashboardLoading || (isAutopilotLoading && isFallbackLoading);

  // Resolved data: prefer autopilot, fall back to derived
  const resolvedNextAction = nextAction.error ? null : (nextAction.data ?? null);
  const resolvedPriorities = prioritiesApi.error
    ? null
    : (prioritiesApi.data?.priorities ?? null);
  const resolvedPlan = planApi.error ? null : (planApi.data ?? null);

  const tasks = tasksApi.data?.tasks ?? [];
  const events = calendarApi.data?.events ?? [];

  const stats = dashboard.data?.stats;
  const user = dashboard.data?.user;
  const apiOnline = !health.error && health.data?.status === 'ok';

  function handleRefresh() {
    health.refetch();
    dashboard.refetch();
    nextAction.refetch();
    prioritiesApi.refetch();
    planApi.refetch();
    tasksApi.refetch();
    calendarApi.refetch();
  }

  const autopilotCardLoading =
    (nextAction.loading && tasksApi.loading) ||
    (prioritiesApi.loading && tasksApi.loading) ||
    (planApi.loading && (tasksApi.loading || calendarApi.loading));

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={isAnyLoading}
            onRefresh={handleRefresh}
            tintColor="#6366f1"
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.greeting}>
            {user ? `Hey, ${user.first_name}` : 'Personal OS'}
          </Text>
          <View style={[styles.statusBadge, apiOnline ? styles.statusOnline : styles.statusOffline]}>
            <Text style={styles.statusText}>{apiOnline ? 'Online' : 'Offline'}</Text>
          </View>
        </View>

        {/* Dashboard skeleton */}
        {isDashboardLoading && !stats && (
          <View style={styles.skeletonRow}>
            <ActivityIndicator size="large" color="#6366f1" />
          </View>
        )}

        {/* Level + XP */}
        {stats && (
          <>
            <View style={styles.levelRow}>
              <Text style={styles.levelTitle}>
                Lv.{stats.level} — {stats.level_title}
              </Text>
              <Text style={styles.xpText}>
                {stats.xp_progress}/{stats.xp_to_next} XP
              </Text>
            </View>
            <View style={styles.xpBar}>
              <View
                style={[
                  styles.xpFill,
                  { width: `${Math.min(100, (stats.xp_progress / stats.xp_to_next) * 100)}%` },
                ]}
              />
            </View>
          </>
        )}

        {/* Quick Stats */}
        {stats && (
          <>
            <Text style={styles.sectionTitle}>Quick Stats</Text>
            <View style={styles.statsGrid}>
              <StatCard label="Streak" value={`${stats.streak_days}d`} />
              <StatCard label="Open Tasks" value={stats.open_tasks} />
              <StatCard label="Objectives" value={stats.active_objectives} />
              <StatCard label="Workouts" value={`${stats.workouts_this_week}/wk`} />
              <StatCard
                label="Routines"
                value={`${stats.routines_done_today}/${stats.routines_total}`}
              />
              <StatCard label="Water" value={`${stats.water_today_liters}L`} />
            </View>
          </>
        )}

        {/* ── Autopilot Section ── */}
        <Text style={styles.sectionTitle}>Autopilot</Text>

        <NextActionCard
          nextAction={resolvedNextAction}
          tasks={tasks}
          loading={autopilotCardLoading && nextAction.loading && tasksApi.loading}
        />

        <PriorityListCard
          priorities={resolvedPriorities}
          tasks={tasks}
          loading={autopilotCardLoading && prioritiesApi.loading && tasksApi.loading}
        />

        <TodayPlanCard
          plan={resolvedPlan}
          tasks={tasks}
          events={events}
          loading={
            autopilotCardLoading &&
            planApi.loading &&
            tasksApi.loading &&
            calendarApi.loading
          }
        />
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  scroll: { padding: 16, flexGrow: 1 },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  greeting: { fontSize: 22, fontWeight: '700', color: '#f9fafb' },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  statusOnline: { backgroundColor: '#14532d' },
  statusOffline: { backgroundColor: '#7f1d1d' },
  statusText: { fontSize: 12, color: '#f9fafb', fontWeight: '600' },

  skeletonRow: { alignItems: 'center', paddingVertical: 24 },

  levelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  levelTitle: { fontSize: 16, fontWeight: '600', color: '#f9fafb' },
  xpText: { fontSize: 12, color: '#9ca3af' },
  xpBar: {
    height: 6,
    backgroundColor: '#1f2937',
    borderRadius: 3,
    marginBottom: 24,
    overflow: 'hidden',
  },
  xpFill: { height: '100%', backgroundColor: '#6366f1', borderRadius: 3 },

  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 12,
    marginTop: 8,
  },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 24 },
  statCard: {
    flex: 1,
    minWidth: '30%',
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  statValue: { fontSize: 20, fontWeight: '700', color: '#f9fafb', marginBottom: 4 },
  statLabel: { fontSize: 11, color: '#9ca3af', textAlign: 'center' },

  // Autopilot cards
  card: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#6366f1',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  nextActionTitle: { fontSize: 17, fontWeight: '700', color: '#f9fafb', marginBottom: 6 },
  metaText: { fontSize: 12, color: '#9ca3af', marginTop: 2 },
  emptySubtext: { fontSize: 13, color: '#6b7280' },

  objectiveContext: {
    fontSize: 11,
    fontWeight: '600',
    color: '#818cf8',
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  blockerBox: {
    backgroundColor: '#1c1917',
    borderRadius: 8,
    padding: 10,
    marginTop: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#f97316',
  },
  blockerLabel: { fontSize: 12, fontWeight: '700', color: '#f97316' },
  nextUnblockedText: { fontSize: 12, color: '#d1d5db', marginTop: 4 },
  whyRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
    marginTop: 10,
  },
  whyLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#4b5563',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: 1,
  },
  whyText: { fontSize: 12, color: '#6b7280', fontStyle: 'italic', flex: 1 },
  ctaRow: { flexDirection: 'row', gap: 10, marginTop: 14 },
  ctaButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  ctaStart: { backgroundColor: '#4f46e5' },
  ctaStarted: { backgroundColor: '#15803d' },
  ctaOpen: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#374151',
  },
  ctaStartText: { fontSize: 13, fontWeight: '700', color: '#ffffff' },
  ctaOpenText: { fontSize: 13, fontWeight: '600', color: '#9ca3af' },

  priorityRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingVertical: 8,
  },
  priorityRowBorder: { borderTopWidth: 1, borderTopColor: '#374151' },
  priorityIndex: {
    fontSize: 15,
    fontWeight: '700',
    color: '#4b5563',
    minWidth: 18,
    marginTop: 1,
  },
  priorityTitle: { fontSize: 14, fontWeight: '600', color: '#f9fafb' },
  overdueTag: {
    fontSize: 10,
    fontWeight: '700',
    color: '#f87171',
    textTransform: 'uppercase',
    alignSelf: 'flex-start',
    marginTop: 2,
  },

  planText: { fontSize: 14, color: '#d1d5db', lineHeight: 20 },
});
