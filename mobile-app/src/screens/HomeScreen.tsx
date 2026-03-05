import React, { useEffect, useRef, useState } from 'react';
import {
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

// ── Weekly Focus / Reflection types ────────────────────────────────────────

interface ReflectionWeeklyPriority {
  id?: number;
  title: string;
  category?: string | null;
}

interface LatestReflectionResponse {
  week_score?: number | null;
  biggest_win?: string | null;
  ai_summary?: {
    weekly_priorities?: ReflectionWeeklyPriority[] | null;
    suggested_tasks?: string[] | null;
    recommendations?: string[] | null;
  } | null;
  weekly_priorities?: ReflectionWeeklyPriority[] | null;
}

interface WeeklyPlanSuggestedTask {
  id?: number;
  title: string;
  category?: string | null;
}

interface WeeklyTimeBlock {
  label?: string | null;
  time?: string | null;
  title?: string | null;
  start_time?: string | null;
}

interface WeeklyPlanResponse {
  priorities?: ReflectionWeeklyPriority[] | null;
  suggested_tasks?: WeeklyPlanSuggestedTask[] | null;
  time_blocks?: WeeklyTimeBlock[] | null;
  summary?: string | null;
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

function SkeletonLine({
  width = '100%',
  height = 14,
  style,
}: {
  width?: string | number;
  height?: number;
  style?: object;
}) {
  return <View style={[styles.skeletonLine, { width, height }, style]} />;
}

function formatRelativeTime(date: Date): string {
  const diffMin = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  return `${Math.floor(diffMin / 60)}h ago`;
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
        <SkeletonLine width="55%" height={11} style={{ marginBottom: 8 }} />
        <SkeletonLine height={18} style={{ marginBottom: 4 }} />
        <SkeletonLine width="80%" height={18} style={{ marginBottom: 12 }} />
        <SkeletonLine width="38%" height={12} style={{ marginBottom: 14 }} />
        <View style={styles.ctaRow}>
          <SkeletonLine height={38} style={{ flex: 1, borderRadius: 8 }} />
          <SkeletonLine height={38} style={{ flex: 1, borderRadius: 8 }} />
        </View>
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
        {[0, 1, 2].map(i => (
          <View key={i} style={[styles.priorityRow, i > 0 && styles.priorityRowBorder]}>
            <SkeletonLine width={18} height={16} style={{ borderRadius: 4 }} />
            <SkeletonLine style={{ flex: 1 }} height={16} />
          </View>
        ))}
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
        <SkeletonLine height={14} style={{ marginBottom: 6 }} />
        <SkeletonLine width="90%" height={14} style={{ marginBottom: 6 }} />
        <SkeletonLine width="65%" height={14} />
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

// ── Weekly Focus card ──────────────────────────────────────────────────────

function WeeklyFocusCard({
  reflection,
  weeklyPlan,
  priorities,
  tasks,
  events,
  loading,
}: {
  reflection: LatestReflectionResponse | null;
  weeklyPlan: WeeklyPlanResponse | null;
  priorities: PriorityItem[] | null;
  tasks: Task[];
  events: CalendarEvent[];
  loading: boolean;
}) {
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList>>();
  const [applied, setApplied] = useState(false);

  if (loading) {
    return (
      <Card>
        <SectionLabel text="Weekly Focus" />
        {[0, 1, 2].map(i => (
          <View key={i} style={[styles.weeklyPriorityRow, i > 0 && styles.priorityRowBorder]}>
            <SkeletonLine width={16} height={14} style={{ borderRadius: 4 }} />
            <SkeletonLine style={{ flex: 1 }} height={14} />
          </View>
        ))}
        <SkeletonLine width="70%" height={12} style={{ marginTop: 14 }} />
      </Card>
    );
  }

  // Top 3 priorities — priority chain: reflection → weekly plan → autopilot → derived
  const weekPriorities: ReflectionWeeklyPriority[] =
    (reflection?.weekly_priorities && reflection.weekly_priorities.length > 0
      ? reflection.weekly_priorities
      : reflection?.ai_summary?.weekly_priorities && reflection.ai_summary.weekly_priorities.length > 0
        ? reflection.ai_summary.weekly_priorities
        : weeklyPlan?.priorities && weeklyPlan.priorities.length > 0
          ? weeklyPlan.priorities
          : (priorities ?? deriveTopTasks(tasks)).map(p => ({ id: p.id, title: p.title, category: p.category }))
    ).slice(0, 3);

  // Suggested tasks
  let suggestedTasks: string[];
  if (weeklyPlan?.suggested_tasks && weeklyPlan.suggested_tasks.length > 0) {
    suggestedTasks = weeklyPlan.suggested_tasks.slice(0, 3).map(t => t.title);
  } else if (reflection?.ai_summary?.suggested_tasks && reflection.ai_summary.suggested_tasks.length > 0) {
    suggestedTasks = reflection.ai_summary.suggested_tasks.slice(0, 3);
  } else {
    suggestedTasks = deriveWeeklySuggestedTasks(tasks);
  }

  // Time blocks
  let timeBlocks: string[];
  if (weeklyPlan?.time_blocks && weeklyPlan.time_blocks.length > 0) {
    timeBlocks = weeklyPlan.time_blocks
      .map(b => {
        if (b.label) return b.label;
        if (b.title) return b.title;
        if (b.time) return b.time;
        if (b.start_time) {
          try {
            const d = new Date(b.start_time);
            const day = d.toLocaleDateString('en-US', { weekday: 'short' });
            const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
            return `${day} ${time}`;
          } catch {
            return b.start_time;
          }
        }
        return '';
      })
      .filter((s): s is string => s.length > 0)
      .slice(0, 3);
  } else {
    timeBlocks = deriveWeeklyTimeBlocks(events);
  }

  const hasContent = weekPriorities.length > 0 || suggestedTasks.length > 0 || timeBlocks.length > 0;

  if (!hasContent) {
    return (
      <Card>
        <SectionLabel text="Weekly Focus" />
        <Text style={styles.emptySubtext}>
          No weekly plan yet — complete a reflection to get started.
        </Text>
      </Card>
    );
  }

  return (
    <Card>
      <SectionLabel text="Weekly Focus" />

      {weekPriorities.length > 0 && (
        <>
          <Text style={styles.weeklySubheading}>This Week's Priorities</Text>
          {weekPriorities.map((p, i) => (
            <View
              key={p.id ?? i}
              style={[styles.weeklyPriorityRow, i > 0 && styles.priorityRowBorder]}
            >
              <Text style={styles.weeklyPriorityNum}>{i + 1}</Text>
              <Text style={styles.weeklyPriorityTitle} numberOfLines={2}>
                {p.title}
              </Text>
            </View>
          ))}
        </>
      )}

      {suggestedTasks.length > 0 && (
        <>
          <Text style={[styles.weeklySubheading, weekPriorities.length > 0 && { marginTop: 12 }]}>
            Tasks to Start
          </Text>
          {suggestedTasks.map((t, i) => (
            <View key={i} style={styles.weeklyTaskRow}>
              <Text style={styles.weeklyTaskBullet}>•</Text>
              <Text style={styles.weeklyTaskTitle} numberOfLines={2}>
                {t}
              </Text>
            </View>
          ))}
        </>
      )}

      {timeBlocks.length > 0 && (
        <>
          <Text style={[styles.weeklySubheading, { marginTop: 12 }]}>Time Blocks</Text>
          {timeBlocks.map((b, i) => (
            <Text key={i} style={styles.weeklyTimeBlock}>
              {b}
            </Text>
          ))}
        </>
      )}

      <View style={[styles.ctaRow, { marginTop: 16 }]}>
        <TouchableOpacity
          style={[
            styles.ctaButton,
            styles.ctaWeeklyApply,
            applied && styles.ctaWeeklyApplied,
          ]}
          onPress={() => setApplied(s => !s)}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaStartText}>{applied ? 'Applied ✓' : 'Apply this week'}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaOpen]}
          onPress={() => navigation.navigate('Calendar')}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaOpenText}>Open Calendar</Text>
        </TouchableOpacity>
      </View>
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

function deriveWeeklySuggestedTasks(tasks: Task[]): string[] {
  const open = tasks.filter(t => t.status !== 'done' && t.status !== 'cancelled');
  const sorted = [...open].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  return sorted.slice(0, 3).map(t => t.title);
}

function deriveWeeklyTimeBlocks(events: CalendarEvent[]): string[] {
  const now = new Date();
  const weekEnd = new Date();
  weekEnd.setDate(now.getDate() + 7);
  const upcoming = events.filter(e => {
    try {
      const d = new Date(e.start_time);
      return d >= now && d <= weekEnd;
    } catch {
      return false;
    }
  });
  return upcoming.slice(0, 3).map(e => {
    try {
      const d = new Date(e.start_time);
      const day = d.toLocaleDateString('en-US', { weekday: 'short' });
      const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
      return `${day} ${time} — ${e.title}`;
    } catch {
      return e.title;
    }
  });
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

function deriveNextEvent(events: CalendarEvent[]): CalendarEvent | null {
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  const upcoming = events
    .filter(e => {
      if (e.all_day || !e.start_time.startsWith(todayStr)) return false;
      try { return new Date(e.start_time) > now; } catch { return false; }
    })
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
  return upcoming[0] ?? null;
}

// ── Free-slot / day-planning helpers ──────────────────────────────────────

interface FreeSlot {
  start: Date;
  end: Date;
}

interface SuggestedBlock {
  slotStart: Date;
  slotEnd: Date;
  taskTitle: string;
}

function formatBlockTime(d: Date): string {
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function deriveFreeSlots(events: CalendarEvent[]): FreeSlot[] {
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  const dayStart = new Date(`${todayStr}T08:00:00`);
  const dayEnd = new Date(`${todayStr}T22:00:00`);
  const MIN_SLOT_MS = 30 * 60000;

  const todayEvents = events
    .filter(e => {
      if (!e.start_time || e.all_day) return false;
      const d = new Date(e.start_time);
      return !isNaN(d.getTime()) && e.start_time.startsWith(todayStr);
    })
    .map(e => ({
      start: new Date(e.start_time),
      end: e.end_time
        ? new Date(e.end_time)
        : new Date(new Date(e.start_time).getTime() + 60 * 60000),
    }))
    .filter(e => e.start < dayEnd && e.end > dayStart)
    .sort((a, b) => a.start.getTime() - b.start.getTime());

  const slots: FreeSlot[] = [];
  let cursor = new Date(Math.max(dayStart.getTime(), now.getTime()));

  for (const ev of todayEvents) {
    const gapEnd = new Date(Math.min(ev.start.getTime(), dayEnd.getTime()));
    if (gapEnd.getTime() - cursor.getTime() >= MIN_SLOT_MS) {
      slots.push({ start: new Date(cursor), end: gapEnd });
    }
    cursor = new Date(Math.max(cursor.getTime(), ev.end.getTime()));
    if (cursor >= dayEnd) break;
  }

  if (cursor < dayEnd && dayEnd.getTime() - cursor.getTime() >= MIN_SLOT_MS) {
    slots.push({ start: new Date(cursor), end: dayEnd });
  }

  return slots;
}

function buildSuggestedBlocks(
  slots: FreeSlot[],
  tasks: Task[],
  priorities: PriorityItem[] | null,
): SuggestedBlock[] {
  const topItems = (priorities ?? deriveTopTasks(tasks)).slice(0, 3);
  const DURATION_MS = 60 * 60000; // 1 hour blocks
  const blocks: SuggestedBlock[] = [];

  for (let i = 0; i < Math.min(slots.length, topItems.length); i++) {
    const slot = slots[i];
    const slotEnd = new Date(
      Math.min(slot.start.getTime() + DURATION_MS, slot.end.getTime()),
    );
    blocks.push({ slotStart: slot.start, slotEnd, taskTitle: topItems[i].title });
  }

  return blocks;
}

// ── FreeSlotsPlanCard ──────────────────────────────────────────────────────

function FreeSlotsPlanCard({
  tasks,
  events,
  priorities,
  accepted,
  onSetAccepted,
  loading,
}: {
  tasks: Task[];
  events: CalendarEvent[];
  priorities: PriorityItem[] | null;
  accepted: boolean;
  onSetAccepted: (v: boolean) => void;
  loading: boolean;
}) {
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList>>();

  if (loading) {
    return (
      <Card>
        <SectionLabel text="Free Slots Today" />
        {[0, 1, 2].map(i => (
          <View key={i} style={[styles.suggestedBlockRow, i > 0 && styles.priorityRowBorder]}>
            <SkeletonLine width={70} height={32} style={{ borderRadius: 6 }} />
            <SkeletonLine style={{ flex: 1 }} height={14} />
          </View>
        ))}
      </Card>
    );
  }

  const freeSlots = deriveFreeSlots(events);
  const suggestedBlocks = buildSuggestedBlocks(freeSlots, tasks, priorities);

  if (freeSlots.length === 0) {
    return (
      <Card>
        <SectionLabel text="Free Slots Today" />
        <Text style={styles.emptySubtext}>
          No free slots detected today — your calendar looks full.
        </Text>
      </Card>
    );
  }

  if (suggestedBlocks.length === 0) {
    return (
      <Card>
        <SectionLabel text="Free Slots Today" />
        <Text style={styles.emptySubtext}>
          {freeSlots.length} free slot{freeSlots.length !== 1 ? 's' : ''} available — add tasks to fill them.
        </Text>
      </Card>
    );
  }

  if (accepted) {
    return (
      <Card>
        <SectionLabel text="Free Slots Today" />
        <View style={styles.acceptedBanner}>
          <Text style={styles.acceptedBannerText}>Plan accepted</Text>
        </View>
        {suggestedBlocks.map((b, i) => (
          <View key={i} style={[styles.acceptedBlock, i > 0 && styles.priorityRowBorder]}>
            <Text style={styles.acceptedBlockTime}>
              {formatBlockTime(b.slotStart)}–{formatBlockTime(b.slotEnd)}
            </Text>
            <Text style={styles.acceptedBlockTask} numberOfLines={1}>
              {b.taskTitle}
            </Text>
          </View>
        ))}
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaOpen, { marginTop: 12 }]}
          onPress={() => onSetAccepted(false)}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaOpenText}>Edit plan</Text>
        </TouchableOpacity>
      </Card>
    );
  }

  return (
    <Card>
      <SectionLabel text="Free Slots Today" />
      <Text style={styles.freeSlotsHint}>
        {freeSlots.length} free slot{freeSlots.length !== 1 ? 's' : ''} · Suggested plan:
      </Text>

      {suggestedBlocks.map((b, i) => (
        <View key={i} style={[styles.suggestedBlockRow, i > 0 && styles.priorityRowBorder]}>
          <View style={styles.suggestedBlockTimeBox}>
            <Text style={styles.suggestedBlockTime}>{formatBlockTime(b.slotStart)}</Text>
            <Text style={styles.suggestedBlockTimeSep}>–</Text>
            <Text style={styles.suggestedBlockTime}>{formatBlockTime(b.slotEnd)}</Text>
          </View>
          <Text style={styles.suggestedBlockTask} numberOfLines={2}>
            {b.taskTitle}
          </Text>
        </View>
      ))}

      <View style={[styles.ctaRow, { marginTop: 14 }]}>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaAccept]}
          onPress={() => onSetAccepted(true)}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaStartText}>Accept plan</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaOpen]}
          onPress={() => navigation.navigate('Calendar')}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaOpenText}>Adjust</Text>
        </TouchableOpacity>
      </View>
    </Card>
  );
}

// ── Execution Pulse card ───────────────────────────────────────────────────

function ExecutionPulseCard({
  tasks,
  events,
  planAccepted,
  planBlockCount,
  onBackToPlan,
  loading,
}: {
  tasks: Task[];
  events: CalendarEvent[];
  planAccepted: boolean;
  planBlockCount: number;
  onBackToPlan: () => void;
  loading: boolean;
}) {
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList>>();

  const topTask = deriveNextTask(tasks);

  function handleDoFirstTask() {
    navigation.navigate('Tasks', { highlightTaskId: topTask?.id });
  }

  if (loading) {
    return (
      <Card>
        <SectionLabel text="Execution Pulse" />
        <View style={styles.pulseMetricsRow}>
          <SkeletonLine width={72} height={56} style={{ borderRadius: 8 }} />
          <SkeletonLine width={72} height={56} style={{ borderRadius: 8 }} />
        </View>
        <SkeletonLine height={34} style={{ borderRadius: 8, marginBottom: 4 }} />
        <View style={[styles.ctaRow, { marginTop: 14 }]}>
          <SkeletonLine height={38} style={{ flex: 1, borderRadius: 8 }} />
          <SkeletonLine height={38} style={{ flex: 1, borderRadius: 8 }} />
        </View>
      </Card>
    );
  }

  const overdueCount = tasks.filter(
    t => t.is_overdue && t.status !== 'done' && t.status !== 'cancelled',
  ).length;
  const nextEvent = deriveNextEvent(events);
  const hasContent = overdueCount > 0 || planBlockCount > 0 || nextEvent != null || topTask != null;

  if (!hasContent) {
    return (
      <Card>
        <SectionLabel text="Execution Pulse" />
        <Text style={styles.emptySubtext}>All clear — nothing pending right now.</Text>
      </Card>
    );
  }

  return (
    <Card>
      <SectionLabel text="Execution Pulse" />

      {/* Metrics row */}
      {(overdueCount > 0 || planBlockCount > 0) && (
        <View style={styles.pulseMetricsRow}>
          {overdueCount > 0 && (
            <View style={[styles.pulseMetric, styles.pulseMetricOverdue]}>
              <Text style={styles.pulseMetricValue}>{overdueCount}</Text>
              <Text style={styles.pulseMetricLabel}>Overdue</Text>
            </View>
          )}
          {planBlockCount > 0 && (
            <View style={[styles.pulseMetric, planAccepted ? styles.pulseMetricAccepted : styles.pulseMetricSuggested]}>
              <Text style={styles.pulseMetricValue}>{planBlockCount}</Text>
              <Text style={styles.pulseMetricLabel}>{planAccepted ? 'Plan blocks' : 'Suggested'}</Text>
            </View>
          )}
        </View>
      )}

      {/* Next event */}
      {nextEvent != null && (
        <View style={styles.pulseEventRow}>
          <Text style={styles.pulseEventLabel}>Next up</Text>
          <Text style={styles.pulseEventTime}>{formatBlockTime(new Date(nextEvent.start_time))}</Text>
          <Text style={styles.pulseEventTitle} numberOfLines={1}>{nextEvent.title}</Text>
        </View>
      )}

      {/* CTAs */}
      <View style={[styles.ctaRow, { marginTop: 14 }]}>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaPulseTask]}
          onPress={handleDoFirstTask}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaStartText}>Do first task now</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.ctaButton, styles.ctaOpen]}
          onPress={onBackToPlan}
          activeOpacity={0.75}
        >
          <Text style={styles.ctaOpenText}>Back to plan</Text>
        </TouchableOpacity>
      </View>
    </Card>
  );
}

// ── Main screen ────────────────────────────────────────────────────────────

export default function HomeScreen() {
  const scrollViewRef = useRef<ScrollView>(null);
  const dayPlanningY = useRef(0);
  const [planAccepted, setPlanAccepted] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const prevLoadingRef = useRef(false);

  const health = useApi<HealthResponse>('/health');
  const dashboard = useApi<DashboardResponse>('/api/dashboard');

  // Autopilot endpoints (may 404 on older backends)
  const nextAction = useApi<NextActionResponse>('/api/autopilot/next-action');
  const prioritiesApi = useApi<PrioritiesResponse>('/api/priorities');
  const planApi = useApi<PlanResponse>('/api/autopilot/plan');

  // Fallback data sources
  const tasksApi = useApi<TasksResponse>('/api/tasks');
  const calendarApi = useApi<CalendarResponse>('/api/calendar');

  // Weekly Focus data sources (may 404 on older backends)
  const reflectionApi = useApi<LatestReflectionResponse>('/api/reflections/latest');
  const weeklyPlanApi = useApi<WeeklyPlanResponse>('/api/autopilot/weekly-plan');

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

  const planBlockCount = buildSuggestedBlocks(
    deriveFreeSlots(events),
    tasks,
    resolvedPriorities,
  ).length;

  function handleBackToPlan() {
    scrollViewRef.current?.scrollTo({ y: dayPlanningY.current, animated: true });
  }

  function handleRefresh() {
    health.refetch();
    dashboard.refetch();
    nextAction.refetch();
    prioritiesApi.refetch();
    planApi.refetch();
    tasksApi.refetch();
    calendarApi.refetch();
    reflectionApi.refetch();
    weeklyPlanApi.refetch();
  }

  useEffect(() => {
    if (prevLoadingRef.current && !isAnyLoading) {
      setLastUpdated(new Date());
    }
    prevLoadingRef.current = isAnyLoading;
  }, [isAnyLoading]);

  const autopilotCardLoading =
    (nextAction.loading && tasksApi.loading) ||
    (prioritiesApi.loading && tasksApi.loading) ||
    (planApi.loading && (tasksApi.loading || calendarApi.loading));

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        ref={scrollViewRef}
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
          <View>
            <Text style={styles.greeting}>
              {user ? `Hey, ${user.first_name}` : 'Personal OS'}
            </Text>
            {lastUpdated && !isAnyLoading && (
              <Text style={styles.lastUpdatedText}>
                updated {formatRelativeTime(lastUpdated)}
              </Text>
            )}
          </View>
          <View style={[styles.statusBadge, apiOnline ? styles.statusOnline : styles.statusOffline]}>
            <Text style={styles.statusText}>{apiOnline ? 'Online' : 'Offline'}</Text>
          </View>
        </View>

        {/* Dashboard skeleton */}
        {isDashboardLoading && !stats && (
          <>
            <View style={styles.levelRow}>
              <SkeletonLine width="42%" height={16} />
              <SkeletonLine width="22%" height={12} />
            </View>
            <SkeletonLine height={6} style={{ borderRadius: 3, marginBottom: 24 }} />
            <View style={styles.statsGrid}>
              {[0, 1, 2, 3, 4, 5].map(i => (
                <View key={i} style={styles.statCard}>
                  <SkeletonLine width="55%" height={22} style={{ alignSelf: 'center', marginBottom: 6, borderRadius: 4 }} />
                  <SkeletonLine width="65%" height={11} style={{ alignSelf: 'center' }} />
                </View>
              ))}
            </View>
          </>
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

        {/* ── Execution Pulse Section ── */}
        <ExecutionPulseCard
          tasks={tasks}
          events={events}
          planAccepted={planAccepted}
          planBlockCount={planBlockCount}
          onBackToPlan={handleBackToPlan}
          loading={tasksApi.loading && calendarApi.loading}
        />

        {/* ── Weekly Focus Section ── */}
        <Text style={styles.sectionTitle}>Weekly Focus</Text>
        <WeeklyFocusCard
          reflection={reflectionApi.error ? null : (reflectionApi.data ?? null)}
          weeklyPlan={weeklyPlanApi.error ? null : (weeklyPlanApi.data ?? null)}
          priorities={resolvedPriorities}
          tasks={tasks}
          events={events}
          loading={
            reflectionApi.loading && weeklyPlanApi.loading && tasksApi.loading
          }
        />

        {/* ── Day Planning Section ── */}
        <View onLayout={(e) => { dayPlanningY.current = e.nativeEvent.layout.y; }}>
          <Text style={styles.sectionTitle}>Day Planning</Text>
        </View>
        <FreeSlotsPlanCard
          tasks={tasks}
          events={events}
          priorities={resolvedPriorities}
          accepted={planAccepted}
          onSetAccepted={setPlanAccepted}
          loading={calendarApi.loading && tasksApi.loading}
        />

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

  skeletonLine: {
    backgroundColor: '#374151',
    borderRadius: 4,
  },
  lastUpdatedText: {
    fontSize: 11,
    color: '#4b5563',
    marginTop: 2,
  },

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

  // Weekly Focus
  weeklySubheading: {
    fontSize: 11,
    fontWeight: '700',
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  weeklyPriorityRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    paddingVertical: 6,
  },
  weeklyPriorityNum: {
    fontSize: 13,
    fontWeight: '700',
    color: '#10b981',
    minWidth: 16,
    marginTop: 1,
  },
  weeklyPriorityTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#f9fafb',
    flex: 1,
  },
  weeklyTaskRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    paddingVertical: 3,
  },
  weeklyTaskBullet: {
    fontSize: 14,
    color: '#6366f1',
    marginTop: 1,
  },
  weeklyTaskTitle: {
    fontSize: 13,
    color: '#d1d5db',
    flex: 1,
  },
  weeklyTimeBlock: {
    fontSize: 12,
    color: '#9ca3af',
    paddingVertical: 2,
  },
  ctaWeeklyApply: { backgroundColor: '#059669' },
  ctaWeeklyApplied: { backgroundColor: '#065f46' },

  // Free Slots / Day Planning card
  freeSlotsHint: {
    fontSize: 12,
    color: '#9ca3af',
    marginBottom: 10,
  },
  suggestedBlockRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingVertical: 8,
  },
  suggestedBlockTimeBox: {
    alignItems: 'center',
    minWidth: 70,
  },
  suggestedBlockTime: {
    fontSize: 11,
    fontWeight: '700',
    color: '#f59e0b',
  },
  suggestedBlockTimeSep: {
    fontSize: 10,
    color: '#4b5563',
  },
  suggestedBlockTask: {
    fontSize: 13,
    fontWeight: '600',
    color: '#f9fafb',
    flex: 1,
    marginTop: 2,
  },
  ctaAccept: { backgroundColor: '#b45309' },
  ctaPulseTask: { backgroundColor: '#be123c' },

  // Execution Pulse card
  pulseMetricsRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  pulseMetric: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
    minWidth: 72,
  },
  pulseMetricOverdue: { backgroundColor: '#450a0a' },
  pulseMetricAccepted: { backgroundColor: '#052e16' },
  pulseMetricSuggested: { backgroundColor: '#172554' },
  pulseMetricValue: { fontSize: 20, fontWeight: '700', color: '#f9fafb' },
  pulseMetricLabel: { fontSize: 10, fontWeight: '600', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 2 },
  pulseEventRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#111827',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
    marginBottom: 4,
  },
  pulseEventLabel: { fontSize: 10, fontWeight: '700', color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.4 },
  pulseEventTime: { fontSize: 12, fontWeight: '700', color: '#f59e0b' },
  pulseEventTitle: { fontSize: 13, color: '#d1d5db', flex: 1 },
  acceptedBanner: {
    backgroundColor: '#064e3b',
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 12,
    alignSelf: 'flex-start',
    marginBottom: 10,
  },
  acceptedBannerText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6ee7b7',
  },
  acceptedBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 6,
  },
  acceptedBlockTime: {
    fontSize: 11,
    fontWeight: '700',
    color: '#10b981',
    minWidth: 100,
  },
  acceptedBlockTask: {
    fontSize: 13,
    color: '#d1d5db',
    flex: 1,
  },
});
