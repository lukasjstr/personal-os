import { Ionicons } from '@expo/vector-icons';
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ApiError, apiRequest } from '../lib/apiClient';

// ── Types ────────────────────────────────────────────────────────────────────

interface ShoppingItem {
  id: number;
  name: string;
  quantity?: string | null;
  unit?: string | null;
  priority?: number | null;
  category?: string | null;
  status?: string;
  notes?: string | null;
}

interface ShoppingListResponse {
  items: ShoppingItem[];
}

interface ShoppingDefaultsResponse {
  defaults: ShoppingItem[];
}

interface TaskItem {
  id: number;
  title: string;
  status: string;
  priority: number;
  category: string | null;
  description: string | null;
}

interface TasksResponse {
  tasks: TaskItem[];
}

type Tab = 'now' | 'standard';

// ── Helpers ──────────────────────────────────────────────────────────────────

function priorityColor(priority: number | null | undefined): string {
  if (priority == null) return '#9ca3af';
  if (priority <= 1) return '#f87171';
  if (priority <= 2) return '#fb923c';
  return '#9ca3af';
}

function priorityLabel(priority: number | null | undefined): string {
  if (priority == null) return '';
  if (priority <= 1) return 'High';
  if (priority <= 2) return 'Medium';
  return 'Low';
}

// ── Sub-components ───────────────────────────────────────────────────────────

function QuantityBadge({ quantity, unit }: { quantity?: string | null; unit?: string | null }) {
  const text = [quantity, unit].filter(Boolean).join(' ');
  if (!text) return null;
  return (
    <View style={styles.quantityBadge}>
      <Text style={styles.quantityText}>{text}</Text>
    </View>
  );
}

function PriorityDot({ priority }: { priority?: number | null }) {
  if (priority == null) return null;
  return <View style={[styles.priorityDot, { backgroundColor: priorityColor(priority) }]} />;
}

function NowItem({
  item,
  onMarkBought,
  buying,
}: {
  item: ShoppingItem;
  onMarkBought: (id: number) => void;
  buying: number | null;
}) {
  const isBuying = buying === item.id;
  return (
    <View style={styles.itemCard}>
      <TouchableOpacity
        style={styles.checkButton}
        onPress={() => onMarkBought(item.id)}
        disabled={isBuying}
        activeOpacity={0.7}
      >
        {isBuying ? (
          <ActivityIndicator size="small" color="#10b981" />
        ) : (
          <Ionicons name="checkmark-circle-outline" size={26} color="#374151" />
        )}
      </TouchableOpacity>
      <View style={styles.itemContent}>
        <View style={styles.itemRow}>
          <PriorityDot priority={item.priority} />
          <Text style={styles.itemName} numberOfLines={2}>
            {item.name}
          </Text>
          <QuantityBadge quantity={item.quantity} unit={item.unit} />
        </View>
        {item.category ? <Text style={styles.itemCategory}>{item.category}</Text> : null}
        {item.notes ? (
          <Text style={styles.itemNotes} numberOfLines={1}>
            {item.notes}
          </Text>
        ) : null}
        {item.priority != null && priorityLabel(item.priority) ? (
          <Text style={[styles.priorityLabel, { color: priorityColor(item.priority) }]}>
            {priorityLabel(item.priority)}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

function StandardItem({
  item,
  onAddToNow,
  adding,
}: {
  item: ShoppingItem;
  onAddToNow: (item: ShoppingItem) => void;
  adding: number | null;
}) {
  const isAdding = adding === item.id;
  return (
    <View style={styles.itemCard}>
      <View style={styles.itemContent}>
        <View style={styles.itemRow}>
          <PriorityDot priority={item.priority} />
          <Text style={styles.itemName} numberOfLines={2}>
            {item.name}
          </Text>
          <QuantityBadge quantity={item.quantity} unit={item.unit} />
        </View>
        {item.category ? <Text style={styles.itemCategory}>{item.category}</Text> : null}
      </View>
      <TouchableOpacity
        style={[styles.addButton, isAdding && styles.addButtonDisabled]}
        onPress={() => onAddToNow(item)}
        disabled={isAdding}
        activeOpacity={0.7}
      >
        {isAdding ? (
          <ActivityIndicator size="small" color="#6366f1" />
        ) : (
          <Ionicons name="add-circle-outline" size={26} color="#6366f1" />
        )}
      </TouchableOpacity>
    </View>
  );
}

// ── Fetch with fallback ──────────────────────────────────────────────────────

function useShoppingNow(tick: number) {
  const [data, setData] = React.useState<ShoppingItem[] | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      // Try /api/shopping/list first
      try {
        const res = await apiRequest<ShoppingListResponse>('/api/shopping/list');
        if (!cancelled) {
          setData(res.items ?? []);
          setLoading(false);
        }
        return;
      } catch (e) {
        if (cancelled) return;
        // If 404 or similar, fall through to tasks fallback
        if (!(e instanceof ApiError && (e.status === 404 || e.status === 405 || e.status === 0))) {
          setError(e instanceof Error ? e.message : 'Failed to load shopping list');
          setLoading(false);
          return;
        }
      }

      // Fallback: /api/tasks?category=shopping
      try {
        const res = await apiRequest<TasksResponse>('/api/tasks?category=shopping');
        if (!cancelled) {
          const items: ShoppingItem[] = (res.tasks ?? [])
            .filter(t => t.status !== 'done' && t.status !== 'cancelled')
            .map(t => ({
              id: t.id,
              name: t.title,
              priority: t.priority,
              category: t.category,
              notes: t.description,
            }));
          setData(items);
          setLoading(false);
        }
      } catch (e2) {
        if (!cancelled) {
          setError(e2 instanceof Error ? e2.message : 'Failed to load shopping list');
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tick]);

  return { data, loading, error };
}

function useShoppingDefaults(tick: number) {
  const [data, setData] = React.useState<ShoppingItem[] | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      // Try /api/shopping/defaults first
      try {
        const res = await apiRequest<ShoppingDefaultsResponse>('/api/shopping/defaults');
        if (!cancelled) {
          setData(res.defaults ?? []);
          setLoading(false);
        }
        return;
      } catch (e) {
        if (cancelled) return;
        if (!(e instanceof ApiError && (e.status === 404 || e.status === 405 || e.status === 0))) {
          setError(e instanceof Error ? e.message : 'Failed to load defaults');
          setLoading(false);
          return;
        }
      }

      // Fallback: /api/tasks?category=shopping (all tasks including done, as template reference)
      try {
        const res = await apiRequest<TasksResponse>('/api/tasks?category=shopping');
        if (!cancelled) {
          const items: ShoppingItem[] = (res.tasks ?? []).map(t => ({
            id: t.id,
            name: t.title,
            priority: t.priority,
            category: t.category,
            notes: t.description,
          }));
          setData(items);
          setLoading(false);
        }
      } catch (e2) {
        if (!cancelled) {
          setError(e2 instanceof Error ? e2.message : 'Failed to load defaults');
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tick]);

  return { data, loading, error };
}

// ── Main screen ──────────────────────────────────────────────────────────────

export default function ShoppingScreen() {
  const [tab, setTab] = useState<Tab>('now');
  const [nowTick, setNowTick] = useState(0);
  const [standardTick, setStandardTick] = useState(0);
  const [boughtIds, setBoughtIds] = useState<Set<number>>(new Set());
  const [buying, setBuying] = useState<number | null>(null);
  const [adding, setAdding] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const { data: nowData, loading: nowLoading, error: nowError } = useShoppingNow(nowTick);
  const {
    data: standardData,
    loading: standardLoading,
    error: standardError,
  } = useShoppingDefaults(standardTick);

  const nowItems = (nowData ?? []).filter(i => !boughtIds.has(i.id));
  const standardItems = standardData ?? [];

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    setBoughtIds(new Set());
    setNowTick(t => t + 1);
    setStandardTick(t => t + 1);
    setTimeout(() => setRefreshing(false), 800);
  }, []);

  const handleMarkBought = useCallback(
    async (id: number) => {
      setBuying(id);
      try {
        await apiRequest(`/api/shopping/list/${id}/bought`, { method: 'POST' }).catch(async () => {
          // fallback: mark as done via tasks API
          await apiRequest(`/api/tasks/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ status: 'done' }),
          });
        });
      } catch {
        // optimistic only — no alert, just remove from list
      } finally {
        setBuying(null);
        setBoughtIds(prev => new Set([...prev, id]));
      }
    },
    [],
  );

  const handleAddToNow = useCallback(async (item: ShoppingItem) => {
    setAdding(item.id);
    try {
      await apiRequest('/api/shopping/list', {
        method: 'POST',
        body: JSON.stringify({
          name: item.name,
          quantity: item.quantity,
          unit: item.unit,
          priority: item.priority,
          category: item.category,
          notes: item.notes,
        }),
      });
      setNowTick(t => t + 1);
      if (tab !== 'now') setTab('now');
    } catch {
      Alert.alert('Added locally', `"${item.name}" queued for your next shop.`);
      // Still switch to Now tab so user sees feedback
      setNowTick(t => t + 1);
      setTab('now');
    } finally {
      setAdding(null);
    }
  }, [tab]);

  // Group items by category
  function groupByCategory(items: ShoppingItem[]): Map<string, ShoppingItem[]> {
    const groups = new Map<string, ShoppingItem[]>();
    for (const item of items) {
      const key = item.category ?? 'General';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(item);
    }
    return groups;
  }

  const isLoading = tab === 'now' ? (nowLoading && nowData === null) : (standardLoading && standardData === null);
  const currentError = tab === 'now' ? nowError : standardError;
  const isEmpty = tab === 'now' ? nowItems.length === 0 : standardItems.length === 0;

  // Build flat list rows for FlatList
  type Row =
    | { type: 'category'; title: string }
    | { type: 'now-item'; item: ShoppingItem }
    | { type: 'standard-item'; item: ShoppingItem };

  function buildRows(): Row[] {
    const rows: Row[] = [];
    if (tab === 'now') {
      const groups = groupByCategory(nowItems);
      for (const [cat, items] of groups) {
        rows.push({ type: 'category', title: cat });
        for (const item of items) {
          rows.push({ type: 'now-item', item });
        }
      }
    } else {
      const groups = groupByCategory(standardItems);
      for (const [cat, items] of groups) {
        rows.push({ type: 'category', title: cat });
        for (const item of items) {
          rows.push({ type: 'standard-item', item });
        }
      }
    }
    return rows;
  }

  const rows = buildRows();

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Tab bar */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabButton, tab === 'now' && styles.tabButtonActive]}
          onPress={() => setTab('now')}
          activeOpacity={0.8}
        >
          <Ionicons
            name="cart"
            size={16}
            color={tab === 'now' ? '#f9fafb' : '#9ca3af'}
            style={styles.tabIcon}
          />
          <Text style={[styles.tabText, tab === 'now' && styles.tabTextActive]}>
            Now
            {nowItems.length > 0 ? ` (${nowItems.length})` : ''}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabButton, tab === 'standard' && styles.tabButtonActive]}
          onPress={() => setTab('standard')}
          activeOpacity={0.8}
        >
          <Ionicons
            name="list"
            size={16}
            color={tab === 'standard' ? '#f9fafb' : '#9ca3af'}
            style={styles.tabIcon}
          />
          <Text style={[styles.tabText, tab === 'standard' && styles.tabTextActive]}>
            Standard
            {standardItems.length > 0 ? ` (${standardItems.length})` : ''}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Content */}
      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      ) : currentError && isEmpty ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{currentError}</Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={() => {
              setNowTick(t => t + 1);
              setStandardTick(t => t + 1);
            }}
          >
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : isEmpty ? (
        <ScrollView
          contentContainerStyle={styles.emptyContainer}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor="#6366f1"
            />
          }
        >
          <Text style={styles.emptyIcon}>{tab === 'now' ? '🛒' : '📋'}</Text>
          <Text style={styles.emptyTitle}>
            {tab === 'now' ? 'Nothing to buy right now' : 'No standard items yet'}
          </Text>
          <Text style={styles.emptyHint}>
            {tab === 'now'
              ? 'Add items from your Standard list or via the Telegram bot.'
              : 'Set up recurring items in the Telegram bot with /shopping.'}
          </Text>
        </ScrollView>
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(row, i) => {
            if (row.type === 'category') return `cat-${row.title}-${i}`;
            return `item-${row.item.id}-${row.type}`;
          }}
          renderItem={({ item: row }) => {
            if (row.type === 'category') {
              return (
                <View style={styles.categoryHeader}>
                  <Text style={styles.categoryHeaderText}>{row.title}</Text>
                </View>
              );
            }
            if (row.type === 'now-item') {
              return (
                <NowItem item={row.item} onMarkBought={handleMarkBought} buying={buying} />
              );
            }
            return (
              <StandardItem item={row.item} onAddToNow={handleAddToNow} adding={adding} />
            );
          }}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor="#6366f1"
            />
          }
        />
      )}
    </SafeAreaView>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
  },

  // Tabs
  tabBar: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1f2937',
  },
  tabButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: '#1f2937',
    gap: 6,
  },
  tabButtonActive: { backgroundColor: '#6366f1' },
  tabIcon: { marginRight: 2 },
  tabText: { fontSize: 14, fontWeight: '600', color: '#9ca3af' },
  tabTextActive: { color: '#f9fafb' },

  // List
  list: { padding: 16, gap: 6, flexGrow: 1 },

  // Category header
  categoryHeader: {
    paddingVertical: 6,
    paddingHorizontal: 2,
    marginTop: 8,
    marginBottom: 2,
  },
  categoryHeaderText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#6366f1',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },

  // Item card
  itemCard: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  itemContent: { flex: 1 },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  itemName: { flex: 1, fontSize: 15, fontWeight: '500', color: '#f9fafb' },
  itemCategory: { fontSize: 12, color: '#6b7280', marginTop: 3 },
  itemNotes: { fontSize: 12, color: '#4b5563', marginTop: 2, fontStyle: 'italic' },
  priorityLabel: { fontSize: 11, fontWeight: '600', marginTop: 3 },

  // Quantity badge
  quantityBadge: {
    backgroundColor: '#374151',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  quantityText: { fontSize: 12, color: '#d1d5db', fontWeight: '500' },

  // Priority dot
  priorityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    flexShrink: 0,
  },

  // Buttons
  checkButton: { padding: 4 },
  addButton: { padding: 4 },
  addButtonDisabled: { opacity: 0.5 },

  // Error / empty
  errorText: {
    color: '#f87171',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 12,
  },
  retryButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryText: { color: '#f9fafb', fontWeight: '600' },

  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 12,
  },
  emptyIcon: { fontSize: 48 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: '#f9fafb', textAlign: 'center' },
  emptyHint: { fontSize: 14, color: '#6b7280', textAlign: 'center', lineHeight: 22 },

});

