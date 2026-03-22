const API_URL = (() => {
  // In the browser, always prefer same-origin API calls via the nginx proxy.
  // This avoids stale env builds, mixed http/https issues, and cert problems on devices.
  if (typeof window !== "undefined") return window.location.origin;
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  return "http://localhost:8000";
})();

function normalizeToken(raw: string): string {
  return raw
    .trim()
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/^['"`]+|['"`]+$/g, "");
}

export async function validateToken(token: string): Promise<boolean> {
  const clean = normalizeToken(token);
  try {
    let res = await fetch(`${API_URL}/api/auth/validate`, {
      headers: { Authorization: `Bearer ${clean}` },
      cache: "no-store",
    });
    if (!res.ok) {
      res = await fetch(`${API_URL}/api/auth/validate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${clean}` },
        cache: "no-store",
      });
    }
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

async function apiUpload<T>(path: string, file: File | Blob, contentType?: string): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": contentType || file.type || "application/octet-stream",
    },
    body: file,
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface NodeRelation {
  id: number;
  relation_type: "blocks" | "depends_on" | "contributes_to" | "unlocks";
  from_type: "task" | "objective" | "key_result";
  from_id: number;
  to_type: "task" | "objective" | "key_result";
  to_id: number;
  note: string | null;
  created_at: string;
}

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
  key_result_id: number | null;
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
  relations?: NodeRelation[];
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
  relations?: NodeRelation[];
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
    quiet_hour_start: number;
    quiet_hour_end: number;
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
  quiet_hour_start?: number;
  quiet_hour_end?: number;
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

// ─── Goal Momentum Types (F3) ─────────────────────────────────────────────────

export interface GoalMomentumItem {
  id: number;
  title: string;
  category: string | null;
  momentum: number;
  tasks_done_14d: number;
  days_since_last_task: number;
  level: "high" | "medium" | "low";
}

export interface GoalMomentumResponse {
  objectives: GoalMomentumItem[];
  portfolio_momentum: number;
  portfolio_level: "high" | "medium" | "low";
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
  // Epic 4.2 trust signals (additive)
  source_type?: "ai" | "deterministic_fallback";
  confidence_level?: "high" | "medium" | "low" | null;
  confidence_reason?: string | null;
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
    // Epic 4.1: graph-aware explainability fields
    why_selected?: string | null;
    unlocks_count?: number;
    contributes_to?: Array<{ type: string; id: number; title?: string | null }>;
  };
  reason?: string | null;
  score?: number | null;
  // Epic 4.1: top-level mirrors (same data, surfaced for convenience)
  why_selected?: string | null;
  unlocks_count?: number;
  contributes_to?: Array<{ type: string; id: number; title?: string | null }>;
  // Epic 4.2 trust signals (additive)
  source_type?: "ai" | "deterministic_fallback";
  confidence_level?: "high" | "medium" | "low" | null;
  confidence_reason?: string | null;
}

// ─── Autopilot Suggestions (P2.3) ────────────────────────────────────────────

export interface AutopilotSuggestionItem {
  type: string;
  message: string;
  action_hint: string;
  notification_id: number | null;
  // Epic 4.2 trust signals (additive)
  source_type?: "ai" | "deterministic_fallback";
  confidence_level?: "high" | "medium" | "low" | null;
  confidence_reason?: string | null;
}

export interface AutopilotSuggestionsResponse {
  suggestions: AutopilotSuggestionItem[];
  generated_at: string;
}

// ─── Epic 2.1: Unified Planner Snapshot Types ─────────────────────────────────

export interface PlannerBlockerRef {
  type: string;
  id: number;
  title: string | null;
}

export interface PlannerBlocker {
  task_id: number;
  task_title: string;
  blocked_by: PlannerBlockerRef[];
}

export interface PlannerSuggestion {
  notification_id: number | null;
  type: string;
  message: string;
  title: string | null;
}

export interface PlannerProgressSummary {
  completed_today: number;
  open_tasks: number;
  active_objectives: number;
  routines_done: number;
  routines_pending: number;
  pending_reminders: number;
  pending_nudges: number;
}

export interface PlannerSnapshot {
  date: string;
  generated_by: "ai" | "deterministic";
  // Epic 4.2 trust signals (additive)
  source_type?: "ai" | "deterministic_fallback";
  confidence_level?: "high" | "medium" | "low" | null;
  confidence_reason?: string | null;
  next_action: (AutopilotNextAction["task"] & {
    type: "task";
    reason: string | null;
    why_selected?: string | null;
    blocked_by?: PlannerBlockerRef[];
    unlocks_count?: number;
    contributes_to?: PlannerBlockerRef[];
  }) | null;
  today_plan: AutopilotDailyPlan;
  blockers: PlannerBlocker[];
  suggestions: PlannerSuggestion[];
  progress_summary: PlannerProgressSummary;
}

// ─── Daily Intelligence Types ─────────────────────────────────────────────────

export interface DailyPlan {
  top_tasks: {
    task_id: number;
    title: string;
    objective_title: string | null;
    kr_title: string | null;
    reason: string;
    estimated_minutes: number;
    energy_required: "low" | "medium" | "high";
  }[];
  focus_block: {
    suggested_start: string;
    duration_minutes: number;
    description: string;
  } | null;
  motivational_kickoff: string;
}

export interface DailyContext {
  id: number;
  date: string;
  energy: number | null;
  hours_available: number | null;
  focus_area: string | null;
  mood_note: string | null;
  daily_plan: DailyPlan | null;
}

export interface StreakRisk {
  objective_id: number;
  title: string;
  category: string;
  days_since: number;
  open_task_count: number;
  suggested_action: string | null;
}

export interface EveningCheckin {
  id: number;
  date: string;
  tasks_planned: number;
  tasks_completed: number;
  win_of_day: string | null;
  blocker: string | null;
  gap_analysis: {
    completion_rate_pct: number;
    gap_summary: string;
    positive_note: string;
    tomorrow_focus: { objective_title: string; suggested_task_title: string } | null;
    pattern_note: string;
  } | null;
}

// ─── Health Daily ─────────────────────────────────────────────────────────────

export interface SupplementItem {
  name: string;
  dose: string;
}

export interface DailyHealthData {
  date: string;
  supplements: {
    morning: SupplementItem[];
    midday: SupplementItem[];
    evening: SupplementItem[];
  };
  fitness: {
    split: string | null;
    focus: string | null;
    exercises: string[];
    is_rest_day: boolean;
  };
  macros: {
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
    water: string;
  };
  last_weights: Array<{
    exercise: string;
    weight_kg: number | null;
    sets: number | null;
    reps: number | null;
    date: string;
  }>;
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

export interface UserDoc {
  id: number;
  title: string;
  emoji: string;
  content: string;
  sort_order: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ObjectiveAnalysis {
  parent_suggestions: Array<{
    child_objective_id: number;
    child_title: string;
    suggested_parent_id: number;
    parent_title: string;
    reason: string;
  }>;
  synergies: Array<{
    objective_ids: number[];
    titles: string[];
    synergy: string;
  }>;
  overlaps: Array<{
    objective_ids: number[];
    titles: string[];
    overlap: string;
    suggestion: string;
  }>;
  missing_links: Array<{
    objective_ids: number[];
    titles: string[];
    connection: string;
  }>;
  summary: string;
}

export interface FinanceTransaction {
  id: number;
  amount: number;
  type: "income" | "expense";
  category: string;
  description: string;
  date: string;
  is_recurring: boolean;
}

export interface FinanceBudget {
  id: number;
  category: string;
  monthly_limit: number;
}

export interface FinanceSummary {
  month: string;
  total_income: number;
  total_expenses: number;
  balance: number;
  savings_rate: number;
  by_category: Record<string, number>;
  category_lines: string[];
  recent_transactions: FinanceTransaction[];
}

// ─── Health Sync Types ────────────────────────────────────────────────────────

export interface HealthMetric {
  id: number;
  type: string;
  date: string;
  hours?: number;
  count?: number;
  score?: number;
  kg?: number;
  quality?: number;
  resting_heart_rate?: number;
  spo2?: number;
  source?: string;
}

export interface HealthShortcutSetup {
  endpoint: string;
  method: string;
  headers: Record<string, string>;
  payload_example: Record<string, string>;
  instructions: string[];
  huawei_instructions: string[];
}

// ─── Pattern Insights Types ───────────────────────────────────────────────────

export interface PatternInsight {
  id: number;
  type: string;
  title: string;
  description: string;
  created_at: string;
}

export interface ConsistencyScore {
  score: number;
  label: string;
  emoji: string;
  components: {
    routine_rate: number;
    task_rate: number;
    logging_rate: number;
  };
}

export interface PatternInsightsResponse {
  insights: PatternInsight[];
  consistency_score: ConsistencyScore | null;
}

export interface CorrelationInsight {
  type: string;
  title: string;
  description: string;
  data: {
    correlation_r: number;
    strength: string;
    n_pairs: number;
    [key: string]: unknown;
  };
}

// ─── Goal Onboarding Types ────────────────────────────────────────────────

export interface GoalQuestion {
  id: string;
  label: string;
  placeholder?: string;
  hint?: string;
  type: "text" | "choice";
  options?: string[];
}

export interface GoalClarifyResponse {
  category: string;
  category_emoji: string;
  questions: GoalQuestion[];
}

export interface GoalKROption {
  title: string;
  metric_type: string;
  target_value: number;
  current_value: number;
  unit: string;
  why: string;
  recommended: boolean;
  difficulty: string;
}

export interface GoalOptionsResponse {
  objective: { title: string; description: string; emoji: string; category: string; target_date: string };
  kr_options: GoalKROption[];
}

export interface GoalPlan {
  objective: { title: string; description: string; category: string; target_date: string; emoji: string };
  key_results: unknown[];
  tasks: { title: string; priority: number; due_days: number }[];
  routines: { title: string; frequency: string; time_of_day: string }[];
  reminders: { title: string; message: string }[];
  shopping_items: string[];
  motivation_message: string;
  first_step: string;
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
  createCalendarEvent: (body: { title: string; start_time: string; event_type?: string; end_time?: string; linked_routine_id?: number; linked_task_id?: number }) =>
    apiPost<CalendarEvent>("/api/calendar", body),
  deleteCalendarEvent: (id: number) => apiDelete<{ ok: boolean }>(`/api/calendar/${id}`),
  addCalendarNotes: (id: number, notes: string) =>
    apiPost<CalendarEvent>(`/api/calendar/${id}/notes`, { notes }),
  shiftDayRoutines: (weekday: number, target_hour: number) =>
    apiPost<{ shifted: number }>("/api/calendar/shift-routines", { weekday, target_hour }),
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
  xpHistory: (days = 30) => apiFetch<{ history: { date: string; xp: number }[]; days: number; total_xp: number }>(`/api/gamification/xp-history?days=${days}`),
  goalMomentum: () => apiFetch<GoalMomentumResponse>("/api/gamification/momentum"),
  gamificationStats: () => apiFetch<GamificationStats>("/api/gamification/stats"),
  priorities: () => apiFetch<{ priorities: Priority[] }>("/api/priorities"),
  completeTask: (taskId: number) => apiPost<{ ok: boolean }>(`/api/tasks/${taskId}/complete`),
  completeRoutine: (routineId: number) => apiPost<{ ok: boolean }>(`/api/routines/${routineId}/complete`),
  // CRUD — Create
  createTask: (body: { title: string; category?: string | null; priority?: number; due_date?: string | null; objective_id?: number | null; description?: string | null; parent_task_id?: number | null; blocked_by_task_id?: number | null }) =>
    apiPost<{ ok: boolean; id: number; title: string }>("/api/tasks", body),
  createObjective: (body: { title: string; category?: string; description?: string | null; target_date?: string | null; parent_objective_id?: number | null }) =>
    apiPost<{ ok: boolean; id: number; title: string }>("/api/objectives", body),
  createRoutine: (body: { title: string; description?: string | null; frequency_human?: string; time_of_day?: string }) =>
    apiPost<{ ok: boolean; id: number; title: string }>("/api/routines", body),
  // CRUD — Update / Delete
  updateObjective: (id: number, body: Partial<{ title: string; category: string; description: string | null; target_date: string | null; status: string }>) =>
    apiPut<{ ok: boolean }>(`/api/objectives/${id}`, body),
  deleteObjective: (id: number) => apiDelete<{ ok: boolean }>(`/api/objectives/${id}`),
  createKeyResult: (objectiveId: number, body: { title: string; metric_type?: string; target_value?: number | null; unit?: string | null }) =>
    apiPost<{ ok: boolean } & KeyResult>(`/api/objectives/${objectiveId}/key-results`, body),
  updateKeyResult: (objectiveId: number, krId: number, body: Partial<{ title: string; metric_type: string; target_value: number | null; unit: string | null; status: string }>) =>
    apiPatch<{ ok: boolean } & KeyResult>(`/api/objectives/${objectiveId}/key-results/${krId}`, body),
  deleteKeyResult: (objectiveId: number, krId: number) =>
    apiDelete<{ ok: boolean }>(`/api/objectives/${objectiveId}/key-results/${krId}`),
  updateTask: (id: number, body: Partial<{ title: string; category: string | null; priority: number; due_date: string | null; status: string; objective_id: number | null; parent_task_id: number | null; blocked_by_task_id: number | null }>) =>
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
  exportDataCsv: async (): Promise<string> => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/settings/export?format=csv`, {
      headers: { Authorization: token ? `Bearer ${token}` : "" },
    });
    if (res.status === 401) throw new Error("UNAUTHORIZED");
    if (!res.ok) throw new Error(`API error ${res.status}`);
    return res.text();
  },
  deleteAccount: () => apiDelete<{ ok: boolean }>("/api/settings/account"),
  reflections: () => apiFetch<{ reflections: WeeklyReflection[] }>("/api/reflections"),
  reflection: (id: number) => apiFetch<WeeklyReflection>(`/api/reflections/${id}`),
  deleteReflection: (id: number) => apiDelete<{ ok: boolean }>(`/api/reflections/${id}`),
  regenerateReflectionInsights: (id: number) =>
    apiPost<{ ok: boolean; ai_summary: Record<string, unknown> }>(`/api/reflections/${id}/insights`, {}),
  updateReflectionPriorities: (id: number, priorities: string[]) =>
    apiPatch<WeeklyReflection>(`/api/reflections/${id}`, { top_priorities: priorities }),
  todaySuggestions: () => apiFetch<DailySuggestionsResponse>("/api/suggestions/today"),
  suggestionsHistory: (days = 14) => apiFetch<DailySuggestionsHistory>(`/api/suggestions/history?days=${days}`),
  regenerateSuggestions: () => apiPost<DailySuggestionsResponse>("/api/suggestions/regenerate", {}),
  // Autopilot intelligence
  deleteProposalDraft: (id: number) => apiDelete<{ ok: boolean }>(`/api/objectives/proposal-drafts/${id}`),
  apiReviewProposal: (id: number, action: "accept" | "reject") =>
    apiPost<{ ok: boolean }>(`/api/objectives/proposal-drafts/${id}/review`, { action }),
  executeProposalDraft: (id: number) =>
    apiPost<{ ok: boolean }>(`/api/objectives/proposal-drafts/${id}/execute`, {}),
  autopilotSnapshot: () => apiFetch<PlannerSnapshot>("/api/autopilot/snapshot"),
  autopilotDailyPlan: () => apiFetch<AutopilotDailyPlan>("/api/autopilot/daily-plan"),
  autopilotActionQueue: () => apiFetch<AutopilotActionQueue>("/api/autopilot/action-queue"),
  autopilotNextAction: () => apiFetch<AutopilotNextAction>("/api/autopilot/next-action"),
  autopilotCompleteQueueItem: (id: number) =>
    apiPatch<{ ok: boolean }>(`/api/autopilot/action-queue/${id}`, { state: "completed" }),
  autopilotPatterns: () => apiFetch<BehavioralPatterns>("/api/autopilot/patterns"),
  autopilotActiveHours: (days = 30) => apiFetch<ActiveHoursResponse>(`/api/autopilot/active-hours?days=${days}`),
  autopilotConfidence: () => apiFetch<AutopilotConfidence>("/api/autopilot/confidence"),
  autopilotSuggestions: () => apiFetch<AutopilotSuggestionsResponse>("/api/autopilot/suggestions"),
  acknowledgeNotification: (id: number) => apiPost<{ ok: boolean }>(`/api/notifications/${id}/acknowledge`, {}),
  // Docs
  listDocs: () => apiFetch<{ docs: UserDoc[] }>("/api/docs"),
  createDoc: (body: { title: string; emoji: string; content: string; sort_order?: number }) =>
    apiPost<UserDoc>("/api/docs", body),
  updateDoc: (id: number, body: Partial<{ title: string; emoji: string; content: string; sort_order: number }>) =>
    apiPut<UserDoc>(`/api/docs/${id}`, body),
  deleteDoc: (id: number) => apiDelete<{ ok: boolean }>(`/api/docs/${id}`),
  // Objective AI analysis
  analyzeObjectives: () => apiFetch<ObjectiveAnalysis>("/api/objectives/ai-analysis"),
  setObjectiveParent: (id: number, parentId: number | null) =>
    apiPost<{ ok: boolean }>(`/api/objectives/${id}/set-parent`, { parent_objective_id: parentId }),
  // Daily intelligence
  dailyContext: () => apiFetch<DailyContext>("/api/intelligence/daily-context"),
  saveDailyContext: (data: { energy: number; hours_available: number; focus_area: string; mood_note?: string }) =>
    apiPost<DailyContext>("/api/intelligence/daily-context", data),
  generateDailyPlan: () => apiPost<DailyContext>("/api/intelligence/daily-plan", {}),
  streakRisks: () => apiFetch<{ risks: StreakRisk[] }>("/api/intelligence/streak-risks"),
  eveningCheckin: () => apiFetch<EveningCheckin>("/api/intelligence/evening-checkin"),
  saveEveningCheckin: (data: unknown) =>
    apiPost<EveningCheckin>("/api/intelligence/evening-checkin", data),
  weeklyPlan: () => apiPost<unknown>("/api/intelligence/weekly-plan", {}),
  // Health daily
  healthDaily: () => apiFetch<DailyHealthData>("/api/health/daily"),
  // Protocol editors
  getSupplementProtocol: () => apiFetch<unknown>("/api/protocols/supplements"),
  updateSupplementProtocol: (data: unknown) => apiPut<{ ok: boolean }>("/api/protocols/supplements", data),
  getFitnessProtocol: () => apiFetch<unknown>("/api/protocols/fitness"),
  updateFitnessProtocol: (data: unknown) => apiPut<{ ok: boolean }>("/api/protocols/fitness", data),
  // Finance
  financeSummary: () => apiFetch<FinanceSummary>("/api/finance/summary"),
  financeTransactions: (month?: number, year?: number, type?: string) => {
    const params = new URLSearchParams();
    if (month) params.set("month", String(month));
    if (year) params.set("year", String(year));
    if (type) params.set("type", type);
    const qs = params.toString();
    return apiFetch<FinanceTransaction[]>(`/api/finance/transactions${qs ? `?${qs}` : ""}`);
  },
  financeBudgets: () => apiFetch<FinanceBudget[]>("/api/finance/budgets"),
  upsertBudget: (category: string, monthly_limit: number) =>
    apiPut<{ ok: boolean }>(`/api/finance/budgets/${category}`, { monthly_limit }),
  deleteFinanceTransaction: (id: number) => apiDelete<{ deleted: boolean }>(`/api/finance/transactions/${id}`),
  patternInsights: () => apiFetch<PatternInsightsResponse>("/api/autopilot/pattern-insights"),
  refreshPatternInsights: () => apiPost<{ ok: boolean; insights_generated: number; consistency_score: unknown }>("/api/autopilot/pattern-insights/refresh", {}),
  correlations: () => apiFetch<{ correlations: CorrelationInsight[]; analysis_days: number }>("/api/intelligence/correlations"),
  refreshCorrelations: () => apiPost<{ ok: boolean; correlations: CorrelationInsight[]; count: number }>("/api/intelligence/correlations/refresh", {}),
  // Health Sync
  healthMetrics: (days = 30) => apiFetch<{ metrics: HealthMetric[] }>(`/api/health/metrics?days=${days}`),
  syncHealth: (data: Record<string, unknown>) => apiPost<{ ok: boolean; stored: string[] }>("/api/health/sync", data),
  healthShortcutSetup: () => apiFetch<HealthShortcutSetup>("/api/health/shortcut-setup"),
  importAppleHealth: (file: File | Blob) =>
    apiUpload<{ ok: boolean; days_imported: number; total_days_in_file: number; kr_updates: string[] }>(
      "/api/health/import/apple-health", file, "application/zip",
    ),
  importHealthCsv: (file: File | Blob) =>
    apiUpload<{ ok: boolean; days_imported: number; total_days_in_file: number; kr_updates: string[] }>(
      "/api/health/import/csv", file, "text/csv",
    ),
  // Push Notifications
  vapidKey: () => apiFetch<{ publicKey: string }>("/api/push/vapid-key"),
  pushSubscribe: (sub: { endpoint: string; keys: Record<string, string>; userAgent?: string }) =>
    apiPost<{ ok: boolean }>("/api/push/subscribe", sub),
  pushTest: () => apiPost<{ ok: boolean; sent_to: number }>("/api/push/test", {}),
  // Onboarding
  onboardingStatus: () => apiFetch<{ completed: boolean }>("/api/onboarding/status"),
  completeOnboarding: (body: {
    name?: string;
    selected_areas?: string[];
    first_goal?: string | null;
    wakeup_time?: string;
    morning_routines?: string[];
  }) => apiPost<{ ok: boolean; created: Record<string, unknown> }>("/api/onboarding", body),
  // Goal Onboarding (conversational flow)
  goalClarify: (goal: string) =>
    apiPost<GoalClarifyResponse>("/api/goals/clarify", { goal }),
  goalGenerateOptions: (body: { goal: string; category?: string; answers?: Record<string, string> }) =>
    apiPost<GoalOptionsResponse>("/api/goals/generate-options", body),
  goalGenerate: (body: { goal: string; category?: string; selected_krs?: unknown[]; answers?: Record<string, string>; feedback?: string }) =>
    apiPost<{ draft_id: number; plan: GoalPlan }>("/api/goals/generate", body),
  goalExecute: (draftId: number) =>
    apiPost<{ ok: boolean; objective_id: number; key_result_ids: number[]; task_ids: number[] }>(
      `/api/objectives/proposal-drafts/${draftId}/execute`, {}
    ),
  // Conversational Goal Onboarding (Telegram-style)
  goalOnboardingStart: (goalText: string) =>
    apiPost<{ onboarding_id: number; message: string; status: string; step: number }>(
      "/api/goal-onboarding/start", { goal_text: goalText }
    ),
  goalOnboardingActive: () =>
    apiFetch<{ active: boolean; onboarding_id?: number; status?: string; step?: number; goal?: string; draft_payload?: GoalPlan }>(
      "/api/goal-onboarding/active"
    ),
  goalOnboardingAnswer: (text: string) =>
    apiPost<{ message: string; status: string; step: number; buttons?: unknown[][]; draft_payload?: GoalPlan }>(
      "/api/goal-onboarding/answer", { text }
    ),
  goalOnboardingConfirm: () =>
    apiPost<{ message: string; status: string }>("/api/goal-onboarding/confirm", {}),
  goalOnboardingAdjust: () =>
    apiPost<{ message: string; status: string }>("/api/goal-onboarding/adjust", {}),
  goalOnboardingCancel: () =>
    apiPost<{ ok: boolean; cancelled: boolean }>("/api/goal-onboarding/cancel", {}),
  // Tasks with category filter
  tasksByCategory: (category: string) =>
    apiFetch<{ tasks: Task[] }>(`/api/tasks?category=${encodeURIComponent(category)}`),
};
