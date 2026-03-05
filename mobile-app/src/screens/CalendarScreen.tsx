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

interface CalendarEvent {
  id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string | null;
  all_day: boolean;
  event_type: string | null;
}

interface CalendarResponse {
  events: CalendarEvent[];
}

function formatEventTime(startIso: string, endIso: string | null, allDay: boolean): string {
  const start = new Date(startIso);
  if (allDay) {
    return start.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  }
  const dateStr = start.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  const timeStr = start.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  if (endIso) {
    const end = new Date(endIso);
    const endTime = end.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    return `${dateStr}  ${timeStr} – ${endTime}`;
  }
  return `${dateStr}  ${timeStr}`;
}

function EventItem({ item }: { item: CalendarEvent }) {
  const timeLabel = formatEventTime(item.start_time, item.end_time, item.all_day);
  return (
    <View style={styles.eventCard}>
      <View style={styles.eventDot} />
      <View style={styles.eventBody}>
        <Text style={styles.eventTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={styles.eventTime}>{timeLabel}</Text>
        {item.event_type && (
          <Text style={styles.eventType}>{item.event_type}</Text>
        )}
      </View>
    </View>
  );
}

export default function CalendarScreen() {
  const { data, loading, error, refetch } = useApi<CalendarResponse>('/api/calendar');
  const events = data?.events ?? [];

  if (loading && events.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      </SafeAreaView>
    );
  }

  if (error && events.length === 0) {
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
        data={events}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => <EventItem item={item} />}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refetch} tintColor="#6366f1" />
        }
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>No upcoming events in the next 30 days.</Text>
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
  eventTime: { fontSize: 12, color: '#9ca3af' },
  eventType: { fontSize: 11, color: '#6b7280', marginTop: 4, textTransform: 'capitalize' },
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
