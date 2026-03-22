/**
 * HealthConnectSync — Universal Android health data sync via Health Connect API.
 *
 * Health Connect aggregates data from ALL Android wearables:
 * - Huawei Health / Honor Band  → via Huawei Health app
 * - Samsung Galaxy Watch        → via Samsung Health
 * - Garmin                      → via Garmin Connect
 * - Fitbit                      → via Fitbit app
 * - Polar, Withings, Xiaomi Mi Band, …
 *
 * Setup (one-time, Android only):
 * 1. Add to android/app/src/main/AndroidManifest.xml:
 *    <uses-permission android:name="android.permission.health.READ_STEPS"/>
 *    <uses-permission android:name="android.permission.health.READ_HEART_RATE"/>
 *    <uses-permission android:name="android.permission.health.READ_SLEEP"/>
 *    <uses-permission android:name="android.permission.health.READ_ACTIVE_CALORIES_BURNED"/>
 *    <uses-permission android:name="android.permission.health.READ_DISTANCE"/>
 *    <uses-permission android:name="android.permission.health.READ_WEIGHT"/>
 *    <uses-permission android:name="android.permission.health.READ_HEART_RATE_VARIABILITY"/>
 *    <uses-permission android:name="android.permission.health.READ_BLOOD_OXYGEN"/>
 *
 * 2. Install: npx expo install react-native-health-connect
 *
 * iOS: Install react-native-health and enable HealthKit entitlement.
 *
 * Usage:
 *   import { syncHealthDataNow, startBackgroundSync } from './HealthConnectSync';
 *   await startBackgroundSync();       // call once in App.tsx
 *   await syncHealthDataNow();         // call on app foreground
 */

import { Platform } from 'react-native';
import { apiRequest } from '../lib/apiClient';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface HealthMetrics {
  steps?: number;
  calories?: number;       // kcal active
  sleep_hours?: number;
  sleep_quality?: number;  // 1-10 estimated from deep/light ratio
  hrv?: number;            // ms
  resting_heart_rate?: number;
  weight_kg?: number;
  spo2?: number;           // %
  distance_km?: number;
  active_minutes?: number;
  metric_date?: string;    // YYYY-MM-DD
  source?: string;
}

// ── Android Health Connect ────────────────────────────────────────────────────

async function readAndroidHealthConnect(targetDate: Date): Promise<HealthMetrics | null> {
  try {
    // Dynamic require — only available in native build (not Expo Go)
    let HC: any;
    try { HC = require('react-native-health-connect'); } catch { return null; }
    if (!HC) return null;

    const { initialize, requestPermission, readRecords, getSdkStatus, SdkAvailabilityStatus } = HC;

    const sdkStatus = await getSdkStatus();
    if (sdkStatus !== SdkAvailabilityStatus.SDK_AVAILABLE) return null;

    const initialized = await initialize();
    if (!initialized) return null;

    // Request permissions
    await requestPermission([
      { accessType: 'read', recordType: 'Steps' },
      { accessType: 'read', recordType: 'HeartRate' },
      { accessType: 'read', recordType: 'SleepSession' },
      { accessType: 'read', recordType: 'ActiveCaloriesBurned' },
      { accessType: 'read', recordType: 'Distance' },
      { accessType: 'read', recordType: 'Weight' },
      { accessType: 'read', recordType: 'HeartRateVariabilityRmssd' },
      { accessType: 'read', recordType: 'OxygenSaturation' },
      { accessType: 'read', recordType: 'RestingHeartRate' },
    ]);

    const startOfDay = new Date(targetDate);
    startOfDay.setHours(0, 0, 0, 0);
    const endOfDay = new Date(targetDate);
    endOfDay.setHours(23, 59, 59, 999);

    const timeRange = {
      operator: 'between' as const,
      startTime: startOfDay.toISOString(),
      endTime: endOfDay.toISOString(),
    };

    // Read all metrics in parallel
    const [stepsRes, caloriesRes, sleepRes, distanceRes, weightRes, hrvRes, spo2Res, rhrRes] =
      await Promise.allSettled([
        readRecords('Steps', { timeRangeFilter: timeRange }),
        readRecords('ActiveCaloriesBurned', { timeRangeFilter: timeRange }),
        readRecords('SleepSession', { timeRangeFilter: timeRange }),
        readRecords('Distance', { timeRangeFilter: timeRange }),
        readRecords('Weight', { timeRangeFilter: timeRange }),
        readRecords('HeartRateVariabilityRmssd', { timeRangeFilter: timeRange }),
        readRecords('OxygenSaturation', { timeRangeFilter: timeRange }),
        readRecords('RestingHeartRate', { timeRangeFilter: timeRange }),
      ]);

    const metrics: HealthMetrics = {
      metric_date: targetDate.toISOString().split('T')[0],
      source: 'health_connect',
    };

    // Steps (sum all records)
    if (stepsRes.status === 'fulfilled' && stepsRes.value.records.length > 0) {
      metrics.steps = stepsRes.value.records.reduce(
        (sum: number, r: any) => sum + (r.count ?? 0), 0
      );
    }

    // Calories
    if (caloriesRes.status === 'fulfilled' && caloriesRes.value.records.length > 0) {
      const totalJoules = caloriesRes.value.records.reduce(
        (sum: number, r: any) => sum + (r.energy?.inKilocalories ?? 0), 0
      );
      metrics.calories = Math.round(totalJoules);
    }

    // Distance (km)
    if (distanceRes.status === 'fulfilled' && distanceRes.value.records.length > 0) {
      const totalM = distanceRes.value.records.reduce(
        (sum: number, r: any) => sum + (r.distance?.inMeters ?? 0), 0
      );
      metrics.distance_km = Math.round(totalM / 100) / 10;
    }

    // Sleep (latest session)
    if (sleepRes.status === 'fulfilled' && sleepRes.value.records.length > 0) {
      const latest = sleepRes.value.records[sleepRes.value.records.length - 1] as any;
      const durationMs =
        new Date(latest.endTime).getTime() - new Date(latest.startTime).getTime();
      metrics.sleep_hours = Math.round((durationMs / 3_600_000) * 10) / 10;

      // Estimate quality from stages if available
      if (latest.stages && Array.isArray(latest.stages)) {
        const deepMs = latest.stages
          .filter((s: any) => s.stage === 5) // DEEP
          .reduce((sum: number, s: any) => {
            return sum + (new Date(s.endTime).getTime() - new Date(s.startTime).getTime());
          }, 0);
        const deepRatio = deepMs / Math.max(durationMs, 1);
        // Map 0-30% deep sleep → quality 4-9
        metrics.sleep_quality = Math.min(10, Math.max(4, Math.round(4 + deepRatio * 20)));
      }
    }

    // Weight (most recent)
    if (weightRes.status === 'fulfilled' && weightRes.value.records.length > 0) {
      const last = weightRes.value.records[weightRes.value.records.length - 1] as any;
      metrics.weight_kg = last.weight?.inKilograms;
    }

    // HRV (average of day)
    if (hrvRes.status === 'fulfilled' && hrvRes.value.records.length > 0) {
      const sum = hrvRes.value.records.reduce((s: number, r: any) => s + (r.heartRateVariabilityMillis ?? 0), 0);
      metrics.hrv = Math.round(sum / hrvRes.value.records.length);
    }

    // SpO2 (average)
    if (spo2Res.status === 'fulfilled' && spo2Res.value.records.length > 0) {
      const sum = spo2Res.value.records.reduce((s: number, r: any) => s + (r.percentage?.value ?? 0), 0);
      metrics.spo2 = Math.round((sum / spo2Res.value.records.length) * 10) / 10;
    }

    // Resting HR
    if (rhrRes.status === 'fulfilled' && rhrRes.value.records.length > 0) {
      const sum = rhrRes.value.records.reduce((s: number, r: any) => s + (r.beatsPerMinute ?? 0), 0);
      metrics.resting_heart_rate = Math.round(sum / rhrRes.value.records.length);
    }

    return metrics;
  } catch (e) {
    console.warn('[HealthConnect] Read error:', e);
    return null;
  }
}

// ── iOS HealthKit ─────────────────────────────────────────────────────────────

async function readiOSHealthKit(targetDate: Date): Promise<HealthMetrics | null> {
  try {
    let AppleHealthKit: any;
    try { AppleHealthKit = require('react-native-health'); } catch { return null; }
    if (!AppleHealthKit) return null;

    const { default: HealthKit, Permissions } = AppleHealthKit as any;

    const permissions = {
      permissions: {
        read: [
          Permissions.Steps,
          Permissions.ActiveEnergyBurned,
          Permissions.SleepAnalysis,
          Permissions.HeartRateVariability,
          Permissions.RestingHeartRate,
          Permissions.Weight,
          Permissions.OxygenSaturation,
        ],
        write: [],
      },
    };

    await new Promise<void>((resolve, reject) => {
      HealthKit.initHealthKit(permissions, (err: any) => {
        if (err) reject(err);
        else resolve();
      });
    });

    const startDate = new Date(targetDate);
    startDate.setHours(0, 0, 0, 0);
    const endDate = new Date(targetDate);
    endDate.setHours(23, 59, 59, 999);

    const opts = { startDate: startDate.toISOString(), endDate: endDate.toISOString() };

    const readHK = (fn: string, options: any): Promise<any> =>
      new Promise((resolve) => {
        (HealthKit as any)[fn](options, (_: any, results: any) => resolve(results));
      });

    const [steps, calories, sleep, hrv, rhr, weight, spo2] = await Promise.allSettled([
      readHK('getStepCount', opts),
      readHK('getActiveEnergyBurned', opts),
      readHK('getSleepSamples', opts),
      readHK('getHeartRateVariabilitySamples', opts),
      readHK('getRestingHeartRate', opts),
      readHK('getWeightSamples', opts),
      readHK('getOxygenSaturationSamples', opts),
    ]);

    const metrics: HealthMetrics = {
      metric_date: targetDate.toISOString().split('T')[0],
      source: 'apple_health',
    };

    if (steps.status === 'fulfilled') metrics.steps = steps.value?.value;
    if (calories.status === 'fulfilled' && Array.isArray(calories.value) && calories.value.length > 0) {
      metrics.calories = Math.round(calories.value.reduce((s: number, r: any) => s + r.value, 0));
    }
    if (sleep.status === 'fulfilled' && Array.isArray(sleep.value) && sleep.value.length > 0) {
      const asleepSamples = sleep.value.filter((s: any) => s.value === 'ASLEEP');
      const totalMs = asleepSamples.reduce((sum: number, s: any) => {
        return sum + (new Date(s.endDate).getTime() - new Date(s.startDate).getTime());
      }, 0);
      metrics.sleep_hours = Math.round((totalMs / 3_600_000) * 10) / 10;
    }
    if (hrv.status === 'fulfilled' && Array.isArray(hrv.value) && hrv.value.length > 0) {
      const avg = hrv.value.reduce((s: number, r: any) => s + r.value, 0) / hrv.value.length;
      metrics.hrv = Math.round(avg);
    }
    if (rhr.status === 'fulfilled') metrics.resting_heart_rate = rhr.value?.value;
    if (weight.status === 'fulfilled' && Array.isArray(weight.value) && weight.value.length > 0) {
      metrics.weight_kg = weight.value[weight.value.length - 1]?.value;
    }
    if (spo2.status === 'fulfilled' && Array.isArray(spo2.value) && spo2.value.length > 0) {
      const avg = spo2.value.reduce((s: number, r: any) => s + r.value, 0) / spo2.value.length;
      metrics.spo2 = Math.round(avg * 10) / 10;
    }

    return metrics;
  } catch (e) {
    console.warn('[HealthKit] Read error:', e);
    return null;
  }
}

// ── Sync to backend ───────────────────────────────────────────────────────────

async function syncMetricsToBackend(metrics: HealthMetrics): Promise<boolean> {
  try {
    // Filter out undefined fields
    const payload = Object.fromEntries(
      Object.entries(metrics).filter(([, v]) => v !== undefined && v !== null)
    );
    if (Object.keys(payload).length <= 2) return false; // only date + source, nothing useful

    await apiRequest('/health/sync', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return true;
  } catch (e) {
    console.warn('[HealthSync] Backend sync failed:', e);
    return false;
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/** Sync today's health data from device to Personal OS backend. */
export async function syncHealthDataNow(): Promise<{ synced: boolean; metrics: HealthMetrics | null }> {
  const today = new Date();
  let metrics: HealthMetrics | null = null;

  if (Platform.OS === 'android') {
    metrics = await readAndroidHealthConnect(today);
  } else if (Platform.OS === 'ios') {
    metrics = await readiOSHealthKit(today);
  }

  if (!metrics) return { synced: false, metrics: null };

  const synced = await syncMetricsToBackend(metrics);
  return { synced, metrics };
}

/**
 * Fetch current watch face data from backend.
 * Used to display complications on watch / widget.
 */
export async function getWatchFaceData(): Promise<Record<string, any> | null> {
  try {
    return await apiRequest<Record<string, any>>('/watch/face');
  } catch {
    return null;
  }
}

/** Start periodic background sync (call once in App.tsx). */
export async function startBackgroundSync(): Promise<void> {
  // Initial sync when app opens
  await syncHealthDataNow();

  // Sync whenever app comes to foreground via AppState listener
  // (Background fetch requires expo-background-fetch + native build)
  const { AppState } = require('react-native');
  let lastSync = Date.now();

  AppState.addEventListener('change', async (nextState: string) => {
    if (nextState === 'active') {
      const now = Date.now();
      // Throttle: max once every 15 minutes
      if (now - lastSync > 15 * 60 * 1000) {
        lastSync = now;
        await syncHealthDataNow();
      }
    }
  });
}
