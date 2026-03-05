import React, { useState } from 'react';
import { Alert, Clipboard, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../context/AuthContext';

const TESTER_STEPS = [
  '1. Install Expo Go from the App Store',
  '2. Message the bot: /token — copy the token',
  '3. Scan the QR code or open the exp:// link',
  '4. Paste token on the Auth screen and sign in',
];

export default function SettingsScreen() {
  const { signOut } = useAuth();
  const [testerExpanded, setTesterExpanded] = useState(false);

  function handleSignOut() {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: signOut },
    ]);
  }

  function handleCopyTokenCommand() {
    Clipboard.setString('/token');
    Alert.alert('Copied', 'Send "/token" to the Telegram bot to get your auth token.');
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.content}>
        <Text style={styles.sectionTitle}>Tester Info</Text>
        <TouchableOpacity
          style={styles.card}
          onPress={() => setTesterExpanded(prev => !prev)}
          activeOpacity={0.8}
        >
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>How to join as a tester</Text>
            <Text style={styles.chevron}>{testerExpanded ? '▲' : '▼'}</Text>
          </View>
          {testerExpanded && (
            <View style={styles.cardBody}>
              {TESTER_STEPS.map(step => (
                <Text key={step} style={styles.stepText}>{step}</Text>
              ))}
              <TouchableOpacity style={styles.copyButton} onPress={handleCopyTokenCommand}>
                <Text style={styles.copyButtonText}>Copy /token command</Text>
              </TouchableOpacity>
            </View>
          )}
        </TouchableOpacity>

        <Text style={[styles.sectionTitle, styles.sectionTitleSpaced]}>Account</Text>
        <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },
  content: { padding: 16 },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 12,
  },
  sectionTitleSpaced: { marginTop: 24 },
  card: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#374151',
    overflow: 'hidden',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 14,
  },
  cardTitle: { color: '#e5e7eb', fontWeight: '600', fontSize: 14 },
  chevron: { color: '#6b7280', fontSize: 11 },
  cardBody: {
    paddingHorizontal: 14,
    paddingBottom: 14,
    borderTopWidth: 1,
    borderTopColor: '#374151',
    paddingTop: 12,
    gap: 6,
  },
  stepText: { color: '#9ca3af', fontSize: 13, lineHeight: 19 },
  copyButton: {
    marginTop: 8,
    backgroundColor: '#374151',
    borderRadius: 7,
    paddingVertical: 8,
    paddingHorizontal: 12,
    alignSelf: 'flex-start',
  },
  copyButtonText: { color: '#60a5fa', fontSize: 13, fontWeight: '600' },
  signOutButton: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#7f1d1d',
  },
  signOutText: { color: '#f87171', fontWeight: '600', fontSize: 15 },
});
