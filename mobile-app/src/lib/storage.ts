import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'pos_auth_token';
const ONBOARDING_KEY = 'pos_onboarding_done';

export async function saveToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function deleteToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function getOnboardingDone(): Promise<boolean> {
  const val = await SecureStore.getItemAsync(ONBOARDING_KEY);
  return val === 'true';
}

export async function setOnboardingDone(): Promise<void> {
  await SecureStore.setItemAsync(ONBOARDING_KEY, 'true');
}

export async function clearOnboardingDone(): Promise<void> {
  await SecureStore.deleteItemAsync(ONBOARDING_KEY);
}
