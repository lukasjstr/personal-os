/**
 * VoiceScreen — AI COO als Sprachassistent direkt von der App / Uhr.
 *
 * Flow:
 * 1. Tippen → Aufnahme startet (expo-av)
 * 2. Nochmal tippen → Aufnahme stoppt, Audio → POST /api/voice/command (Whisper)
 * 3. KI-Antwort kommt zurück → wird vorgelesen (expo-speech) + angezeigt
 * 4. Verlauf der Session bleibt sichtbar
 *
 * Fallback: Texteingabe direkt möglich (Tastatur-Icon).
 */
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';
import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { API_BASE_URL } from '../config/api';
import { getToken } from '../lib/storage';

// ── Types ─────────────────────────────────────────────────────────────────────

type MessageRole = 'user' | 'assistant';

interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  transcribed?: string;
}

type RecordingState = 'idle' | 'recording' | 'processing';

// ── Colors ────────────────────────────────────────────────────────────────────

const C = {
  bg: '#0f172a',
  surface: '#1e293b',
  border: '#334155',
  primary: '#6366f1',
  primaryDark: '#4f46e5',
  accent: '#e11d48',
  text: '#f1f5f9',
  muted: '#94a3b8',
  userBubble: '#312e81',
  aiBubble: '#1e293b',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

async function sendVoiceAudio(uri: string): Promise<{ transcribed: string; response: string }> {
  const token = await getToken();
  const formData = new FormData();
  // @ts-ignore – React Native FormData accepts this shape
  formData.append('audio', { uri, name: 'voice.m4a', type: 'audio/m4a' });
  formData.append('source', 'watch');

  const res = await fetch(`${API_BASE_URL}/api/voice/command`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Fehler beim Senden der Sprachaufnahme');
  }
  return res.json();
}

async function sendVoiceText(text: string): Promise<{ transcribed: string; response: string }> {
  const token = await getToken();
  const formData = new FormData();
  formData.append('text', text);
  formData.append('source', 'watch_text');

  const res = await fetch(`${API_BASE_URL}/api/voice/command`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) throw new Error('Fehler');
  return res.json();
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function VoiceScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [recordingState, setRecordingState] = useState<RecordingState>('idle');
  const [showTextInput, setShowTextInput] = useState(false);
  const [textDraft, setTextDraft] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const listRef = useRef<FlatList>(null);

  useEffect(() => {
    // Request mic permissions on mount
    Audio.requestPermissionsAsync();
    return () => {
      // Stop any ongoing speech when leaving screen
      Speech.stop();
    };
  }, []);

  const scrollToBottom = () => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
  };

  const addMessage = (msg: Omit<ChatMessage, 'id'>) => {
    const full: ChatMessage = { ...msg, id: Date.now().toString() + Math.random() };
    setMessages((prev) => [...prev, full]);
    scrollToBottom();
    return full;
  };

  const speakResponse = (text: string) => {
    Speech.stop();
    setIsSpeaking(true);
    Speech.speak(text, {
      language: 'de-DE',
      rate: 1.0,
      pitch: 1.0,
      onDone: () => setIsSpeaking(false),
      onStopped: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  // ── Recording ───────────────────────────────────────────────────────────────

  const startRecording = async () => {
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
      );
      recordingRef.current = recording;
      setRecordingState('recording');
    } catch {
      addMessage({ role: 'assistant', text: '⚠️ Mikrofon-Zugriff verweigert. Bitte Berechtigung in Einstellungen erteilen.' });
    }
  };

  const stopRecordingAndProcess = async () => {
    if (!recordingRef.current) return;
    setRecordingState('processing');

    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (!uri) throw new Error('Keine Aufnahme');

      const { transcribed, response } = await sendVoiceAudio(uri);
      addMessage({ role: 'user', text: transcribed });
      addMessage({ role: 'assistant', text: response });
      speakResponse(response);
    } catch (e: any) {
      addMessage({ role: 'assistant', text: `⚠️ ${e.message}` });
    } finally {
      setRecordingState('idle');
    }
  };

  const handleMicPress = () => {
    if (recordingState === 'idle') {
      startRecording();
    } else if (recordingState === 'recording') {
      stopRecordingAndProcess();
    }
  };

  // ── Text submit ─────────────────────────────────────────────────────────────

  const handleTextSubmit = async () => {
    const t = textDraft.trim();
    if (!t) return;
    setTextDraft('');
    setShowTextInput(false);
    addMessage({ role: 'user', text: t });
    setRecordingState('processing');
    try {
      const { response } = await sendVoiceText(t);
      addMessage({ role: 'assistant', text: response });
      speakResponse(response);
    } catch (e: any) {
      addMessage({ role: 'assistant', text: `⚠️ ${e.message}` });
    } finally {
      setRecordingState('idle');
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  const renderMessage = ({ item }: { item: ChatMessage }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAI]}>
        {!isUser && (
          <View style={styles.aiLabel}>
            <Ionicons name="sparkles" size={12} color={C.primary} />
            <Text style={styles.aiLabelText}>AI COO</Text>
          </View>
        )}
        <Text style={[styles.bubbleText, isUser ? styles.bubbleTextUser : styles.bubbleTextAI]}>
          {item.text}
        </Text>
      </View>
    );
  };

  const micColor =
    recordingState === 'recording' ? C.accent : recordingState === 'processing' ? C.muted : C.primary;

  const micIcon: React.ComponentProps<typeof Ionicons>['name'] =
    recordingState === 'recording' ? 'stop-circle' : 'mic';

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Header hint */}
      <View style={styles.header}>
        <Ionicons name="watch" size={16} color={C.muted} />
        <Text style={styles.headerText}>
          {recordingState === 'recording'
            ? 'Aufnahme läuft…'
            : recordingState === 'processing'
            ? 'KI denkt nach…'
            : isSpeaking
            ? 'Spricht…'
            : 'Tippe den Mic-Button und sprich'}
        </Text>
        {isSpeaking && (
          <TouchableOpacity onPress={() => { Speech.stop(); setIsSpeaking(false); }}>
            <Ionicons name="volume-mute" size={16} color={C.muted} />
          </TouchableOpacity>
        )}
      </View>

      {/* Chat history */}
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        renderItem={renderMessage}
        contentContainerStyle={styles.chatContent}
        ListEmptyComponent={<EmptyState />}
        style={styles.chat}
      />

      {/* Text input (optional fallback) */}
      {showTextInput && (
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.textRow}
        >
          <TextInput
            style={styles.textInput}
            placeholder="Nachricht tippen…"
            placeholderTextColor={C.muted}
            value={textDraft}
            onChangeText={setTextDraft}
            onSubmitEditing={handleTextSubmit}
            autoFocus
            returnKeyType="send"
            multiline={false}
          />
          <TouchableOpacity onPress={handleTextSubmit} style={styles.sendBtn}>
            <Ionicons name="send" size={20} color={C.text} />
          </TouchableOpacity>
        </KeyboardAvoidingView>
      )}

      {/* Action bar */}
      <View style={styles.actionBar}>
        {/* Keyboard toggle */}
        <TouchableOpacity
          style={styles.iconBtn}
          onPress={() => setShowTextInput((v) => !v)}
          disabled={recordingState === 'recording'}
        >
          <Ionicons
            name={showTextInput ? 'close' : 'create-outline'}
            size={22}
            color={showTextInput ? C.accent : C.muted}
          />
        </TouchableOpacity>

        {/* Main mic button */}
        <TouchableOpacity
          style={[styles.micBtn, { backgroundColor: micColor, opacity: recordingState === 'processing' ? 0.5 : 1 }]}
          onPress={handleMicPress}
          disabled={recordingState === 'processing'}
          activeOpacity={0.8}
        >
          {recordingState === 'processing' ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Ionicons name={micIcon} size={32} color="#fff" />
          )}
        </TouchableOpacity>

        {/* Clear history */}
        <TouchableOpacity
          style={styles.iconBtn}
          onPress={() => setMessages([])}
          disabled={recordingState !== 'idle' || messages.length === 0}
        >
          <Ionicons name="trash-outline" size={22} color={messages.length === 0 ? C.border : C.muted} />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <View style={styles.empty}>
      <Ionicons name="watch" size={48} color="#334155" />
      <Text style={styles.emptyTitle}>Dein AI COO hört zu</Text>
      <Text style={styles.emptyBody}>
        Tippe den Mic-Button und sprich direkt — Workouts loggen, Fragen stellen, Aufgaben anlegen,
        Check-ins machen. Alles was du Lukas, deinem persönlichen COO, sagen würdest.
      </Text>
      <View style={styles.examples}>
        {[
          '"Workout abgeschlossen, 45 min Kraft"',
          '"Wie ist mein Tag heute?"',
          '"Füge Aufgabe Steuern hinzu"',
          '"Ich bin heute müde, passe Plan an"',
        ].map((ex) => (
          <View key={ex} style={styles.exampleChip}>
            <Text style={styles.exampleText}>{ex}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: C.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  headerText: {
    flex: 1,
    color: C.muted,
    fontSize: 13,
  },
  chat: {
    flex: 1,
  },
  chatContent: {
    padding: 16,
    gap: 12,
    flexGrow: 1,
  },
  bubble: {
    maxWidth: '82%',
    borderRadius: 16,
    padding: 12,
    marginVertical: 4,
  },
  bubbleUser: {
    alignSelf: 'flex-end',
    backgroundColor: C.userBubble,
    borderBottomRightRadius: 4,
  },
  bubbleAI: {
    alignSelf: 'flex-start',
    backgroundColor: C.aiBubble,
    borderWidth: 1,
    borderColor: C.border,
    borderBottomLeftRadius: 4,
  },
  aiLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  aiLabelText: {
    color: C.primary,
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  bubbleText: {
    fontSize: 15,
    lineHeight: 22,
  },
  bubbleTextUser: {
    color: '#e0e7ff',
  },
  bubbleTextAI: {
    color: C.text,
  },
  textRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: C.border,
    gap: 8,
  },
  textInput: {
    flex: 1,
    backgroundColor: C.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: C.text,
    fontSize: 15,
    borderWidth: 1,
    borderColor: C.border,
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  micBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  iconBtn: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
    gap: 12,
  },
  emptyTitle: {
    color: C.text,
    fontSize: 20,
    fontWeight: '700',
    marginTop: 8,
  },
  emptyBody: {
    color: C.muted,
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 22,
  },
  examples: {
    marginTop: 16,
    gap: 8,
    width: '100%',
  },
  exampleChip: {
    backgroundColor: C.surface,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: C.border,
  },
  exampleText: {
    color: C.muted,
    fontSize: 13,
    fontStyle: 'italic',
  },
});
