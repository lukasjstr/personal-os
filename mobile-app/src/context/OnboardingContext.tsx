import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { apiRequest } from '../lib/apiClient';
import { getOnboardingDone, setOnboardingDone } from '../lib/storage';
import { useAuth } from './AuthContext';

export type OnboardingState = 'loading' | 'needed' | 'done';

interface OnboardingContextValue {
  state: OnboardingState;
  completeOnboarding: () => Promise<void>;
}

interface DashboardUserFragment {
  user?: { first_name?: string | null };
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null);

export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const { state: authState } = useAuth();
  const [state, setState] = useState<OnboardingState>('loading');

  useEffect(() => {
    if (authState !== 'authenticated') {
      // Reset so the next sign-in re-evaluates
      if (authState === 'unauthenticated') setState('loading');
      return;
    }

    let cancelled = false;

    async function check() {
      // 1. Local flag is the fastest signal — existing users who already onboarded
      const localDone = await getOnboardingDone();
      if (localDone) {
        if (!cancelled) setState('done');
        return;
      }

      // 2. Ask the server: if this user already has a name they are an existing user
      try {
        const data = await apiRequest<DashboardUserFragment>('/api/dashboard');
        if (data?.user?.first_name?.trim()) {
          // Mark locally so we never hit the server for this check again
          await setOnboardingDone();
          if (!cancelled) setState('done');
          return;
        }
      } catch {
        // Server unreachable — fall through; show onboarding so they can set their name
      }

      if (!cancelled) setState('needed');
    }

    check();
    return () => {
      cancelled = true;
    };
  }, [authState]);

  const completeOnboarding = useCallback(async () => {
    await setOnboardingDone();
    setState('done');
  }, []);

  return (
    <OnboardingContext.Provider value={{ state, completeOnboarding }}>
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding(): OnboardingContextValue {
  const ctx = useContext(OnboardingContext);
  if (!ctx) throw new Error('useOnboarding must be used within OnboardingProvider');
  return ctx;
}
