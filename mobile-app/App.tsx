import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { OnboardingProvider, useOnboarding } from './src/context/OnboardingContext';
import TabNavigator from './src/navigation/TabNavigator';
import AuthScreen from './src/screens/AuthScreen';
import OnboardingWizard from './src/screens/OnboardingWizard';
import { startBackgroundSync } from './src/services/HealthConnectSync';

function AppContent() {
  const { state: authState } = useAuth();
  const { state: onboardingState } = useOnboarding();

  // Start health data background sync once authenticated
  useEffect(() => {
    if (authState === 'authenticated') {
      startBackgroundSync().catch(() => {/* silent — no native health SDK in Expo Go */});
    }
  }, [authState]);

  // Still resolving auth or (authenticated and still checking onboarding)
  if (authState === 'loading' || (authState === 'authenticated' && onboardingState === 'loading')) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color="#6366f1" />
      </View>
    );
  }

  if (authState === 'unauthenticated') {
    return <AuthScreen />;
  }

  // Authenticated — route based on onboarding
  if (onboardingState === 'needed') {
    return <OnboardingWizard />;
  }

  return (
    <NavigationContainer>
      <TabNavigator />
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <OnboardingProvider>
          <AppContent />
          <StatusBar style="light" />
        </OnboardingProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    backgroundColor: '#111827',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
