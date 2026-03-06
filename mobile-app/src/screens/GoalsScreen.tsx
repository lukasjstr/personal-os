import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

// Minimal CORE-8 screen: proposal drafts list + create + accept/reject.
// Keeps dependencies minimal; uses fetch directly.

type ProposalDraft = {
  id: number;
  source_text: string;
  draft_payload: any;
  status: string;
  created_at: string;
};

const API_URL = process.env.EXPO_PUBLIC_API_URL;

async function apiFetch(path: string, init?: RequestInit) {
  if (!API_URL) throw new Error('EXPO_PUBLIC_API_URL not set');
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export default function GoalsScreen() {
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<ProposalDraft[]>([]);
  const [sourceText, setSourceText] = useState('');

  const sorted = useMemo(() => drafts.slice().sort((a, b) => b.id - a.id), [drafts]);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/objectives/proposal-drafts');
      setDrafts(Array.isArray(data) ? data : []);
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const createDraft = async () => {
    if (!sourceText.trim()) return;
    try {
      await apiFetch('/api/objectives/proposal-drafts', {
        method: 'POST',
        body: JSON.stringify({ source_text: sourceText.trim() }),
      });
      setSourceText('');
      await refresh();
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Failed to create');
    }
  };

  const review = async (id: number, action: 'accept' | 'reject') => {
    try {
      await apiFetch(`/api/objectives/proposal-drafts/${id}/review`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      });
      await refresh();
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Failed to review');
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.h1}>Goals</Text>
      <Text style={styles.p}>
        Proposal drafts from autopilot (CORE-8 minimal). Review and accept/reject.
      </Text>

      <View style={styles.card}>
        <Text style={styles.h2}>Create draft</Text>
        <TextInput
          value={sourceText}
          onChangeText={setSourceText}
          placeholder="Describe your goal idea…"
          placeholderTextColor="#6b7280"
          style={styles.input}
          multiline
        />
        <TouchableOpacity style={styles.button} onPress={createDraft}>
          <Text style={styles.buttonText}>Create</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.rowBetween}>
        <Text style={styles.h2}>Drafts</Text>
        <TouchableOpacity onPress={refresh}>
          <Text style={styles.link}>Refresh</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator />
      ) : sorted.length === 0 ? (
        <Text style={styles.p}>No drafts yet.</Text>
      ) : (
        sorted.map((d) => (
          <View key={d.id} style={styles.card}>
            <View style={styles.rowBetween}>
              <Text style={styles.h2}>Draft #{d.id}</Text>
              <Text style={styles.meta}>{d.status}</Text>
            </View>
            <Text style={styles.meta}>{new Date(d.created_at).toLocaleString()}</Text>
            <Text style={styles.mono}>{d.source_text}</Text>

            <View style={[styles.rowBetween, { marginTop: 12 }]}>
              <TouchableOpacity style={[styles.smallButton, styles.accept]} onPress={() => review(d.id, 'accept')}>
                <Text style={styles.smallButtonText}>Accept</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.smallButton, styles.reject]} onPress={() => review(d.id, 'reject')}>
                <Text style={styles.smallButtonText}>Reject</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    backgroundColor: '#0b1220',
  },
  h1: {
    color: '#f9fafb',
    fontSize: 24,
    fontWeight: '700',
  },
  h2: {
    color: '#f9fafb',
    fontSize: 16,
    fontWeight: '700',
  },
  p: {
    color: '#9ca3af',
    marginTop: 8,
    lineHeight: 18,
  },
  meta: {
    color: '#9ca3af',
    fontSize: 12,
    marginTop: 6,
  },
  mono: {
    marginTop: 10,
    color: '#e5e7eb',
  },
  card: {
    marginTop: 14,
    borderWidth: 1,
    borderColor: '#1f2937',
    backgroundColor: '#0f172a',
    borderRadius: 12,
    padding: 12,
  },
  input: {
    marginTop: 10,
    borderWidth: 1,
    borderColor: '#1f2937',
    borderRadius: 10,
    padding: 10,
    minHeight: 90,
    color: '#f9fafb',
    backgroundColor: '#0b1220',
  },
  button: {
    marginTop: 10,
    backgroundColor: '#6366f1',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontWeight: '700',
  },
  smallButton: {
    flex: 1,
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  smallButtonText: {
    color: '#fff',
    fontWeight: '700',
  },
  accept: {
    backgroundColor: '#16a34a',
    marginRight: 8,
  },
  reject: {
    backgroundColor: '#dc2626',
    marginLeft: 8,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  link: {
    color: '#60a5fa',
    fontWeight: '600',
  },
});
