/**
 * API configuration.
 *
 * Set EXPO_PUBLIC_API_URL in your .env.local to override the default:
 *   - iOS simulator:     http://localhost:8000
 *   - Android emulator:  http://10.0.2.2:8000
 *   - Physical device:   http://<your-machine-ip>:8000
 *   - Production:        https://95.111.252.176  (default)
 */
export const API_BASE_URL: string = (
  process.env.EXPO_PUBLIC_API_URL ?? 'https://95.111.252.176'
).replace(/\/$/, '');

export const API_TIMEOUT_MS = 10_000;
