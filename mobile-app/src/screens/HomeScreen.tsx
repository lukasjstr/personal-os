import React from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useApi } from '../hooks/useApi';

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

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

export default function HomeScreen() {
  const health = useApi<HealthResponse>('/health');
  const dashboard = useApi<DashboardResponse>('/api/dashboard');

  const isLoading = health.loading || dashboard.loading;
  const error = dashboard.error;

  function handleRefresh() {
    health.refetch();
    dashboard.refetch();
  }

  const stats = dashboard.data?.stats;
  const user = dashboard.data?.user;
  const apiOnline = !health.error && health.data?.status === 'ok';

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={handleRefresh} tintColor="#6366f1" />
        }
      >
        <View style={styles.header}>
          <Text style={styles.greeting}>
            {user ? `Hey, ${user.first_name}` : 'Personal OS'}
          </Text>
          <View style={[styles.statusBadge, apiOnline ? styles.statusOnline : styles.statusOffline]}>
            <Text style={styles.statusText}>{apiOnline ? 'Online' : 'Offline'}</Text>
          </View>
        </View>

        {isLoading && !stats && (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#6366f1" />
          </View>
        )}

        {!isLoading && error && !stats && (
          <View style={styles.center}>
            <Text style={styles.errorText}>{error}</Text>
            <Text style={styles.retryHint} onPress={handleRefresh}>
              Tap to retry
            </Text>
          </View>
        )}

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
                  {
                    width: `${Math.min(100, (stats.xp_progress / stats.xp_to_next) * 100)}%`,
                  },
                ]}
              />
            </View>

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

        {!stats && !isLoading && !error && (
          <View style={styles.center}>
            <Text style={styles.emptyText}>No dashboard data available.</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

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
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusOnline: { backgroundColor: '#14532d' },
  statusOffline: { backgroundColor: '#7f1d1d' },
  statusText: { fontSize: 12, color: '#f9fafb', fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 48 },
  errorText: { color: '#f87171', fontSize: 14, textAlign: 'center', marginBottom: 8 },
  retryHint: { color: '#6366f1', fontSize: 14 },
  emptyText: { color: '#6b7280', fontSize: 14 },
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
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
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
});
