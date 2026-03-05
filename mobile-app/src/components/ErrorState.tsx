import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

const NETWORK_PHRASES = [
  'network error',
  'check your connection',
  'request timed out',
  'network request failed',
  'unable to reach',
];

function isNetworkError(message: string): boolean {
  const lower = message.toLowerCase();
  return NETWORK_PHRASES.some(p => lower.includes(p));
}

interface ErrorStateProps {
  /** The error message string from useApi */
  error: string;
  /** Called when the user presses Retry */
  onRetry: () => void;
}

/**
 * Unified full-screen error state used in core screens.
 * Shows an offline hint when the error looks network-related.
 */
export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const offline = isNetworkError(error);
  return (
    <View style={styles.container}>
      {offline && (
        <View style={styles.offlinePill}>
          <Text style={styles.offlineText}>You appear to be offline</Text>
        </View>
      )}
      <Text style={styles.errorText}>
        {offline ? 'Could not reach the server.' : error}
      </Text>
      <TouchableOpacity style={styles.retryButton} onPress={onRetry} activeOpacity={0.75}>
        <Text style={styles.retryText}>Retry</Text>
      </TouchableOpacity>
    </View>
  );
}

/**
 * Non-blocking inline banner used in Home to signal a fetch failure
 * without hiding existing content.
 */
export function ErrorBanner({ error, onRetry }: ErrorStateProps) {
  const offline = isNetworkError(error);
  return (
    <View style={styles.banner}>
      <Text style={styles.bannerText} numberOfLines={2}>
        {offline ? 'Offline — showing cached data.' : `Load error: ${error}`}
      </Text>
      <TouchableOpacity onPress={onRetry} activeOpacity={0.75} style={styles.bannerRetry}>
        <Text style={styles.bannerRetryText}>Retry</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  // Full-screen state (Tasks, Calendar)
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  offlinePill: {
    backgroundColor: '#1f2937',
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 4,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#374151',
  },
  offlineText: {
    fontSize: 12,
    color: '#9ca3af',
    fontWeight: '500',
  },
  errorText: {
    color: '#f87171',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 16,
  },
  retryButton: {
    backgroundColor: '#6366f1',
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryText: {
    color: '#f9fafb',
    fontWeight: '600',
    fontSize: 14,
  },

  // Inline banner (Home)
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1c1917',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#f87171',
    gap: 8,
  },
  bannerText: {
    flex: 1,
    fontSize: 12,
    color: '#fca5a5',
  },
  bannerRetry: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: '#292524',
    borderWidth: 1,
    borderColor: '#44403c',
  },
  bannerRetryText: {
    fontSize: 12,
    color: '#d1d5db',
    fontWeight: '600',
  },
});
