import React, { useState, useCallback } from 'react';
import {
  ActivityIndicator,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  TouchableWithoutFeedback,
  View,
} from 'react-native';
import { apiRequest } from '../lib/apiClient';

// ── Types ──────────────────────────────────────────────────────────────────

interface DailyPlanSection {
  id: string;
  title: string;
  items: { id: number; title: string; reason: string }[];
}

interface DailyPlanResponse {
  summary: string;
  sections: DailyPlanSection[];
  generated_by: string;
}

interface NextActionResponse {
  task: { id: number; title: string; category?: string | null; objective_title?: string | null };
  reason?: string | null;
}

interface TasksResponse {
  tasks: { id: number; title: string; category: string | null; priority: number; status: string; is_overdue: boolean }[];
}

// ── Sub-views ──────────────────────────────────────────────────────────────

function PlanDayView() {
  const [plan, setPlan] = useState<DailyPlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPlan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<DailyPlanResponse>('/api/autopilot/daily-plan');
      setPlan(data);
    } catch {
      // Fallback: try simple tasks list
      try {
        const tasksData = await apiRequest<TasksResponse>('/api/tasks');
        const open = tasksData.tasks.filter(t => t.status !== 'done' && t.status !== 'cancelled');
        setPlan({
          summary: `${open.length} open tasks today`,
          sections: [{ id: 'tasks', title: 'Open Tasks', items: open.slice(0, 5).map(t => ({ id: t.id, title: t.title, reason: t.is_overdue ? 'Overdue' : '' })) }],
          generated_by: 'deterministic',
        });
      } catch {
        setError('Could not load plan');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchPlan(); }, [fetchPlan]);

  if (loading) {
    return (
      <View style={subStyles.centered}>
        <ActivityIndicator color="#6366f1" size="large" />
        <Text style={subStyles.loadingText}>Building your plan…</Text>
      </View>
    );
  }

  if (error || !plan) {
    return (
      <View style={subStyles.centered}>
        <Text style={subStyles.errorText}>{error ?? 'No plan available'}</Text>
        <TouchableOpacity style={subStyles.retryBtn} onPress={fetchPlan}>
          <Text style={subStyles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={subStyles.scroll} showsVerticalScrollIndicator={false}>
      <Text style={subStyles.planSummary}>{plan.summary}</Text>
      {plan.generated_by === 'ai' && (
        <View style={subStyles.aiBadge}>
          <Text style={subStyles.aiBadgeText}>AI-generated</Text>
        </View>
      )}
      {plan.sections.map(section => (
        <View key={section.id} style={subStyles.planSection}>
          <Text style={subStyles.planSectionTitle}>{section.title}</Text>
          {section.items.slice(0, 4).map((item, i) => (
            <View key={item.id} style={[subStyles.planItem, i > 0 && subStyles.planItemBorder]}>
              <Text style={subStyles.planItemTitle} numberOfLines={2}>{item.title}</Text>
              {item.reason ? <Text style={subStyles.planItemReason} numberOfLines={1}>{item.reason}</Text> : null}
            </View>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}

function BrainDumpView({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest('/api/brain-dumps', {
        method: 'POST',
        body: JSON.stringify({ raw_input: trimmed }),
      });
      setSubmitted(true);
      setText('');
      setTimeout(onDone, 1200);
    } catch {
      setError('Failed to save — check your connection');
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <View style={subStyles.centered}>
        <Text style={subStyles.successIcon}>✓</Text>
        <Text style={subStyles.successText}>Brain dump saved!</Text>
        <Text style={subStyles.successSub}>AI will process it shortly</Text>
      </View>
    );
  }

  return (
    <View style={subStyles.brainDumpContainer}>
      <TextInput
        style={subStyles.brainDumpInput}
        value={text}
        onChangeText={setText}
        placeholder="Dump whatever is on your mind…"
        placeholderTextColor="#6b7280"
        multiline
        autoFocus
        textAlignVertical="top"
      />
      {error ? <Text style={subStyles.errorText}>{error}</Text> : null}
      <TouchableOpacity
        style={[subStyles.submitBtn, (!text.trim() || submitting) && subStyles.submitBtnDisabled]}
        onPress={handleSubmit}
        disabled={!text.trim() || submitting}
        activeOpacity={0.8}
      >
        {submitting
          ? <ActivityIndicator color="#fff" size="small" />
          : <Text style={subStyles.submitBtnText}>Save Brain Dump</Text>}
      </TouchableOpacity>
    </View>
  );
}

function FocusModeView() {
  const [task, setTask] = useState<{ id: number; title: string; category?: string | null; reason?: string | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const [done, setDone] = useState(false);

  const fetchNextAction = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiRequest<NextActionResponse>('/api/autopilot/next-action');
      setTask({ id: data.task.id, title: data.task.title, category: data.task.category, reason: data.reason });
    } catch {
      // Fallback: top open task
      try {
        const tasksData = await apiRequest<TasksResponse>('/api/tasks');
        const open = tasksData.tasks
          .filter(t => t.status !== 'done' && t.status !== 'cancelled')
          .sort((a, b) => {
            if (a.is_overdue !== b.is_overdue) return a.is_overdue ? -1 : 1;
            return (b.priority ?? 0) - (a.priority ?? 0);
          });
        if (open.length > 0) setTask({ id: open[0].id, title: open[0].title, category: open[0].category });
      } catch {
        // no-op
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchNextAction(); }, [fetchNextAction]);

  async function handleDone() {
    if (!task) return;
    try {
      await apiRequest(`/api/tasks/${task.id}/complete`, { method: 'POST' });
    } catch {
      // best-effort
    }
    setDone(true);
  }

  if (loading) {
    return (
      <View style={subStyles.centered}>
        <ActivityIndicator color="#6366f1" size="large" />
        <Text style={subStyles.loadingText}>Finding your next focus…</Text>
      </View>
    );
  }

  if (done) {
    return (
      <View style={subStyles.centered}>
        <Text style={subStyles.successIcon}>✓</Text>
        <Text style={subStyles.successText}>Task completed!</Text>
        <Text style={subStyles.successSub}>Great work — keep it up</Text>
      </View>
    );
  }

  if (!task) {
    return (
      <View style={subStyles.centered}>
        <Text style={subStyles.emptyText}>No tasks right now — inbox zero!</Text>
      </View>
    );
  }

  return (
    <View style={subStyles.focusContainer}>
      <View style={[subStyles.focusBadge, started && subStyles.focusBadgeActive]}>
        <Text style={subStyles.focusBadgeText}>{started ? 'IN FOCUS' : 'NEXT UP'}</Text>
      </View>
      <Text style={subStyles.focusTitle}>{task.title}</Text>
      {task.category ? <Text style={subStyles.focusMeta}>{task.category}</Text> : null}
      {task.reason ? <Text style={subStyles.focusReason}>{task.reason}</Text> : null}
      <View style={subStyles.focusCtas}>
        {!started ? (
          <TouchableOpacity style={subStyles.focusStartBtn} onPress={() => setStarted(true)} activeOpacity={0.8}>
            <Text style={subStyles.focusStartText}>Start Focus</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={subStyles.focusDoneBtn} onPress={handleDone} activeOpacity={0.8}>
            <Text style={subStyles.focusDoneText}>Mark Done</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity style={subStyles.focusSkipBtn} onPress={fetchNextAction} activeOpacity={0.8}>
          <Text style={subStyles.focusSkipText}>Skip</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

type ActiveView = 'menu' | 'plan' | 'dump' | 'focus';

interface Action {
  id: ActiveView;
  icon: string;
  label: string;
  sublabel: string;
  color: string;
}

const ACTIONS: Action[] = [
  { id: 'plan', icon: '📅', label: 'Plan Day', sublabel: "See today's schedule", color: '#6366f1' },
  { id: 'dump', icon: '🧠', label: 'Brain Dump', sublabel: 'Capture a thought', color: '#10b981' },
  { id: 'focus', icon: '⚡', label: 'Focus Mode', sublabel: 'Work on your next task', color: '#f59e0b' },
];

const VIEW_TITLES: Record<ActiveView, string> = {
  menu: 'Quick Actions',
  plan: 'Plan Day',
  dump: 'Brain Dump',
  focus: 'Focus Mode',
};

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [activeView, setActiveView] = useState<ActiveView>('menu');

  function handleOpen() {
    setActiveView('menu');
    setOpen(true);
  }

  function handleClose() {
    setOpen(false);
    setActiveView('menu');
  }

  function handleAction(id: ActiveView) {
    setActiveView(id);
  }

  function handleBack() {
    setActiveView('menu');
  }

  return (
    <>
      {/* Floating Action Button */}
      <TouchableOpacity style={styles.fab} onPress={handleOpen} activeOpacity={0.85}>
        <Text style={styles.fabIcon}>⚡</Text>
      </TouchableOpacity>

      {/* Palette Modal */}
      <Modal
        visible={open}
        transparent
        animationType="slide"
        onRequestClose={handleClose}
        statusBarTranslucent
      >
        <TouchableWithoutFeedback onPress={handleClose}>
          <View style={styles.backdrop} />
        </TouchableWithoutFeedback>

        <View style={styles.sheet}>
          {/* Header */}
          <View style={styles.sheetHeader}>
            {activeView !== 'menu' ? (
              <TouchableOpacity onPress={handleBack} style={styles.backBtn} activeOpacity={0.7}>
                <Text style={styles.backText}>← Back</Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.backBtn} />
            )}
            <Text style={styles.sheetTitle}>{VIEW_TITLES[activeView]}</Text>
            <TouchableOpacity onPress={handleClose} style={styles.closeBtn} activeOpacity={0.7}>
              <Text style={styles.closeText}>✕</Text>
            </TouchableOpacity>
          </View>

          {/* Content */}
          <View style={styles.sheetContent}>
            {activeView === 'menu' && (
              <View style={styles.menuGrid}>
                {ACTIONS.map(action => (
                  <TouchableOpacity
                    key={action.id}
                    style={styles.menuCard}
                    onPress={() => handleAction(action.id)}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.menuCardIcon}>{action.icon}</Text>
                    <Text style={styles.menuCardLabel}>{action.label}</Text>
                    <Text style={styles.menuCardSub}>{action.sublabel}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
            {activeView === 'plan' && <PlanDayView />}
            {activeView === 'dump' && <BrainDumpView onDone={handleClose} />}
            {activeView === 'focus' && <FocusModeView />}
          </View>
        </View>
      </Modal>
    </>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 20,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#6366f1',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  fabIcon: { fontSize: 22 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' },
  sheet: {
    backgroundColor: '#1f2937',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '75%',
    minHeight: 280,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#374151',
  },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: '#f9fafb' },
  backBtn: { width: 60 },
  backText: { fontSize: 14, color: '#6366f1', fontWeight: '600' },
  closeBtn: { width: 60, alignItems: 'flex-end' },
  closeText: { fontSize: 16, color: '#9ca3af' },
  sheetContent: { flex: 1, padding: 16 },

  menuGrid: { flexDirection: 'row', gap: 10 },
  menuCard: {
    flex: 1,
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  menuCardIcon: { fontSize: 28, marginBottom: 8 },
  menuCardLabel: { fontSize: 13, fontWeight: '700', color: '#f9fafb', marginBottom: 4, textAlign: 'center' },
  menuCardSub: { fontSize: 11, color: '#6b7280', textAlign: 'center' },
});

const subStyles = StyleSheet.create({
  scroll: { flex: 1 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 24 },
  loadingText: { marginTop: 12, color: '#9ca3af', fontSize: 14 },
  errorText: { color: '#ef4444', fontSize: 13, textAlign: 'center', marginBottom: 12 },
  emptyText: { color: '#6b7280', fontSize: 14, textAlign: 'center' },
  retryBtn: { backgroundColor: '#374151', paddingHorizontal: 20, paddingVertical: 8, borderRadius: 8 },
  retryText: { color: '#f9fafb', fontSize: 14, fontWeight: '600' },

  // Plan Day
  planSummary: { fontSize: 15, color: '#f9fafb', fontWeight: '600', marginBottom: 12 },
  aiBadge: { backgroundColor: '#1e1b4b', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, alignSelf: 'flex-start', marginBottom: 12 },
  aiBadgeText: { fontSize: 11, color: '#818cf8', fontWeight: '600' },
  planSection: { marginBottom: 12 },
  planSectionTitle: { fontSize: 11, fontWeight: '700', color: '#6366f1', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 6 },
  planItem: { paddingVertical: 8 },
  planItemBorder: { borderTopWidth: 1, borderTopColor: '#374151' },
  planItemTitle: { fontSize: 14, color: '#f9fafb' },
  planItemReason: { fontSize: 12, color: '#6b7280', marginTop: 2 },

  // Brain Dump
  brainDumpContainer: { flex: 1 },
  brainDumpInput: {
    backgroundColor: '#111827',
    borderRadius: 10,
    padding: 14,
    color: '#f9fafb',
    fontSize: 15,
    minHeight: 120,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#374151',
  },
  submitBtn: { backgroundColor: '#6366f1', borderRadius: 10, paddingVertical: 13, alignItems: 'center' },
  submitBtnDisabled: { opacity: 0.4 },
  submitBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  successIcon: { fontSize: 40, marginBottom: 12 },
  successText: { fontSize: 18, fontWeight: '700', color: '#f9fafb', marginBottom: 6 },
  successSub: { fontSize: 13, color: '#9ca3af' },

  // Focus Mode
  focusContainer: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  focusBadge: { backgroundColor: '#1f2937', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4, marginBottom: 16, borderWidth: 1, borderColor: '#374151' },
  focusBadgeActive: { backgroundColor: '#064e3b', borderColor: '#059669' },
  focusBadgeText: { fontSize: 11, fontWeight: '700', color: '#6b7280', letterSpacing: 1 },
  focusTitle: { fontSize: 20, fontWeight: '700', color: '#f9fafb', textAlign: 'center', marginBottom: 8, lineHeight: 28 },
  focusMeta: { fontSize: 13, color: '#9ca3af', marginBottom: 6 },
  focusReason: { fontSize: 13, color: '#6b7280', textAlign: 'center', marginBottom: 20, paddingHorizontal: 16 },
  focusCtas: { flexDirection: 'row', gap: 10, marginTop: 8 },
  focusStartBtn: { backgroundColor: '#6366f1', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 24 },
  focusStartText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  focusDoneBtn: { backgroundColor: '#059669', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 24 },
  focusDoneText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  focusSkipBtn: { backgroundColor: '#374151', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 20 },
  focusSkipText: { color: '#9ca3af', fontSize: 15, fontWeight: '600' },
});
