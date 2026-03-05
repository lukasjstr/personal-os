import React from 'react';
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
import { useApi } from '../hooks/useApi';

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

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  todo: { bg: '#374151', text: '#d1d5db' },
  in_progress: { bg: '#1e3a5f', text: '#60a5fa' },
  done: { bg: '#14532d', text: '#4ade80' },
  cancelled: { bg: '#1f2937', text: '#6b7280' },
};

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

function TaskItem({ item }: { item: Task }) {
  return (
    <View style={styles.taskCard}>
      <View style={styles.taskHeader}>
        <Text style={styles.taskTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <StatusChip status={item.status} />
      </View>
      <View style={styles.taskMeta}>
        {item.category && (
          <Text style={styles.metaText}>{item.category}</Text>
        )}
        {item.due_date && (
          <Text style={[styles.metaText, item.is_overdue && styles.overdueText]}>
            {item.is_overdue ? 'Overdue · ' : ''}{item.due_date}
          </Text>
        )}
      </View>
    </View>
  );
}

export default function TasksScreen() {
  const { data, loading, error, refetch } = useApi<TasksResponse>('/api/tasks');
  const tasks = data?.tasks ?? [];

  if (loading && tasks.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      </SafeAreaView>
    );
  }

  if (error && tasks.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity onPress={refetch} style={styles.retryButton}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <FlatList
        data={tasks}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => <TaskItem item={item} />}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refetch} tintColor="#6366f1" />
        }
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>No open tasks — you're all caught up!</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  list: { padding: 16, gap: 10, flexGrow: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 48 },
  taskCard: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 14,
  },
  taskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  taskTitle: { flex: 1, fontSize: 15, fontWeight: '600', color: '#f9fafb' },
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  chipText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  taskMeta: { flexDirection: 'row', gap: 12, marginTop: 6 },
  metaText: { fontSize: 12, color: '#9ca3af' },
  overdueText: { color: '#f87171' },
  errorText: { color: '#f87171', fontSize: 14, textAlign: 'center', marginBottom: 12 },
  emptyText: { color: '#6b7280', fontSize: 14 },
  retryButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryText: { color: '#f9fafb', fontWeight: '600' },
});
