/**
 * API configuration.
 *
 * Set EXPO_PUBLIC_API_URL in your .env.local to override the default:
 *   - iOS simulator:     http://localhost:8000
 *   - Android emulator:  http://10.0.2.2:8000
 *   - Physical device:   http://<your-machine-ip>:8000
 *   - Production:        http://95.111.252.176:3000  (default via nginx proxy)
 */
export const API_BASE_URL: string = (
  process.env.EXPO_PUBLIC_API_URL ?? 'http://95.111.252.176:3000'
).replace(/\/$/, '');

export const API_TIMEOUT_MS = 10_000;
