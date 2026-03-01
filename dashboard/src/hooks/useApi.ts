"use client";

import useSWR from "swr";
import { api } from "@/lib/api";

export function useDashboard() {
  return useSWR("dashboard", () => api.dashboard(), { refreshInterval: 60_000 });
}

export function useObjectives() {
  return useSWR("objectives", () => api.objectives(), { refreshInterval: 120_000 });
}

export function useTasks(status?: string) {
  const key = status ? `tasks-${status}` : "tasks";
  return useSWR(key, () => api.tasks(status), { refreshInterval: 60_000 });
}

export function useAllTasks() {
  return useSWR("tasks-all", () => api.allTasks(), { refreshInterval: 60_000 });
}

export function useLogs(log_type?: string, days = 30) {
  const key = `logs-${log_type || "all"}-${days}`;
  return useSWR(key, () => api.logs(log_type, days), { refreshInterval: 120_000 });
}

export function useRoutines() {
  return useSWR("routines", () => api.routines(), { refreshInterval: 60_000 });
}

export function useCalendar(days = 60) {
  return useSWR(`calendar-${days}`, () => api.calendar(days), { refreshInterval: 300_000 });
}

export function useBrainDumps() {
  return useSWR("brain-dumps", () => api.brainDumps(), { refreshInterval: 120_000 });
}

export function useShopping() {
  return useSWR("shopping", () => api.shopping(), { refreshInterval: 60_000 });
}

export function useFitnessSummary() {
  return useSWR("fitness-summary", () => api.fitnessSummary(), { refreshInterval: 300_000 });
}

export function useFitnessExercises() {
  return useSWR("fitness-exercises", () => api.fitnessExercises(), { refreshInterval: 300_000 });
}

export function useFitnessPRs() {
  return useSWR("fitness-prs", () => api.fitnessPRs(), { refreshInterval: 300_000 });
}
