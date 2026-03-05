const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");

export async function validateToken(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/auth/validate`, {
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

async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "PATCH",
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
  time_of_day: string;
  sort_order: number;
  completed_today: boolean;
}

export interface ShoppingDefault {
  id: number;
  title: string;
  category: string | null;
  active: boolean;
  created_at: string;
}

export interface CalendarEvent {
  id: number;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string | null;
  all_day: boolean;
  event_type: string;
  linked_task_id: number | null;
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

export interface FitnessSplitExercise {
  name: string;
  sets?: number | null;
  reps?: string | null;
  target_weight?: number | null;
}

export interface FitnessSplit {
  id: number;
  name: string;
  exercises: FitnessSplitExercise[];
  day_of_week: number | null;
  order_in_rotation: number | null;
  created_at: string;
  workout_count: number;
  last_used: string | null;
  is_next: boolean;
}

export interface FitnessSplitsResponse {
  splits: FitnessSplit[];
  next_split_id: number | null;
}

export interface FitnessProgressionPoint {
  date: string;
  weight: number;
  reps?: number | null;
  sets?: number | null;
}

export interface FitnessProgression {
  exercise: string;
  data_points: FitnessProgressionPoint[];
}

// ─── Settings Types ─────────────────────────────────────────────────────────

export interface UserSettings {
  profile: {
    first_name: string | null;
    telegram_username: string | null;
    timezone: string;
  };
  toggles: {
    priorities_enabled: boolean;
    review_enabled: boolean;
    proactive_enabled: boolean;
    reflection_enabled: boolean;
  };
  times: {
    morning_brief_time: string;
    evening_review_time: string;
    weekly_reflection_day: string;
    weekly_reflection_time: string;
  };
  category_weights: Record<string, number>;
}

export interface SettingsUpdateBody {
  priorities_enabled?: boolean;
  review_enabled?: boolean;
  proactive_enabled?: boolean;
  reflection_enabled?: boolean;
  morning_brief_time?: string;
  evening_review_time?: string;
  weekly_reflection_day?: string;
  weekly_reflection_time?: string;
  category_weights?: Record<string, number>;
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

// ─── Achievement Types ────────────────────────────────────────────────────────

export interface AchievementProgress {
  current: number | null;
  target: number | null;
}

export interface Achievement {
  id: number;
  key: string;
  title: string;
  description: string;
  emoji: string;
  category: string;
  xp_reward: number;
  condition_type: string;
  condition_value: number;
  unlocked: boolean;
  unlocked_at: string | null;
  progress: AchievementProgress;
}

export interface RecentAchievement {
  id: number;
  key: string;
  title: string;
  description: string;
  emoji: string;
  category: string;
  xp_reward: number;
  unlocked_at: string;
}

export interface GamificationStats {
  xp: number;
  level: number;
  level_title: string;
  xp_progress: number;
  xp_to_next: number;
  recent_achievements: {
    id: number;
    title: string;
    emoji: string;
    category: string;
    xp_reward: number;
    unlocked_at: string;
  }[];
}

// ─── Daily Suggestions Types ─────────────────────────────────────────────────

export interface FokusTodayItem {
  task: string;
  begruendung: string;
}

export interface DailySuggestions {
  fokus_heute: FokusTodayItem[];
  tipp: string;
  streak_warnung: string | null;
  dimension_check: string | null;
}

export interface DailySuggestionsResponse {
  date: string;
  suggestions: DailySuggestions | null;
}

export interface DailySuggestionsHistoryEntry {
  date: string;
  suggestions: DailySuggestions;
  created_at: string;
}

export interface DailySuggestionsHistory {
  history: DailySuggestionsHistoryEntry[];
}

// ─── Behavioral Patterns Types ────────────────────────────────────────────────

export interface MissedRoutine {
  id: number;
  title: string;
  completion_rate: number;
  completions_30d: number;
}

export interface DriftingObjective {
  id: number;
  title: string;
  category: string | null;
  days_inactive: number;
}

export interface MoodTrend {
  recent_avg: number;
  prior_avg: number;
  delta: number;
  direction: "up" | "down" | "stable";
}

export interface BehavioralPatterns {
  missed_routines: MissedRoutine[];
  drifting_objectives: DriftingObjective[];
  mood_trend: MoodTrend | null;
}

// ─── Confidence Scoring Types (E5) ────────────────────────────────────────────

export interface ConfidenceEscalation {
  code: string;
  severity: "high" | "medium" | "low";
  message: string;
}

export interface AutopilotConfidence {
  confidence: number;
  level: "high" | "medium" | "low";
  scores: {
    data_recency: number;
    objective_coverage: number;
    routine_adherence: number;
    reflection_freshness: number;
  };
  escalations: ConfidenceEscalation[];
}

// ─── Active Hours Types (E4) ──────────────────────────────────────────────────

export interface ActiveHoursWindow {
  start_hour: number;
  end_hour: number;
  activity_score: number;
}

export interface ActiveHoursResponse {
  hours: Record<string, number>;
  peak_hour: number | null;
  recommended_windows: ActiveHoursWindow[];
  total_events: number;
  days_analyzed: number;
}

// ─── Autopilot Intelligence Types ─────────────────────────────────────────────

export interface AutopilotDailyPlanItem {
  id: number;
  type: "task" | "routine" | "event";
  title: string;
  reason: string;
  category?: string | null;
  completed?: boolean;
  time_of_day?: string | null;
}

export interface AutopilotDailyPlanSection {
  id: string;
  title: string;
  items: AutopilotDailyPlanItem[];
}

export interface AutopilotDailyPlan {
  date: string;
  generated_by: "ai" | "deterministic";
  summary: string;
  sections: AutopilotDailyPlanSection[];
}

export interface AutopilotActionQueueCounts {
  planned: number;
  suggested: number;
  accepted: number;
  completed: number;
  snoozed: number;
}

export interface AutopilotActionQueueItem {
  id: number;
  state: string;
  item_type: string;
  title: string;
  reason?: string | null;
  linked_task_id?: number | null;
}

export interface AutopilotActionQueue {
  items: AutopilotActionQueueItem[];
  counts: AutopilotActionQueueCounts;
  total_active: number;
}

export interface AutopilotNextAction {
  task: {
    id: number;
    title: string;
    category?: string | null;
    objective_title?: string | null;
    is_blocked?: boolean;
    blocker_title?: string | null;
  };
  reason?: string | null;
  score?: number | null;
}

// ─── Reflection Types ─────────────────────────────────────────────────────────

export interface ReflectionAiSummary {
  recommendations: string[];
  goal_adjustments: string[];
  motivation: string;
}

export interface WeeklyReflection {
  id: number;
  week_start: string;
  week_number: number;
  year: number;
  status: string;
  week_score: number | null;
  biggest_win: string | null;
  biggest_blocker: string | null;
  key_learning: string | null;
  raw_answers: Record<string, unknown>;
  priorities_next_week: unknown | null;
  ai_summary: ReflectionAiSummary | null;
  created_at: string;
  updated_at: string | null;
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
  calendar: (days = 60, daysPast = 0) =>
    apiFetch<{ events: CalendarEvent[] }>(`/api/calendar?days=${days}&days_past=${daysPast}`),
  updateCalendarEvent: (id: number, body: Partial<{ title: string; description: string | null; start_time: string; end_time: string | null; all_day: boolean; event_type: string }>) =>
    apiPut<CalendarEvent>(`/api/calendar/${id}`, body),
  addCalendarNotes: (id: number, notes: string) =>
    apiPost<CalendarEvent>(`/api/calendar/${id}/notes`, { notes }),
  brainDumps: () => apiFetch<{ brain_dumps: BrainDump[] }>("/api/brain-dumps"),
  shopping: () => apiFetch<{ items: { id: number; title: string; created_at: string }[] }>("/api/shopping"),
  shoppingDefaults: () => apiFetch<{ defaults: ShoppingDefault[] }>("/api/shopping/defaults"),
  createShoppingDefault: (body: { title: string; category?: string }) =>
    apiPost<{ ok: boolean; id: number; title: string; category: string | null }>("/api/shopping/defaults", body),
  loadShoppingDefaults: () =>
    apiPost<{ ok: boolean; added: number; items: { title: string; category: string | null }[] }>("/api/shopping/load-defaults"),
  deleteShoppingDefault: (id: number) => apiDelete<{ ok: boolean }>(`/api/shopping/defaults/${id}`),
  health: () => apiFetch<{ status: string }>("/api/health"),
  generateToken: () => apiPost<{ token: string }>("/api/auth/token"),
  fitnessSummary: () => apiFetch<FitnessSummary>("/api/fitness/summary"),
  fitnessExercises: () => apiFetch<{ exercises: FitnessExercise[] }>("/api/fitness/exercises"),
  fitnessPRs: () => apiFetch<{ prs: FitnessPR[] }>("/api/fitness/prs"),
  fitnessSplits: () => apiFetch<FitnessSplitsResponse>("/api/fitness/splits"),
  createFitnessSplit: (body: { name: string; exercises: FitnessSplitExercise[]; day_of_week?: number | null; order_in_rotation?: number | null }) =>
    apiPost<FitnessSplit>("/api/fitness/splits", body),
  fitnessProgression: (exercise: string) =>
    apiFetch<FitnessProgression>(`/api/fitness/progression/${encodeURIComponent(exercise)}`),
  weeklySummary: () => apiFetch<WeeklySummary>("/api/weekly-summary"),
  achievements: () => apiFetch<{ achievements: Achievement[] }>("/api/achievements"),
  recentAchievements: (limit = 5) => apiFetch<{ recent: RecentAchievement[] }>(`/api/achievements/recent?limit=${limit}`),
  checkAchievements: () => apiPost<{ ok: boolean; newly_unlocked: { key: string; title: string; emoji: string; xp_reward: number }[]; count: number }>("/api/achievements/check", {}),
  gamificationStats: () => apiFetch<GamificationStats>("/api/gamification/stats"),
  priorities: () => apiFetch<{ priorities: Priority[] }>("/api/priorities"),
  completeTask: (taskId: number) => apiPost<{ ok: boolean }>(`/api/tasks/${taskId}/complete`),
  completeRoutine: (routineId: number) => apiPost<{ ok: boolean }>(`/api/routines/${routineId}/complete`),
  // CRUD — Create
  createTask: (body: { title: string; category?: string | null; priority?: number; due_date?: string | null; objective_id?: number | null; description?: string | null }) =>
    apiPost<{ ok: boolean; id: number; title: string }>("/api/tasks", body),
  createObjective: (body: { title: string; category?: string; description?: string | null; target_date?: string | null }) =>
    apiPost<{ ok: boolean; id: number; title: string }>("/api/objectives", body),
  createRoutine: (body: { title: string; description?: string | null; frequency_human?: string; time_of_day?: string }) =>
    apiPost<{ ok: boolean; id: number; title: string }>("/api/routines", body),
  // CRUD — Update / Delete
  updateObjective: (id: number, body: Partial<{ title: string; category: string; description: string | null; target_date: string | null; status: string }>) =>
    apiPut<{ ok: boolean }>(`/api/objectives/${id}`, body),
  deleteObjective: (id: number) => apiDelete<{ ok: boolean }>(`/api/objectives/${id}`),
  updateTask: (id: number, body: Partial<{ title: string; category: string | null; priority: number; due_date: string | null; status: string; objective_id: number | null }>) =>
    apiPut<{ ok: boolean }>(`/api/tasks/${id}`, body),
  deleteTask: (id: number) => apiDelete<{ ok: boolean }>(`/api/tasks/${id}`),
  updateRoutine: (id: number, body: Partial<{ title: string; description: string | null; frequency_human: string | null; status: string; time_of_day: string; sort_order: number }>) =>
    apiPut<{ ok: boolean }>(`/api/routines/${id}`, body),
  deleteRoutine: (id: number) => apiDelete<{ ok: boolean }>(`/api/routines/${id}`),
  updateBrainDump: (id: number, body: { raw_input: string }) =>
    apiPut<{ ok: boolean }>(`/api/brain-dumps/${id}`, body),
  deleteBrainDump: (id: number) => apiDelete<{ ok: boolean }>(`/api/brain-dumps/${id}`),
  deleteLog: (id: number) => apiDelete<{ ok: boolean }>(`/api/logs/${id}`),
  // Settings
  getSettings: () => apiFetch<UserSettings>("/api/settings"),
  updateProfile: (body: { first_name?: string; timezone?: string }) =>
    apiPut<{ ok: boolean; first_name: string | null; timezone: string | null }>("/api/settings/profile", body),
  updateSettings: (body: SettingsUpdateBody) =>
    apiPut<{ ok: boolean }>("/api/settings", body),
  exportData: () => apiFetch<unknown>("/api/settings/export"),
  deleteAccount: () => apiDelete<{ ok: boolean }>("/api/settings/account"),
  reflections: () => apiFetch<{ reflections: WeeklyReflection[] }>("/api/reflections"),
  reflection: (id: number) => apiFetch<WeeklyReflection>(`/api/reflections/${id}`),
  regenerateReflectionInsights: (id: number) =>
    apiPost<{ ok: boolean; ai_summary: Record<string, unknown> }>(`/api/reflections/${id}/insights`, {}),
  todaySuggestions: () => apiFetch<DailySuggestionsResponse>("/api/suggestions/today"),
  suggestionsHistory: (days = 14) => apiFetch<DailySuggestionsHistory>(`/api/suggestions/history?days=${days}`),
  regenerateSuggestions: () => apiPost<DailySuggestionsResponse>("/api/suggestions/regenerate", {}),
  // Autopilot intelligence
  autopilotDailyPlan: () => apiFetch<AutopilotDailyPlan>("/api/autopilot/daily-plan"),
  autopilotActionQueue: () => apiFetch<AutopilotActionQueue>("/api/autopilot/action-queue"),
  autopilotNextAction: () => apiFetch<AutopilotNextAction>("/api/autopilot/next-action"),
  autopilotCompleteQueueItem: (id: number) =>
    apiPatch<{ ok: boolean }>(`/api/autopilot/action-queue/${id}`, { state: "completed" }),
  autopilotPatterns: () => apiFetch<BehavioralPatterns>("/api/autopilot/patterns"),
  autopilotActiveHours: (days = 30) => apiFetch<ActiveHoursResponse>(`/api/autopilot/active-hours?days=${days}`),
  autopilotConfidence: () => apiFetch<AutopilotConfidence>("/api/autopilot/confidence"),
};
