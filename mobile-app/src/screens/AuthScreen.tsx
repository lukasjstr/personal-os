import React, { useState } from 'react';
import {
  ActivityIndicator,
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
import { useAuth } from '../context/AuthContext';

export default function AuthScreen() {
  const { signIn } = useAuth();
  const [inputToken, setInputToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function normalizeToken(raw: string): string {
    let t = raw.trim();
    t = t.replace(/^Bearer\s+/i, '').trim();
    t = t.replace(/^`+|`+$/g, '').trim();
    t = t.replace(/^['\"]+|['\"]+$/g, '').trim();

    // If user pasted a full message, try to extract the longest token-like chunk.
    const candidates = t.match(/[A-Za-z0-9_\-]{20,}/g);
    if (candidates && candidates.length > 0) {
      t = candidates.sort((a, b) => b.length - a.length)[0];
    }
    return t;
  }

  async function handleConnect() {
    const normalized = normalizeToken(inputToken);
    if (!normalized) {
      setError('Please enter your API token.');
      return;
    }
    setLoading(true);
    setError(null);
    const success = await signIn(normalized);
    setLoading(false);
    if (!success) {
      setError('Invalid token (or backend unreachable). Get a fresh /token and try again.');
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.card}>
          <Text style={styles.title}>Personal OS</Text>
          <Text style={styles.subtitle}>Enter your API token to connect</Text>

          <TextInput
            style={[styles.input, error != null && styles.inputError]}
            value={inputToken}
            onChangeText={(t) => {
              setInputToken(t);
              setError(null);
            }}
            placeholder="Paste token here"
            placeholderTextColor="#4b5563"
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry
            returnKeyType="done"
            onSubmitEditing={handleConnect}
          />

          {error != null && <Text style={styles.errorText}>{error}</Text>}

          <TouchableOpacity
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleConnect}
            disabled={loading}
            activeOpacity={0.8}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Connect</Text>
            )}
          </TouchableOpacity>

          <Text style={styles.serverHint}>{API_BASE_URL}</Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#111827',
  },
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    backgroundColor: '#1f2937',
    borderRadius: 16,
    padding: 28,
    gap: 16,
    borderWidth: 1,
    borderColor: '#374151',
  },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#f9fafb',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: '#9ca3af',
    textAlign: 'center',
  },
  input: {
    backgroundColor: '#111827',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#374151',
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 15,
    color: '#f9fafb',
  },
  inputError: {
    borderColor: '#ef4444',
  },
  errorText: {
    fontSize: 13,
    color: '#ef4444',
  },
  button: {
    backgroundColor: '#6366f1',
    borderRadius: 10,
    paddingVertical: 15,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  serverHint: {
    fontSize: 11,
    color: '#4b5563',
    textAlign: 'center',
  },
});
