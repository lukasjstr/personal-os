import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApi } from '../hooks/useApi';
import { apiRequest } from '../lib/apiClient';

interface SplitExercise {
  name: string;
  sets?: number;
  reps?: string;
  target_weight?: number;
}

interface FitnessSplit {
  id: number;
  name: string;
  exercises: SplitExercise[];
  day_of_week: number | null;
  order_in_rotation: number | null;
  workout_count: number;
  last_used: string | null;
  is_next: boolean;
}

interface SplitsResponse {
  splits: FitnessSplit[];
  next_split_id: number | null;
}

interface WorkoutSession {
  date: string;
  exercises: {
    exercise: string;
    weight: number | null;
    reps: number | null;
    sets: number | null;
    duration_min: number | null;
  }[];
}

interface SummaryResponse {
  total_workout_days: number;
  last_sessions: WorkoutSession[];
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const diffMs = today.setHours(0, 0, 0, 0) - d.setHours(0, 0, 0, 0);
  const diffDays = Math.round(diffMs / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function ExerciseTag({ ex }: { ex: SplitExercise }) {
  const parts: string[] = [];
  if (ex.sets) parts.push(`${ex.sets}x`);
  if (ex.reps) parts.push(ex.reps);
  if (ex.target_weight) parts.push(`${ex.target_weight}kg`);
  return (
    <View style={styles.exerciseTag}>
      <Text style={styles.exerciseTagText}>
        {ex.name}
        {parts.length > 0 ? `  ${parts.join(' ')}` : ''}
      </Text>
    </View>
  );
}

function TodaySplitCard({
  split,
  onMarkDone,
  onSkip,
  actionLoading,
  actionDone,
}: {
  split: FitnessSplit;
  onMarkDone: () => void;
  onSkip: () => void;
  actionLoading: boolean;
  actionDone: 'done' | 'skipped' | null;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardLabel}>TODAY'S WORKOUT</Text>
        {split.workout_count > 0 && (
          <Text style={styles.cardMeta}>{split.workout_count}x done</Text>
        )}
      </View>
      <Text style={styles.splitName}>{split.name}</Text>
      {split.last_used && (
        <Text style={styles.lastUsed}>Last: {formatDate(split.last_used)}</Text>
      )}
      <View style={styles.exerciseTags}>
        {split.exercises.map((ex, i) => (
          <ExerciseTag key={i} ex={ex} />
        ))}
      </View>
      {actionDone ? (
        <View style={styles.doneBanner}>
          <Text style={styles.doneBannerText}>
            {actionDone === 'done' ? 'Workout logged!' : 'Skipped for today'}
          </Text>
        </View>
      ) : (
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnPrimary]}
            onPress={onMarkDone}
            disabled={actionLoading}
            activeOpacity={0.8}
          >
            {actionLoading ? (
              <ActivityIndicator size="small" color="#111827" />
            ) : (
              <Text style={styles.btnPrimaryText}>Mark workout done</Text>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnSecondary]}
            onPress={onSkip}
            disabled={actionLoading}
            activeOpacity={0.8}
          >
            <Text style={styles.btnSecondaryText}>Skipped today</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

function RecentSessionsCard({ sessions }: { sessions: WorkoutSession[] }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardLabel}>RECENT WORKOUTS</Text>
      {sessions.map((session, i) => (
        <View key={i} style={[styles.sessionRow, i > 0 && styles.sessionRowBorder]}>
          <Text style={styles.sessionDate}>{formatDate(session.date)}</Text>
          <Text style={styles.sessionExercises} numberOfLines={1}>
            {session.exercises.map(e => e.exercise).join(', ')}
          </Text>
        </View>
      ))}
    </View>
  );
}

function EmptyState() {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyIcon}>🏋️</Text>
      <Text style={styles.emptyTitle}>No splits set up yet</Text>
      <Text style={styles.emptyHint}>
        Open the Telegram bot and use /fitness to create your first workout split. It will appear
        here once saved.
      </Text>
    </View>
  );
}

export default function FitnessScreen() {
  const {
    data: splitsData,
    loading: splitsLoading,
    error: splitsError,
    refetch: refetchSplits,
  } = useApi<SplitsResponse>('/api/fitness/splits');

  const {
    data: summaryData,
    loading: summaryLoading,
    error: summaryError,
    refetch: refetchSummary,
  } = useApi<SummaryResponse>('/api/fitness/summary');

  const [actionLoading, setActionLoading] = useState(false);
  const [actionDone, setActionDone] = useState<'done' | 'skipped' | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const nextSplit = splitsData?.splits.find(s => s.is_next) ?? splitsData?.splits[0] ?? null;
  const recentSessions = (summaryData?.last_sessions ?? []).slice(0, 5);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    setActionDone(null);
    refetchSplits();
    refetchSummary();
    setTimeout(() => setRefreshing(false), 800);
  }, [refetchSplits, refetchSummary]);

  const handleMarkDone = useCallback(async () => {
    if (!nextSplit) return;
    setActionLoading(true);
    try {
      await apiRequest('/api/logs', {
        method: 'POST',
        body: JSON.stringify({
          log_type: 'workout',
          data: {
            split_id: nextSplit.id,
            split_name: nextSplit.name,
            status: 'completed',
          },
        }),
      });
      setActionDone('done');
    } catch {
      Alert.alert('Error', 'Could not log workout. Please try again.');
    } finally {
      setActionLoading(false);
    }
  }, [nextSplit]);

  const handleSkip = useCallback(async () => {
    if (!nextSplit) return;
    setActionLoading(true);
    try {
      await apiRequest('/api/logs', {
        method: 'POST',
        body: JSON.stringify({
          log_type: 'workout',
          data: {
            split_id: nextSplit.id,
            split_name: nextSplit.name,
            status: 'skipped',
          },
        }),
      });
      setActionDone('skipped');
    } catch {
      Alert.alert('Error', 'Could not log skip. Please try again.');
    } finally {
      setActionLoading(false);
    }
  }, [nextSplit]);

  const isLoading = splitsLoading || summaryLoading;
  const error = splitsError ?? summaryError;
  const hasSplits = (splitsData?.splits.length ?? 0) > 0;

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor="#6b7280"
          />
        }
      >
        <Text style={styles.title}>Fitness</Text>

        {isLoading && !splitsData && !summaryData ? (
          <ActivityIndicator size="large" color="#6b7280" style={styles.loader} />
        ) : error && !splitsData && !summaryData ? (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity onPress={handleRefresh} style={styles.retryBtn}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : !hasSplits ? (
          <EmptyState />
        ) : (
          <>
            {nextSplit && (
              <TodaySplitCard
                split={nextSplit}
                onMarkDone={handleMarkDone}
                onSkip={handleSkip}
                actionLoading={actionLoading}
                actionDone={actionDone}
              />
            )}
            {recentSessions.length > 0 && (
              <RecentSessionsCard sessions={recentSessions} />
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  scroll: { padding: 16, gap: 16 },
  title: { fontSize: 28, fontWeight: '700', color: '#f9fafb', marginBottom: 4 },
  loader: { marginTop: 60 },

  errorBox: { alignItems: 'center', gap: 12, marginTop: 40 },
  errorText: { color: '#ef4444', fontSize: 14, textAlign: 'center' },
  retryBtn: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: '#1f2937',
    borderRadius: 8,
  },
  retryText: { color: '#9ca3af', fontSize: 14 },

  card: {
    backgroundColor: '#1f2937',
    borderRadius: 12,
    padding: 16,
    gap: 10,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardLabel: { fontSize: 11, fontWeight: '600', color: '#6b7280', letterSpacing: 1 },
  cardMeta: { fontSize: 12, color: '#4b5563' },

  splitName: { fontSize: 20, fontWeight: '700', color: '#f9fafb' },
  lastUsed: { fontSize: 12, color: '#6b7280' },

  exerciseTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  exerciseTag: {
    backgroundColor: '#374151',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  exerciseTagText: { fontSize: 13, color: '#d1d5db' },

  actionRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
  btn: { flex: 1, borderRadius: 8, paddingVertical: 11, alignItems: 'center' },
  btnPrimary: { backgroundColor: '#10b981' },
  btnPrimaryText: { fontSize: 14, fontWeight: '600', color: '#111827' },
  btnSecondary: { backgroundColor: '#374151' },
  btnSecondaryText: { fontSize: 14, fontWeight: '500', color: '#9ca3af' },

  doneBanner: {
    backgroundColor: '#064e3b',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginTop: 4,
  },
  doneBannerText: { fontSize: 14, fontWeight: '600', color: '#6ee7b7' },

  sessionRow: { paddingVertical: 8 },
  sessionRowBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#374151' },
  sessionDate: { fontSize: 12, color: '#6b7280', marginBottom: 2 },
  sessionExercises: { fontSize: 14, color: '#d1d5db' },

  emptyState: { alignItems: 'center', gap: 12, marginTop: 60, paddingHorizontal: 24 },
  emptyIcon: { fontSize: 48 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#f9fafb' },
  emptyHint: { fontSize: 14, color: '#6b7280', textAlign: 'center', lineHeight: 22 },
});
