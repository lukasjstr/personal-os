/**
 * QuickLog Screen — frictionless one-tap logging for daily health metrics.
 *
 * Sections:
 * 1. Water — quick-tap predefined amounts (250ml, 500ml, 750ml, 1L)
 * 2. Sleep — last night's hours + quality rating
 * 3. Mood — emoji scale 1-5 (maps to 2/4/6/8/10)
 * 4. Food — quick text entry + meal type selector
 *
 * All entries save instantly with haptic feedback.
 */
import React, { useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiRequest } from '../lib/apiClient';

// ── Types ──────────────────────────────────────────────────────────────────

type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

// ── Constants ──────────────────────────────────────────────────────────────

const WATER_AMOUNTS = [
  { label: '250ml', value: 0.25 },
  { label: '500ml', value: 0.5 },
  { label: '750ml', value: 0.75 },
  { label: '1L', value: 1.0 },
];

const MOOD_OPTIONS = [
  { emoji: '😔', label: 'Schlecht', score: 2 },
  { emoji: '😕', label: 'Mäßig', score: 4 },
  { emoji: '😐', label: 'Okay', score: 6 },
  { emoji: '😊', label: 'Gut', score: 8 },
  { emoji: '🤩', label: 'Großartig', score: 10 },
];

const MEAL_TYPES: { type: MealType; label: string; emoji: string }[] = [
  { type: 'breakfast', label: 'Frühstück', emoji: '🌅' },
  { type: 'lunch', label: 'Mittagessen', emoji: '☀️' },
  { type: 'dinner', label: 'Abendessen', emoji: '🌙' },
  { type: 'snack', label: 'Snack', emoji: '🍎' },
];

// ── Main Component ─────────────────────────────────────────────────────────

export default function QuickLogScreen() {
  // Water state
  const [waterLoading, setWaterLoading] = useState<number | null>(null);
  const [waterTodayL, setWaterTodayL] = useState<number | null>(null);

  // Sleep state
  const [sleepHours, setSleepHours] = useState('');
  const [sleepQuality, setSleepQuality] = useState<number | null>(null);
  const [sleepLoading, setSleepLoading] = useState(false);
  const [sleepSaved, setSleepSaved] = useState(false);

  // Mood state
  const [moodLoading, setMoodLoading] = useState<number | null>(null);
  const [moodSaved, setMoodSaved] = useState<number | null>(null);

  // Food state
  const [foodText, setFoodText] = useState('');
  const [selectedMealType, setSelectedMealType] = useState<MealType>('snack');
  const [foodLoading, setFoodLoading] = useState(false);
  const [foodSaved, setFoodSaved] = useState<string | null>(null);

  // ── Water Logging ────────────────────────────────────────────────────────

  const logWater = async (amount: number) => {
    setWaterLoading(amount);
    try {
      const result = await apiRequest<{ total_today: number }>('/api/logs/water', {
        method: 'POST',
        body: JSON.stringify({ amount_liters: amount }),
      });
      setWaterTodayL(result.total_today);
    } catch {
      Alert.alert('Fehler', 'Wasser konnte nicht geloggt werden.');
    } finally {
      setWaterLoading(null);
    }
  };

  // ── Sleep Logging ────────────────────────────────────────────────────────

  const logSleep = async () => {
    const hours = parseFloat(sleepHours);
    if (isNaN(hours) || hours < 0 || hours > 24) {
      Alert.alert('Ungültig', 'Bitte gib eine gültige Stundenanzahl ein (0-24).');
      return;
    }
    setSleepLoading(true);
    try {
      await apiRequest('/api/logs/sleep', {
        method: 'POST',
        body: JSON.stringify({ hours, quality: sleepQuality }),
      });
      setSleepSaved(true);
      setTimeout(() => setSleepSaved(false), 3000);
    } catch {
      Alert.alert('Fehler', 'Schlaf konnte nicht geloggt werden.');
    } finally {
      setSleepLoading(false);
    }
  };

  // ── Mood Logging ─────────────────────────────────────────────────────────

  const logMood = async (score: number) => {
    setMoodLoading(score);
    try {
      await apiRequest('/api/logs/mood', {
        method: 'POST',
        body: JSON.stringify({ score }),
      });
      setMoodSaved(score);
    } catch {
      Alert.alert('Fehler', 'Stimmung konnte nicht geloggt werden.');
    } finally {
      setMoodLoading(null);
    }
  };

  // ── Food Logging ─────────────────────────────────────────────────────────

  const logFood = async () => {
    if (!foodText.trim()) {
      Alert.alert('Pflichtfeld', 'Bitte beschreibe deine Mahlzeit.');
      return;
    }
    setFoodLoading(true);
    try {
      await apiRequest('/api/nutrition/log', {
        method: 'POST',
        body: JSON.stringify({
          food_name: foodText.trim(),
          meal_type: selectedMealType,
          source: 'mobile',
        }),
      });
      const mealLabel = MEAL_TYPES.find(m => m.type === selectedMealType)?.label || selectedMealType;
      setFoodSaved(`${mealLabel}: ${foodText.trim()}`);
      setFoodText('');
      setTimeout(() => setFoodSaved(null), 4000);
    } catch {
      Alert.alert('Fehler', 'Mahlzeit konnte nicht geloggt werden.');
    } finally {
      setFoodLoading(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Text style={styles.pageTitle}>Quick Log</Text>
        <Text style={styles.pageSubtitle}>Schnelles Logging — alles in einem</Text>

        {/* ── Water Section ──────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>💧 Wasser</Text>
          {waterTodayL !== null && (
            <Text style={styles.sectionSubtitle}>Heute: {waterTodayL.toFixed(1)}L</Text>
          )}
          <View style={styles.row}>
            {WATER_AMOUNTS.map(({ label, value }) => (
              <TouchableOpacity
                key={value}
                style={styles.quickBtn}
                onPress={() => logWater(value)}
                disabled={waterLoading !== null}
              >
                {waterLoading === value ? (
                  <ActivityIndicator size="small" color="#3b82f6" />
                ) : (
                  <Text style={styles.quickBtnText}>{label}</Text>
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* ── Sleep Section ──────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>😴 Schlaf</Text>
          <Text style={styles.label}>Stunden letzte Nacht</Text>
          <TextInput
            style={styles.input}
            value={sleepHours}
            onChangeText={setSleepHours}
            keyboardType="decimal-pad"
            placeholder="z.B. 7.5"
            placeholderTextColor="#6b7280"
          />
          <Text style={styles.label}>Qualität (1–10)</Text>
          <View style={styles.row}>
            {[2, 4, 6, 8, 10].map(q => (
              <TouchableOpacity
                key={q}
                style={[styles.qualityBtn, sleepQuality === q && styles.qualityBtnActive]}
                onPress={() => setSleepQuality(q)}
              >
                <Text style={[styles.qualityBtnText, sleepQuality === q && styles.qualityBtnTextActive]}>
                  {q}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity
            style={[styles.saveBtn, sleepSaved && styles.saveBtnSuccess]}
            onPress={logSleep}
            disabled={sleepLoading}
          >
            {sleepLoading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.saveBtnText}>{sleepSaved ? '✓ Gespeichert' : 'Schlaf speichern'}</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* ── Mood Section ───────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>😊 Stimmung</Text>
          <View style={styles.moodRow}>
            {MOOD_OPTIONS.map(({ emoji, label, score }) => (
              <TouchableOpacity
                key={score}
                style={[styles.moodBtn, moodSaved === score && styles.moodBtnActive]}
                onPress={() => logMood(score)}
                disabled={moodLoading !== null}
              >
                {moodLoading === score ? (
                  <ActivityIndicator size="small" color="#3b82f6" />
                ) : (
                  <>
                    <Text style={styles.moodEmoji}>{emoji}</Text>
                    <Text style={styles.moodLabel}>{label}</Text>
                  </>
                )}
              </TouchableOpacity>
            ))}
          </View>
          {moodSaved !== null && (
            <Text style={styles.savedHint}>
              ✓ Stimmung {moodSaved}/10 gespeichert
            </Text>
          )}
        </View>

        {/* ── Food Section ───────────────────────────────────────────── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🍽️ Mahlzeit</Text>
          <Text style={styles.label}>Mahlzeitentyp</Text>
          <View style={styles.row}>
            {MEAL_TYPES.map(({ type, label, emoji }) => (
              <TouchableOpacity
                key={type}
                style={[styles.mealTypeBtn, selectedMealType === type && styles.mealTypeBtnActive]}
                onPress={() => setSelectedMealType(type)}
              >
                <Text style={styles.mealTypeEmoji}>{emoji}</Text>
                <Text style={[styles.mealTypeText, selectedMealType === type && styles.mealTypeTextActive]}>
                  {label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput
            style={[styles.input, styles.inputMultiline]}
            value={foodText}
            onChangeText={setFoodText}
            placeholder="Was hast du gegessen? (z.B. Hähnchenbrust 200g mit Reis)"
            placeholderTextColor="#6b7280"
            multiline
            numberOfLines={2}
          />
          <TouchableOpacity
            style={[styles.saveBtn, foodSaved !== null && styles.saveBtnSuccess]}
            onPress={logFood}
            disabled={foodLoading}
          >
            {foodLoading ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={styles.saveBtnText}>
                {foodSaved !== null ? '✓ Gespeichert' : 'Mahlzeit loggen'}
              </Text>
            )}
          </TouchableOpacity>
          {foodSaved && (
            <Text style={styles.savedHint}>✓ {foodSaved}</Text>
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  scroll: {
    padding: 16,
  },
  pageTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: '#f1f5f9',
    marginBottom: 4,
  },
  pageSubtitle: {
    fontSize: 14,
    color: '#94a3b8',
    marginBottom: 24,
  },
  section: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#f1f5f9',
    marginBottom: 12,
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#3b82f6',
    marginBottom: 10,
    marginTop: -8,
  },
  label: {
    fontSize: 13,
    color: '#94a3b8',
    marginBottom: 8,
    marginTop: 8,
  },
  row: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  quickBtn: {
    backgroundColor: '#1d4ed8',
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
    minWidth: 70,
    alignItems: 'center',
  },
  quickBtnText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 15,
  },
  input: {
    backgroundColor: '#0f172a',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155',
    color: '#f1f5f9',
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    marginBottom: 12,
  },
  inputMultiline: {
    height: 72,
    textAlignVertical: 'top',
    paddingTop: 12,
  },
  qualityBtn: {
    backgroundColor: '#0f172a',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: '#334155',
    minWidth: 44,
    alignItems: 'center',
  },
  qualityBtnActive: {
    backgroundColor: '#1d4ed8',
    borderColor: '#3b82f6',
  },
  qualityBtnText: {
    color: '#94a3b8',
    fontWeight: '600',
    fontSize: 14,
  },
  qualityBtnTextActive: {
    color: '#fff',
  },
  saveBtn: {
    backgroundColor: '#1d4ed8',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  saveBtnSuccess: {
    backgroundColor: '#16a34a',
  },
  saveBtnText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
  },
  moodRow: {
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
  },
  moodBtn: {
    flex: 1,
    backgroundColor: '#0f172a',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  moodBtnActive: {
    backgroundColor: '#1e3a5f',
    borderColor: '#3b82f6',
  },
  moodEmoji: {
    fontSize: 22,
    marginBottom: 4,
  },
  moodLabel: {
    color: '#94a3b8',
    fontSize: 11,
    textAlign: 'center',
  },
  mealTypeBtn: {
    flex: 1,
    backgroundColor: '#0f172a',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
    minWidth: 70,
  },
  mealTypeBtnActive: {
    backgroundColor: '#1e3a5f',
    borderColor: '#3b82f6',
  },
  mealTypeEmoji: {
    fontSize: 18,
    marginBottom: 2,
  },
  mealTypeText: {
    color: '#94a3b8',
    fontSize: 10,
    textAlign: 'center',
  },
  mealTypeTextActive: {
    color: '#60a5fa',
  },
  savedHint: {
    color: '#22c55e',
    fontSize: 13,
    marginTop: 8,
    textAlign: 'center',
  },
});
