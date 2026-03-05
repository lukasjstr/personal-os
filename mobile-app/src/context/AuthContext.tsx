import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { validateToken } from '../lib/apiClient';
import { deleteToken, getToken, saveToken } from '../lib/storage';

type AuthState = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  state: AuthState;
  token: string | null;
  signIn: (token: string) => Promise<boolean>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>('loading');
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    async function bootstrap() {
      const stored = await getToken();
      if (!stored) {
        setState('unauthenticated');
        return;
      }
      const valid = await validateToken(stored);
      if (valid) {
        setToken(stored);
        setState('authenticated');
      } else {
        await deleteToken();
        setState('unauthenticated');
      }
    }
    bootstrap();
  }, []);

  const signIn = useCallback(async (newToken: string): Promise<boolean> => {
    const valid = await validateToken(newToken);
    if (!valid) return false;
    await saveToken(newToken);
    setToken(newToken);
    setState('authenticated');
    return true;
  }, []);

  const signOut = useCallback(async () => {
    await deleteToken();
    setToken(null);
    setState('unauthenticated');
  }, []);

  return (
    <AuthContext.Provider value={{ state, token, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
