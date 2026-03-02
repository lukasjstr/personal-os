const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function validateToken(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/health`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("api_token");
}

export function setToken(token: string) {
  localStorage.setItem("api_token", token);
}

export function clearToken() {
  localStorage.removeItem("api_token");
}

export function hasToken(): boolean {
  return !!getToken();
}

async function apiFetch<T>(path: string): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (res.status === 401) {
    throw new Error("UNAUTHORIZED");
  }
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

async function apiDelete<T>(path: string): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "DELETE",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
    },
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface KeyResult {
  id: number;
  title: string;
  metric_type: string;
  target_value: number | null;
  current_value: number;
  unit: string | null;
  frequency: string;
  status: string;
  progress_pct: number;
}

export interface ObjectiveTask {
  id: number;
  title: string;
  status: string;
  priority: number;
  parent_task_id: number | null;
}

export interface Objective {
  id: number;
  title: string;
  description: string | null;
  category: string;
  status: string;
  priority_weight: number;
  parent_objective_id: number | null;
  target_date: string | null;
  created_at: string;
  key_results: KeyResult[];
  tasks: ObjectiveTask[];
}

export interface Task {
  id: number;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  category: string | null;
  due_date: string | null;
  is_overdue: boolean;
  completed_at: string | null;
  key_result_id: number | null;
  objective_id: number | null;
  parent_task_id: number | null;
  blocked_by_task_id: number | null;
  key_result_title: string | null;
  objective_title: string | null;
  created_at: string;
}

export interface Log {
  id: number;
  log_type: string;
  data: Record<string, unknown>;
  source: string;
  raw_input: string | null;
  logged_at: string;
  key_result_id: number | null;
}

export interface Routine {
  id: number;
  title: string;
  description: string | null;
  schedule_cron: string | null;
  frequency_human: string | null;
  status: string;
  completed_today: boolean;
}

export interface CalendarEvent {
  id: number;
  title: string;
  start_time: string;
  end_time: string | null;
  all_day: boolean;
  event_type: string;
}

export interface BrainDump {
  id: number;
  raw_input: string;
  processed: boolean;
  ai_interpretation: string | null;
  linked_objective_id: number | null;
  created_at: string;
}

export interface DashboardStats {
  user: { id: number; first_name: string | null; timezone: string };
  stats: {
    active_objectives: number;
    open_tasks: number;
    shopping_items: number;
    water_today_liters: number;
    workouts_this_week: number;
    latest_mood: number | null;
    routines_total: number;
    routines_done_today: number;
    streak_days: number;
    total_xp: number;
    level: number;
    level_title: string;
    xp_progress: number;
    xp_to_next: number;
  };
}

export interface FitnessExerciseEntry {
  exercise: string;
  weight?: number | null;
  reps?: number | null;
  sets?: number | null;
  duration_min?: number | null;
}

export interface FitnessSession {
  date: string;
  exercises: FitnessExerciseEntry[];
}

export interface FitnessVolumeEntry {
  week: string;
  volume: number;
}

export interface FitnessSummary {
  total_workout_days: number;
  workout_days: string[];
  volume_by_week: FitnessVolumeEntry[];
  last_sessions: FitnessSession[];
}

export interface FitnessExercise {
  name: string;
  count: number;
  max_weight: number;
  last_done: string;
}

export interface FitnessPR {
  exercise: string;
  weight: number;
  reps?: number | null;
  date: string;
}

// ─── Phase 4 Types ─────────────────────────────────────────────────────────

export interface WeeklySummary {
  week_start: string;
  tasks_done_this_week: number;
  tasks_open: number;
  workout_days: number;
  routine_completion_rate: number;
  mood_avg: number | null;
  mood_scores: number[];
  water_avg_liters: number;
}

export interface Priority {
  rank: number;
  score: number;
  task_id: number;
  title: string;
  priority: number;
  category: string | null;
  due_date: string | null;
  is_overdue: boolean;
  objective_title: string | null;
}

export interface RoutineHistoryEntry {
  id: number;
  title: string;
  completions: string[];
  streak: number;
}

export interface RoutinesHistory {
  days: string[];
  routines: RoutineHistoryEntry[];
}

// ─── API functions ─────────────────────────────────────────────────────────

export const fetcher = (path: string) => apiFetch(path);

export const api = {
  dashboard: () => apiFetch<DashboardStats>("/api/dashboard"),
  objectives: () => apiFetch<{ objectives: Objective[] }>("/api/objectives"),
  tasks: (status?: string) =>
    apiFetch<{ tasks: Task[] }>(`/api/tasks${status ? `?status=${status}` : ""}`),
  allTasks: async () => {
    const [active, done, cancelled] = await Promise.all([
      apiFetch<{ tasks: Task[] }>("/api/tasks"),
      apiFetch<{ tasks: Task[] }>("/api/tasks?status=done"),
      apiFetch<{ tasks: Task[] }>("/api/tasks?status=cancelled"),
    ]);
    return { tasks: [...active.tasks, ...done.tasks, ...cancelled.tasks] };
  },
  logs: (log_type?: string, days = 30) =>
    apiFetch<{ logs: Log[] }>(
      `/api/logs?days=${days}${log_type ? `&log_type=${log_type}` : ""}`
    ),
  routines: () => apiFetch<{ routines: Routine[] }>("/api/routines"),
  routinesHistory: (days = 7) =>
    apiFetch<RoutinesHistory>(`/api/routines/history?days=${days}`),
  calendar: (days = 60) =>
    apiFetch<{ events: CalendarEvent[] }>(`/api/calendar?days=${days}`),
  brainDumps: () => apiFetch<{ brain_dumps: BrainDump[] }>("/api/brain-dumps"),
  shopping: () => apiFetch<{ items: { id: number; title: string }[] }>("/api/shopping"),
  health: () => apiFetch<{ status: string }>("/api/health"),
  generateToken: () => apiPost<{ token: string }>("/api/auth/token"),
  fitnessSummary: () => apiFetch<FitnessSummary>("/api/fitness/summary"),
  fitnessExercises: () => apiFetch<{ exercises: FitnessExercise[] }>("/api/fitness/exercises"),
  fitnessPRs: () => apiFetch<{ prs: FitnessPR[] }>("/api/fitness/prs"),
  weeklySummary: () => apiFetch<WeeklySummary>("/api/weekly-summary"),
  priorities: () => apiFetch<{ priorities: Priority[] }>("/api/priorities"),
  completeTask: (taskId: number) => apiPost<{ ok: boolean }>(`/api/tasks/${taskId}/complete`),
  completeRoutine: (routineId: number) => apiPost<{ ok: boolean }>(`/api/routines/${routineId}/complete`),
  // CRUD
  updateObjective: (id: number, body: Partial<{ title: string; category: string; description: string | null; target_date: string | null; status: string }>) =>
    apiPut<{ ok: boolean }>(`/api/objectives/${id}`, body),
  deleteObjective: (id: number) => apiDelete<{ ok: boolean }>(`/api/objectives/${id}`),
  updateTask: (id: number, body: Partial<{ title: string; category: string | null; priority: number; due_date: string | null; status: string; objective_id: number | null }>) =>
    apiPut<{ ok: boolean }>(`/api/tasks/${id}`, body),
  deleteTask: (id: number) => apiDelete<{ ok: boolean }>(`/api/tasks/${id}`),
  updateRoutine: (id: number, body: Partial<{ title: string; description: string | null; frequency_human: string | null; status: string }>) =>
    apiPut<{ ok: boolean }>(`/api/routines/${id}`, body),
  deleteRoutine: (id: number) => apiDelete<{ ok: boolean }>(`/api/routines/${id}`),
  updateBrainDump: (id: number, body: { raw_input: string }) =>
    apiPut<{ ok: boolean }>(`/api/brain-dumps/${id}`, body),
  deleteBrainDump: (id: number) => apiDelete<{ ok: boolean }>(`/api/brain-dumps/${id}`),
  deleteLog: (id: number) => apiDelete<{ ok: boolean }>(`/api/logs/${id}`),
};
