import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiRequest } from '../lib/apiClient';
import { useApi } from '../hooks/useApi';

interface ObjectiveImpact {
  objective_id: number;
  objective_title: string;
  impact_score: number;
}

interface Routine {
  id: number;
  title: string;
  description: string | null;
  time_of_day: string;
  frequency_human: string | null;
  sort_order: number;
  completed_today: boolean;
  objective_impacts?: ObjectiveImpact[];
}

interface RoutinesResponse {
  routines: Routine[];
}

type TimeOfDay = 'morning' | 'midday' | 'evening' | 'anytime';

const TIME_SECTIONS: { key: TimeOfDay; label: string; icon: string }[] = [
  { key: 'morning', label: 'Morning', icon: '☀️' },
  { key: 'midday', label: 'Midday', icon: '🌤' },
  { key: 'evening', label: 'Evening', icon: '🌙' },
  { key: 'anytime', label: 'Anytime', icon: '🔄' },
];

function normalizeTimeOfDay(raw: string): TimeOfDay {
  const v = raw?.toLowerCase();
  if (v === 'morning' || v === 'midday' || v === 'evening') return v;
  return 'anytime';
}

function ProgressBar({ completed, total }: { completed: number; total: number }) {
  const pct = total > 0 ? completed / total : 0;
  return (
    <View style={styles.progressBg}>
      <View style={[styles.progressFill, { flex: pct }]} />
      <View style={{ flex: 1 - pct }} />
    </View>
  );
}

function RoutineRow({
  routine,
  onToggle,
  toggling,
}: {
  routine: Routine;
  onToggle: (id: number) => void;
  toggling: boolean;
}) {
  return (
    <View style={[styles.row, routine.completed_today && styles.rowDone]}>
      <View style={styles.rowContent}>
        <Text
          style={[styles.rowTitle, routine.completed_today && styles.rowTitleDone]}
          numberOfLines={1}
        >
          {routine.title}
        </Text>
        {routine.frequency_human ? (
          <Text style={styles.rowMeta}>{routine.frequency_human}</Text>
        ) : null}
        {routine.objective_impacts && routine.objective_impacts.length > 0 ? (
          <View style={styles.impactRow}>
            {routine.objective_impacts.slice(0, 2).map(oi => (
              <View key={oi.objective_id} style={styles.impactBadge}>
                <Text style={styles.impactBadgeText} numberOfLines={1}>
                  {'\u25CF'.repeat(oi.impact_score)} {oi.objective_title}
                </Text>
              </View>
            ))}
            {routine.objective_impacts.length > 2 ? (
              <View style={styles.impactBadge}>
                <Text style={styles.impactBadgeText}>+{routine.objective_impacts.length - 2}</Text>
              </View>
            ) : null}
          </View>
        ) : null}
      </View>
      <TouchableOpacity
        style={[styles.checkBtn, routine.completed_today && styles.checkBtnDone]}
        onPress={() => onToggle(routine.id)}
        disabled={toggling || routine.completed_today}
        activeOpacity={0.7}
      >
        {toggling ? (
          <ActivityIndicator size="small" color="#4ade80" />
        ) : (
          <Text style={styles.checkIcon}>{routine.completed_today ? '✓' : '○'}</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

export default function RoutinesScreen() {
  const { data, loading, error, refetch } = useApi<RoutinesResponse>('/routines');
  const [toggling, setToggling] = useState<Set<number>>(new Set());
  const [localDone, setLocalDone] = useState<Set<number>>(new Set());

  const handleToggle = useCallback(
    async (id: number) => {
      setToggling(prev => new Set(prev).add(id));
      setLocalDone(prev => new Set(prev).add(id));
      try {
        await apiRequest(`/routines/${id}/complete`, { method: 'POST' });
        refetch();
      } catch {
        // Optimistic update stays — server may already have it or network is flaky
      } finally {
        setToggling(prev => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [refetch],
  );

  const routines: Routine[] = (data?.routines ?? []).map(r => ({
    ...r,
    completed_today: r.completed_today || localDone.has(r.id),
  }));

  const totalCount = routines.length;
  const doneCount = routines.filter(r => r.completed_today).length;

  const grouped = TIME_SECTIONS.map(section => ({
    ...section,
    items: routines.filter(r => normalizeTimeOfDay(r.time_of_day) === section.key),
  })).filter(s => s.items.length > 0);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={loading && !!data}
            onRefresh={refetch}
            tintColor="#6b7280"
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Routines</Text>
          {!loading && !error && totalCount > 0 && (
            <Text style={styles.progressLabel}>
              {doneCount}/{totalCount} today
            </Text>
          )}
        </View>

        {/* Progress bar */}
        {!loading && !error && totalCount > 0 && (
          <View style={styles.progressContainer}>
            <ProgressBar completed={doneCount} total={totalCount} />
          </View>
        )}

        {/* Loading */}
        {loading && !data && (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#6b7280" />
          </View>
        )}

        {/* Error */}
        {error && (
          <View style={styles.center}>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={refetch}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Empty */}
        {!loading && !error && totalCount === 0 && (
          <View style={styles.center}>
            <Text style={styles.emptyText}>No routines yet.</Text>
            <Text style={styles.emptyHint}>Add routines via the Telegram bot.</Text>
          </View>
        )}

        {/* Sections */}
        {grouped.map(section => (
          <View key={section.key} style={styles.section}>
            <Text style={styles.sectionHeader}>
              {section.icon}  {section.label}
            </Text>
            {section.items.map(routine => (
              <RoutineRow
                key={routine.id}
                routine={routine}
                onToggle={handleToggle}
                toggling={toggling.has(routine.id)}
              />
            ))}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  scroll: { padding: 16, paddingTop: 8, flexGrow: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  title: { fontSize: 22, fontWeight: '700', color: '#f9fafb' },
  progressLabel: { fontSize: 14, color: '#9ca3af' },
  progressContainer: { marginBottom: 20 },
  progressBg: {
    flexDirection: 'row',
    height: 6,
    borderRadius: 3,
    backgroundColor: '#374151',
    overflow: 'hidden',
  },
  progressFill: { backgroundColor: '#4ade80', borderRadius: 3 },
  section: { marginBottom: 20 },
  sectionHeader: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1f2937',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 8,
  },
  rowDone: { backgroundColor: '#14532d22' },
  rowContent: { flex: 1, marginRight: 10 },
  rowTitle: { fontSize: 15, fontWeight: '500', color: '#f3f4f6' },
  rowTitleDone: { color: '#6b7280', textDecorationLine: 'line-through' },
  rowMeta: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  checkBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#374151',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkBtnDone: { backgroundColor: '#14532d' },
  checkIcon: { fontSize: 16, color: '#4ade80' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  errorText: { color: '#f87171', fontSize: 14, textAlign: 'center', marginBottom: 12 },
  retryBtn: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: '#374151',
    borderRadius: 8,
  },
  retryText: { color: '#d1d5db', fontSize: 14 },
  emptyText: { fontSize: 16, color: '#9ca3af', marginBottom: 6 },
  emptyHint: { fontSize: 13, color: '#4b5563' },
  impactRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 5 },
  impactBadge: {
    backgroundColor: '#1e3a5f',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    maxWidth: 180,
  },
  impactBadgeText: { fontSize: 10, color: '#60a5fa' },
});
