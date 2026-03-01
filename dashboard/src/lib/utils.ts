import { format, formatDistanceToNow, parseISO } from "date-fns";
import { de } from "date-fns/locale";
import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(iso: string): string {
  return format(parseISO(iso), "dd. MMM yyyy", { locale: de });
}

export function formatDateTime(iso: string): string {
  return format(parseISO(iso), "dd. MMM, HH:mm", { locale: de });
}

export function formatTimeAgo(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true, locale: de });
}

export function formatTime(iso: string): string {
  return format(parseISO(iso), "HH:mm");
}

export const CATEGORY_EMOJI: Record<string, string> = {
  health: "🏥",
  fitness: "💪",
  business: "💼",
  personal: "🧠",
  finance: "💰",
  learning: "📚",
  relationships: "❤️",
  default: "🎯",
};

export const LOG_TYPE_EMOJI: Record<string, string> = {
  workout: "💪",
  water: "💧",
  food: "🍽️",
  mood: "😊",
  progress: "📈",
  note: "📝",
  general: "💬",
  default: "📌",
};

export const EVENT_TYPE_EMOJI: Record<string, string> = {
  training: "🏋️",
  meeting: "📅",
  routine: "🔄",
  deadline: "⏰",
  reminder: "🔔",
  default: "📌",
};

export const STATUS_COLOR: Record<string, string> = {
  active: "text-green-400",
  completed: "text-blue-400",
  paused: "text-yellow-400",
  abandoned: "text-red-400",
  todo: "text-zinc-400",
  in_progress: "text-blue-400",
  done: "text-green-400",
  cancelled: "text-red-400",
};

export const PRIORITY_LABEL: Record<number, string> = {
  1: "Highest",
  2: "High",
  3: "Medium",
  4: "Low",
  5: "Lowest",
};

export const PRIORITY_COLOR: Record<number, string> = {
  1: "text-red-400",
  2: "text-orange-400",
  3: "text-yellow-400",
  4: "text-blue-400",
  5: "text-zinc-500",
};

export function getMoodEmoji(score: number): string {
  if (score >= 9) return "🤩";
  if (score >= 7) return "😊";
  if (score >= 5) return "😐";
  if (score >= 3) return "😔";
  return "😢";
}

export function truncate(str: string, len = 80): string {
  if (str.length <= len) return str;
  return str.slice(0, len) + "…";
}
