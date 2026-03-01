const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export interface Objective {
  id: number;
  title: string;
  description: string | null;
  category: string;
  status: string;
  priority_weight: number;
  target_date: string | null;
  created_at: string;
  key_results: KeyResult[];
}

export interface Task {
  id: number;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  category: string | null;
  due_date: string | null;
  completed_at: string | null;
  key_result_id: number | null;
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
  };
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
  calendar: (days = 60) =>
    apiFetch<{ events: CalendarEvent[] }>(`/api/calendar?days=${days}`),
  brainDumps: () => apiFetch<{ brain_dumps: BrainDump[] }>("/api/brain-dumps"),
  shopping: () => apiFetch<{ items: { id: number; title: string }[] }>("/api/shopping"),
  health: () => apiFetch<{ status: string }>("/api/health"),
  generateToken: () => apiPost<{ token: string }>("/api/auth/token"),
};
