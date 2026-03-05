import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  TouchableWithoutFeedback,
  View,
} from 'react-native';
import { apiRequest } from '../lib/apiClient';

// ── Helpers ────────────────────────────────────────────────────────────────

function currentReviewType(): 'morning' | 'evening' | null {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return 'morning';
  if (h >= 18) return 'evening';
  return null;
}

// ── Morning Check-in ───────────────────────────────────────────────────────

interface MorningCheckinData {
  mood: number;
  intentions: string[];
}

function MorningCheckinFlow({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<'mood' | 'intentions' | 'done'>(
    'mood',
  );
  const [mood, setMood] = useState<number>(7);
  const [intentions, setIntentions] = useState(['', '', '']);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    const payload: MorningCheckinData = {
      mood,
      intentions: intentions.filter(i => i.trim()),
    };
    try {
      await apiRequest('/api/autopilot/morning-checkin', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setStep('done');
      setTimeout(onDone, 1400);
    } catch {
      setError('Failed to save — check your connection');
    } finally {
      setSubmitting(false);
    }
  }

  if (step === 'done') {
    return (
      <View style={subStyles.centered}>
        <Text style={subStyles.doneIcon}>☀️</Text>
        <Text style={subStyles.doneTitle}>Have a great day!</Text>
        <Text style={subStyles.doneSub}>Check-in saved</Text>
      </View>
    );
  }

  if (step === 'mood') {
    return (
      <View style={subStyles.stepContainer}>
        <Text style={subStyles.stepLabel}>How are you feeling?</Text>
        <View style={subStyles.moodRow}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
            <TouchableOpacity
              key={n}
              style={[subStyles.moodBtn, mood === n && subStyles.moodBtnActive]}
              onPress={() => setMood(n)}
              activeOpacity={0.7}
            >
              <Text style={[subStyles.moodBtnText, mood === n && subStyles.moodBtnTextActive]}>
                {n}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity
          style={subStyles.primaryBtn}
          onPress={() => setStep('intentions')}
          activeOpacity={0.8}
        >
          <Text style={subStyles.primaryBtnText}>Next →</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={subStyles.stepContainer}>
      <Text style={subStyles.stepLabel}>Top 3 intentions for today</Text>
      {intentions.map((val, i) => (
        <TextInput
          key={i}
          style={subStyles.intentionInput}
          value={val}
          onChangeText={text => {
            const next = [...intentions];
            next[i] = text;
            setIntentions(next);
          }}
          placeholder={`Intention ${i + 1}…`}
          placeholderTextColor="#6b7280"
          autoFocus={i === 0}
          returnKeyType={i < 2 ? 'next' : 'done'}
        />
      ))}
      {error ? <Text style={subStyles.errorText}>{error}</Text> : null}
      <TouchableOpacity
        style={[subStyles.primaryBtn, submitting && subStyles.btnDisabled]}
        onPress={handleSubmit}
        disabled={submitting}
        activeOpacity={0.8}
      >
        {submitting
          ? <ActivityIndicator color="#fff" size="small" />
          : <Text style={subStyles.primaryBtnText}>Start Day</Text>}
      </TouchableOpacity>
    </View>
  );
}

// ── Evening Review ─────────────────────────────────────────────────────────

interface EveningReviewData {
  day_score: number;
  biggest_win: string;
  learning: string;
}

function EveningReviewFlow({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<'score' | 'wins' | 'done'>('score');
  const [dayScore, setDayScore] = useState<number>(7);
  const [biggestWin, setBiggestWin] = useState('');
  const [learning, setLearning] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    const payload: EveningReviewData = {
      day_score: dayScore,
      biggest_win: biggestWin.trim(),
      learning: learning.trim(),
    };
    try {
      await apiRequest('/api/autopilot/evening-review', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setStep('done');
      setTimeout(onDone, 1400);
    } catch {
      setError('Failed to save — check your connection');
    } finally {
      setSubmitting(false);
    }
  }

  if (step === 'done') {
    return (
      <View style={subStyles.centered}>
        <Text style={subStyles.doneIcon}>🌙</Text>
        <Text style={subStyles.doneTitle}>Great work today!</Text>
        <Text style={subStyles.doneSub}>Review saved · Day score: {dayScore}/10</Text>
      </View>
    );
  }

  if (step === 'score') {
    return (
      <View style={subStyles.stepContainer}>
        <Text style={subStyles.stepLabel}>How was your day?</Text>
        <View style={subStyles.moodRow}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
            <TouchableOpacity
              key={n}
              style={[subStyles.moodBtn, dayScore === n && subStyles.moodBtnActive]}
              onPress={() => setDayScore(n)}
              activeOpacity={0.7}
            >
              <Text style={[subStyles.moodBtnText, dayScore === n && subStyles.moodBtnTextActive]}>
                {n}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity
          style={subStyles.primaryBtn}
          onPress={() => setStep('wins')}
          activeOpacity={0.8}
        >
          <Text style={subStyles.primaryBtnText}>Next →</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={subStyles.stepContainer}>
      <Text style={subStyles.stepLabel}>Biggest win today</Text>
      <TextInput
        style={subStyles.intentionInput}
        value={biggestWin}
        onChangeText={setBiggestWin}
        placeholder="What went well?"
        placeholderTextColor="#6b7280"
        autoFocus
        multiline
      />
      <Text style={[subStyles.stepLabel, { marginTop: 12 }]}>Key learning</Text>
      <TextInput
        style={subStyles.intentionInput}
        value={learning}
        onChangeText={setLearning}
        placeholder="What did you learn?"
        placeholderTextColor="#6b7280"
        multiline
      />
      {error ? <Text style={subStyles.errorText}>{error}</Text> : null}
      <TouchableOpacity
        style={[subStyles.primaryBtn, submitting && subStyles.btnDisabled]}
        onPress={handleSubmit}
        disabled={submitting}
        activeOpacity={0.8}
      >
        {submitting
          ? <ActivityIndicator color="#fff" size="small" />
          : <Text style={subStyles.primaryBtnText}>Save Review</Text>}
      </TouchableOpacity>
    </View>
  );
}

// ── Banner + Modal ─────────────────────────────────────────────────────────

export default function ReviewFlowBanner() {
  const reviewType = currentReviewType();
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (!reviewType || dismissed) return null;

  const isMorning = reviewType === 'morning';
  const bannerLabel = isMorning ? '☀️  Morning Check-in' : '🌙  Evening Review';
  const bannerSub = isMorning ? 'Set your intentions for today' : 'Reflect on today';
  const modalTitle = isMorning ? 'Morning Check-in' : 'Evening Review';

  return (
    <>
      <TouchableOpacity
        style={[bannerStyles.banner, isMorning ? bannerStyles.morning : bannerStyles.evening]}
        onPress={() => setOpen(true)}
        activeOpacity={0.8}
      >
        <View style={bannerStyles.bannerContent}>
          <Text style={bannerStyles.bannerLabel}>{bannerLabel}</Text>
          <Text style={bannerStyles.bannerSub}>{bannerSub}</Text>
        </View>
        <View style={bannerStyles.bannerRight}>
          <Text style={bannerStyles.bannerArrow}>Start →</Text>
          <TouchableOpacity
            onPress={e => { e.stopPropagation(); setDismissed(true); }}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={bannerStyles.dismissText}>✕</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>

      <Modal
        visible={open}
        transparent
        animationType="slide"
        onRequestClose={() => setOpen(false)}
        statusBarTranslucent
      >
        <TouchableWithoutFeedback onPress={() => setOpen(false)}>
          <View style={modalStyles.backdrop} />
        </TouchableWithoutFeedback>
        <View style={modalStyles.sheet}>
          <View style={modalStyles.header}>
            <Text style={modalStyles.title}>{modalTitle}</Text>
            <TouchableOpacity onPress={() => setOpen(false)} activeOpacity={0.7}>
              <Text style={modalStyles.closeText}>✕</Text>
            </TouchableOpacity>
          </View>
          <View style={modalStyles.content}>
            {isMorning
              ? <MorningCheckinFlow onDone={() => { setOpen(false); setDismissed(true); }} />
              : <EveningReviewFlow onDone={() => { setOpen(false); setDismissed(true); }} />}
          </View>
        </View>
      </Modal>
    </>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────

const bannerStyles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 16,
  },
  morning: { backgroundColor: '#1c1917', borderWidth: 1, borderColor: '#f59e0b33' },
  evening: { backgroundColor: '#0f0b1a', borderWidth: 1, borderColor: '#8b5cf633' },
  bannerContent: { flex: 1 },
  bannerLabel: { fontSize: 14, fontWeight: '700', color: '#f9fafb' },
  bannerSub: { fontSize: 12, color: '#9ca3af', marginTop: 2 },
  bannerRight: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  bannerArrow: { fontSize: 13, color: '#6366f1', fontWeight: '600' },
  dismissText: { fontSize: 14, color: '#6b7280' },
});

const modalStyles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' },
  sheet: {
    backgroundColor: '#1f2937',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    minHeight: 320,
    maxHeight: '70%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#374151',
  },
  title: { fontSize: 16, fontWeight: '700', color: '#f9fafb' },
  closeText: { fontSize: 16, color: '#9ca3af' },
  content: { flex: 1, padding: 16 },
});

const subStyles = StyleSheet.create({
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 24 },
  doneIcon: { fontSize: 44, marginBottom: 12 },
  doneTitle: { fontSize: 20, fontWeight: '700', color: '#f9fafb', marginBottom: 6 },
  doneSub: { fontSize: 13, color: '#9ca3af' },

  stepContainer: { flex: 1 },
  stepLabel: { fontSize: 15, fontWeight: '600', color: '#f9fafb', marginBottom: 12 },

  moodRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 20 },
  moodBtn: {
    width: 38,
    height: 38,
    borderRadius: 8,
    backgroundColor: '#111827',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#374151',
  },
  moodBtnActive: { backgroundColor: '#6366f1', borderColor: '#6366f1' },
  moodBtnText: { fontSize: 14, color: '#9ca3af', fontWeight: '600' },
  moodBtnTextActive: { color: '#fff' },

  intentionInput: {
    backgroundColor: '#111827',
    borderRadius: 10,
    padding: 12,
    color: '#f9fafb',
    fontSize: 14,
    borderWidth: 1,
    borderColor: '#374151',
    marginBottom: 10,
  },

  primaryBtn: {
    backgroundColor: '#6366f1',
    borderRadius: 10,
    paddingVertical: 13,
    alignItems: 'center',
    marginTop: 8,
  },
  btnDisabled: { opacity: 0.4 },
  primaryBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },

  errorText: { color: '#ef4444', fontSize: 13, marginBottom: 8 },
});
