import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useOnboarding } from '../context/OnboardingContext';
import { apiRequest } from '../lib/apiClient';

// ─── Types ───────────────────────────────────────────────────────────────────

type RoutineKey = 'Morning' | 'Midday' | 'Evening';

const ROUTINE_KEYS: RoutineKey[] = ['Morning', 'Midday', 'Evening'];

type FitnessKey = 'ppl' | 'upper_lower' | 'full_body' | 'skip';

const FITNESS_OPTIONS: { label: string; value: FitnessKey }[] = [
  { label: 'Push / Pull / Legs', value: 'ppl' },
  { label: 'Upper + Lower', value: 'upper_lower' },
  { label: 'Full Body 3×/wk', value: 'full_body' },
  { label: 'Skip for now', value: 'skip' },
];

const TOTAL_STEPS = 5;

// ─── Step sub-screens ────────────────────────────────────────────────────────

function StepName({
  name,
  setName,
  timezone,
  setTimezone,
}: {
  name: string;
  setName: (v: string) => void;
  timezone: string;
  setTimezone: (v: string) => void;
}) {
  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Welcome to Personal OS</Text>
      <Text style={styles.stepSubtitle}>Let's get your account set up quickly.</Text>

      <Text style={styles.label}>Your name *</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Alex"
        placeholderTextColor="#4b5563"
        autoCapitalize="words"
        returnKeyType="next"
      />

      <Text style={styles.label}>Timezone (optional)</Text>
      <TextInput
        style={styles.input}
        value={timezone}
        onChangeText={setTimezone}
        placeholder="e.g. Europe/Berlin"
        placeholderTextColor="#4b5563"
        autoCapitalize="none"
        autoCorrect={false}
        returnKeyType="done"
      />
      <Text style={styles.hint}>Used for morning briefs and reminders.</Text>
    </View>
  );
}

function StepGoals({
  goals,
  setGoals,
}: {
  goals: [string, string, string];
  setGoals: (v: [string, string, string]) => void;
}) {
  function update(idx: number, val: string) {
    const next: [string, string, string] = [...goals] as [string, string, string];
    next[idx] = val;
    setGoals(next);
  }

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Top Goals</Text>
      <Text style={styles.stepSubtitle}>
        What are your 1–3 most important goals right now? (optional)
      </Text>

      {goals.map((g, i) => (
        <TextInput
          key={i}
          style={[styles.input, { marginBottom: 10 }]}
          value={g}
          onChangeText={(v) => update(i, v)}
          placeholder={`Goal ${i + 1}`}
          placeholderTextColor="#4b5563"
          returnKeyType="next"
        />
      ))}

      <Text style={styles.hint}>These will be saved as a brain dump for the AI to process.</Text>
    </View>
  );
}

function StepRoutines({
  selected,
  onToggle,
}: {
  selected: RoutineKey[];
  onToggle: (r: RoutineKey) => void;
}) {
  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Daily Routines</Text>
      <Text style={styles.stepSubtitle}>
        Which routine slots are you interested in? (optional)
      </Text>

      <View style={styles.chipRow}>
        {ROUTINE_KEYS.map((r) => {
          const active = selected.includes(r);
          return (
            <TouchableOpacity
              key={r}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => onToggle(r)}
              activeOpacity={0.7}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{r}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Text style={styles.hint}>
        You can always add or edit routines later in the Routines tab.
      </Text>
    </View>
  );
}

function StepFitness({
  choice,
  setChoice,
}: {
  choice: FitnessKey | null;
  setChoice: (v: FitnessKey) => void;
}) {
  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Fitness Preference</Text>
      <Text style={styles.stepSubtitle}>How do you like to train? (optional)</Text>

      {FITNESS_OPTIONS.map((opt) => {
        const active = choice === opt.value;
        return (
          <TouchableOpacity
            key={opt.value}
            style={[styles.radioRow, active && styles.radioRowActive]}
            onPress={() => setChoice(opt.value)}
            activeOpacity={0.7}
          >
            <View style={[styles.radioCircle, active && styles.radioCircleActive]}>
              {active && <View style={styles.radioInner} />}
            </View>
            <Text style={[styles.radioLabel, active && styles.radioLabelActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}

      <Text style={styles.hint}>
        You can set up detailed splits anytime in the Fitness tab.
      </Text>
    </View>
  );
}

function StepFinish({ name }: { name: string }) {
  return (
    <View style={styles.stepContent}>
      <Text style={styles.finishEmoji}>🎉</Text>
      <Text style={styles.stepTitle}>You're all set{name.trim() ? `, ${name.trim()}` : ''}!</Text>
      <Text style={styles.stepSubtitle}>
        Your Personal OS is ready. You'll find your daily brief, tasks, calendar, routines, and
        fitness tracker all in the tabs below.
      </Text>
      <Text style={[styles.hint, { marginTop: 16 }]}>
        Tip: Connect your Telegram bot to get AI-powered morning briefs and evening reviews.
      </Text>
    </View>
  );
}

// ─── Main wizard ─────────────────────────────────────────────────────────────

export default function OnboardingWizard() {
  const { completeOnboarding } = useOnboarding();

  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [timezone, setTimezone] = useState('');
  const [goals, setGoals] = useState<[string, string, string]>(['', '', '']);
  const [selectedRoutines, setSelectedRoutines] = useState<RoutineKey[]>([]);
  const [fitnessChoice, setFitnessChoice] = useState<FitnessKey | null>(null);

  function toggleRoutine(r: RoutineKey) {
    setSelectedRoutines((prev) =>
      prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r],
    );
  }

  function canAdvance(): boolean {
    if (step === 0) return name.trim().length > 0;
    return true;
  }

  async function handleFinish() {
    setSubmitting(true);
    try {
      // Profile name — defensive, silent failure
      if (name.trim()) {
        await apiRequest('/api/settings/profile', {
          method: 'PUT',
          body: JSON.stringify({ first_name: name.trim() }),
        }).catch(() => {});
      }

      // Goals → brain dump — defensive, silent failure
      const filledGoals = goals.filter((g) => g.trim());
      if (filledGoals.length > 0) {
        const raw = `Onboarding goals:\n${filledGoals.map((g, i) => `${i + 1}. ${g}`).join('\n')}`;
        await apiRequest('/api/brain-dumps', {
          method: 'POST',
          body: JSON.stringify({ raw_input: raw }),
        }).catch(() => {});
      }
    } finally {
      setSubmitting(false);
      await completeOnboarding();
    }
  }

  const isLastStep = step === TOTAL_STEPS - 1;

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Progress dots */}
          <View style={styles.progressRow}>
            {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
              <View key={i} style={[styles.dot, i <= step && styles.dotActive]} />
            ))}
          </View>

          {/* Step content */}
          {step === 0 && (
            <StepName
              name={name}
              setName={setName}
              timezone={timezone}
              setTimezone={setTimezone}
            />
          )}
          {step === 1 && <StepGoals goals={goals} setGoals={setGoals} />}
          {step === 2 && (
            <StepRoutines selected={selectedRoutines} onToggle={toggleRoutine} />
          )}
          {step === 3 && <StepFitness choice={fitnessChoice} setChoice={setFitnessChoice} />}
          {step === 4 && <StepFinish name={name} />}

          {/* Navigation */}
          <View style={styles.navRow}>
            {step > 0 ? (
              <TouchableOpacity style={styles.backBtn} onPress={() => setStep((s) => s - 1)}>
                <Text style={styles.backBtnText}>Back</Text>
              </TouchableOpacity>
            ) : (
              <View style={{ flex: 1 }} />
            )}

            {!isLastStep ? (
              <TouchableOpacity
                style={[styles.nextBtn, !canAdvance() && styles.nextBtnDisabled]}
                onPress={() => setStep((s) => s + 1)}
                disabled={!canAdvance()}
                activeOpacity={0.8}
              >
                <Text style={styles.nextBtnText}>Next</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={styles.nextBtn}
                onPress={handleFinish}
                disabled={submitting}
                activeOpacity={0.8}
              >
                {submitting ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.nextBtnText}>Get Started</Text>
                )}
              </TouchableOpacity>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#111827',
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 40,
  },
  progressRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 32,
    justifyContent: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#374151',
  },
  dotActive: {
    backgroundColor: '#6366f1',
  },
  stepContent: {
    flex: 1,
    marginBottom: 32,
  },
  stepTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#f9fafb',
    marginBottom: 8,
  },
  stepSubtitle: {
    fontSize: 14,
    color: '#9ca3af',
    lineHeight: 20,
    marginBottom: 24,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#d1d5db',
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#374151',
    paddingHorizontal: 16,
    paddingVertical: 13,
    fontSize: 15,
    color: '#f9fafb',
    marginBottom: 16,
  },
  hint: {
    fontSize: 12,
    color: '#4b5563',
    lineHeight: 18,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 16,
  },
  chip: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: '#1f2937',
    borderWidth: 1,
    borderColor: '#374151',
  },
  chipActive: {
    backgroundColor: '#312e81',
    borderColor: '#6366f1',
  },
  chipText: {
    fontSize: 14,
    color: '#9ca3af',
    fontWeight: '500',
  },
  chipTextActive: {
    color: '#a5b4fc',
  },
  radioRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1f2937',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#374151',
    padding: 14,
    marginBottom: 10,
    gap: 12,
  },
  radioRowActive: {
    borderColor: '#6366f1',
    backgroundColor: '#1e1b4b',
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#4b5563',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioCircleActive: {
    borderColor: '#6366f1',
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#6366f1',
  },
  radioLabel: {
    fontSize: 15,
    color: '#9ca3af',
  },
  radioLabelActive: {
    color: '#f9fafb',
    fontWeight: '600',
  },
  finishEmoji: {
    fontSize: 52,
    textAlign: 'center',
    marginBottom: 16,
  },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 'auto',
  },
  backBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#1f2937',
    borderWidth: 1,
    borderColor: '#374151',
    alignItems: 'center',
  },
  backBtnText: {
    color: '#9ca3af',
    fontSize: 15,
    fontWeight: '600',
  },
  nextBtn: {
    flex: 2,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#6366f1',
    alignItems: 'center',
  },
  nextBtnDisabled: {
    opacity: 0.4,
  },
  nextBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
  },
});
