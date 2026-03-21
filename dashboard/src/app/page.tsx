"use client";

import React, { useState } from "react";
import Link from "next/link";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import XPBar from "@/components/XPBar";
import {
  useDashboard,
  useTasks,
  useRoutines,
  useObjectives,
  useWeeklySummary,
  useGamificationStats,
  useCalendar,
  useDailyContext,
} from "@/hooks/useApi";
import { api } from "@/lib/api";
import { useSWRConfig } from "swr";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/lib/api";

// ─── Constants ────────────────────────────────────────────────────────────────

const EVENT_TYPE_ICON: Record<string, string> = {
  meeting: "🤝",
  training: "💪",
  deadline: "⚠️",
  travel: "✈️",
  reminder: "🔔",
  errand: "📍",
  work_block: "💼",
  routine: "🔄",
  default: "📅",
};

const EVENT_TYPE_COLOR: Record<string, string> = {
  meeting: "border-blue-500/50 bg-blue-950/20",
  training: "border-green-500/50 bg-green-950/20",
  deadline: "border-red-500/50 bg-red-950/20",
  travel: "border-purple-500/50 bg-purple-950/20",
  reminder: "border-yellow-500/50 bg-yellow-950/20",
  errand: "border-orange-500/50 bg-orange-950/20",
  work_block: "border-indigo-500/50 bg-indigo-950/20",
  default: "border-zinc-700/50 bg-zinc-800/30",
};

const EVENT_TYPE_TEXT: Record<string, string> = {
  meeting: "text-blue-300",
  training: "text-green-300",
  deadline: "text-red-300",
  travel: "text-purple-300",
  reminder: "text-yellow-300",
  errand: "text-orange-300",
  work_block: "text-indigo-300",
  default: "text-zinc-300",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
}

function isFuture(iso: string): boolean {
  return new Date(iso) > new Date();
}

// ─── Today's Timeline ─────────────────────────────────────────────────────────

function TodayTimeline({ events }: { events: CalendarEvent[] }) {
  const todayEvents = events
    .filter((e) => isToday(e.start_time) && e.event_type !== "routine")
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  if (todayEvents.length === 0) {
    return (
      <div className="text-zinc-500 text-sm text-center py-4">
        Keine Termine heute — freier Tag 🙌
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {todayEvents.map((event) => {
        const isPast = !isFuture(event.start_time);
        const colors = EVENT_TYPE_COLOR[event.event_type] ?? EVENT_TYPE_COLOR.default;
        const textColor = EVENT_TYPE_TEXT[event.event_type] ?? EVENT_TYPE_TEXT.default;
        const icon = EVENT_TYPE_ICON[event.event_type] ?? EVENT_TYPE_ICON.default;

        return (
          <div
            key={event.id}
            className={cn(
              "flex items-start gap-3 rounded-xl border px-3.5 py-2.5 transition-opacity",
              colors,
              isPast && "opacity-50"
            )}
          >
            {/* Time */}
            <div className="shrink-0 text-right min-w-[38px]">
              <div className={cn("text-xs font-semibold tabular-nums", isPast ? "text-zinc-500" : textColor)}>
                {event.all_day ? "ganzt." : formatTime(event.start_time)}
              </div>
              {event.end_time && !event.all_day && (
                <div className="text-zinc-600 text-[10px] tabular-nums">
                  {formatTime(event.end_time)}
                </div>
              )}
            </div>

            {/* Divider */}
            <div className={cn("w-px self-stretch shrink-0", isPast ? "bg-zinc-700" : "bg-zinc-600")} />

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{icon}</span>
                <span className={cn("text-sm font-medium truncate", isPast ? "text-zinc-500 line-through" : "text-white")}>
                  {event.title}
                </span>
              </div>
              {event.description && (
                <p className="text-zinc-500 text-xs mt-0.5 line-clamp-1">{event.description}</p>
              )}
            </div>

            {/* Next-up indicator */}
            {!isPast && todayEvents.filter((e) => !isFuture(e.start_time)).length ===
              todayEvents.indexOf(event) && (
              <div className="shrink-0">
                <span className="text-[10px] font-bold bg-blue-500 text-white px-1.5 py-0.5 rounded-full">
                  NEXT
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Top Tasks ────────────────────────────────────────────────────────────────

const PRIORITY_COLOR: Record<number, string> = {
  1: "text-red-400",
  2: "text-orange-400",
  3: "text-yellow-400",
  4: "text-zinc-400",
  5: "text-zinc-500",
};

function TopTasksSection() {
  const { data } = useTasks();
  const { mutate } = useSWRConfig();
  const [completing, setCompleting] = useState<number | null>(null);

  const tasks = (data?.tasks ?? [])
    .filter((t) => t.category !== "shopping")
    .slice(0, 5);

  if (tasks.length === 0) return (
    <div className="text-zinc-500 text-sm text-center py-3">
      Alle Tasks erledigt 🎉
    </div>
  );

  async function complete(id: number) {
    setCompleting(id);
    try {
      await api.completeTask(id);
      await mutate("tasks-todo");
    } catch { /* ignore */ }
    finally { setCompleting(null); }
  }

  return (
    <div className="space-y-1.5">
      {tasks.map((task) => (
        <div
          key={task.id}
          className="flex items-center gap-3 group rounded-xl px-3.5 py-2.5 bg-zinc-800/40 border border-zinc-700/40 hover:border-zinc-600/60 transition-colors"
        >
          <button
            onClick={() => complete(task.id)}
            disabled={completing === task.id}
            className="shrink-0 w-5 h-5 rounded-full border-2 border-zinc-600 group-hover:border-zinc-400 flex items-center justify-center transition-colors disabled:opacity-50"
          >
            {completing === task.id && (
              <div className="w-2.5 h-2.5 rounded-full border border-zinc-400 border-t-transparent animate-spin" />
            )}
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-white text-sm truncate">{task.title}</div>
            {task.due_date && (
              <div className="text-zinc-500 text-xs">
                fällig {new Date(task.due_date + "T00:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "short" })}
              </div>
            )}
          </div>
          <span className={cn("text-xs font-bold shrink-0", PRIORITY_COLOR[task.priority] ?? PRIORITY_COLOR[5])}>
            P{task.priority}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Routinen Today ───────────────────────────────────────────────────────────

function RoutinesToday() {
  const { data } = useRoutines();
  const { mutate } = useSWRConfig();
  const [completing, setCompleting] = useState<number | null>(null);

  const routines = data?.routines ?? [];
  if (routines.length === 0) return null;

  const done = routines.filter((r) => r.completed_today).length;

  async function complete(id: number) {
    setCompleting(id);
    try {
      await api.completeRoutine(id);
      await mutate("routines");
    } catch { /* ignore */ }
    finally { setCompleting(null); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2">
          <span>🌅</span> Routinen
        </h2>
        <div className="flex items-center gap-2">
          <div className="text-xs text-zinc-500">{done}/{routines.length}</div>
          {done === routines.length && (
            <span className="text-xs text-green-400 font-medium">✓ Alles erledigt</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden mb-3">
        <div
          className="h-full bg-green-500 rounded-full transition-all"
          style={{ width: `${routines.length > 0 ? (done / routines.length) * 100 : 0}%` }}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {routines.map((r) => (
          <button
            key={r.id}
            onClick={() => !r.completed_today && complete(r.id)}
            disabled={r.completed_today || completing === r.id}
            className={cn(
              "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-all",
              r.completed_today
                ? "bg-green-950/40 border-green-800/40 text-green-500"
                : "bg-zinc-800/60 border-zinc-700/60 text-zinc-300 hover:border-zinc-500 active:scale-95"
            )}
          >
            <span>{r.completed_today ? "✓" : completing === r.id ? "…" : "○"}</span>
            <span className={r.completed_today ? "line-through opacity-60" : ""}>{r.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Key Stats Row ────────────────────────────────────────────────────────────

function KeyStats() {
  const { data: dash } = useDashboard();
  const { data: weekly } = useWeeklySummary();
  const { data: gamification } = useGamificationStats();

  const stats = dash?.stats;
  const streakDays = stats?.streak_days ?? 0;
  const routinesDone = stats?.routines_done_today ?? 0;
  const routinesTotal = stats?.routines_total ?? 0;
  const tasksDone = weekly?.tasks_done_this_week ?? 0;
  const level = stats?.level ?? 1;

  return (
    <div className="grid grid-cols-4 gap-2">
      {/* Streak */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex flex-col items-center text-center gap-1">
        <span className="text-xl">🔥</span>
        <div className={cn("text-lg font-bold leading-none", streakDays > 0 ? "text-orange-400" : "text-zinc-600")}>
          {streakDays}
        </div>
        <div className="text-zinc-600 text-[10px] leading-tight">Tage</div>
      </div>

      {/* Routinen */}
      <Link href="/routines" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex flex-col items-center text-center gap-1 hover:border-zinc-700 transition-colors">
        <span className="text-xl">🌅</span>
        <div className={cn("text-lg font-bold leading-none", routinesDone === routinesTotal && routinesTotal > 0 ? "text-green-400" : "text-zinc-300")}>
          {routinesDone}/{routinesTotal}
        </div>
        <div className="text-zinc-600 text-[10px] leading-tight">Routinen</div>
      </Link>

      {/* Tasks diese Woche */}
      <Link href="/tasks" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex flex-col items-center text-center gap-1 hover:border-zinc-700 transition-colors">
        <span className="text-xl">✅</span>
        <div className="text-lg font-bold leading-none text-blue-400">{tasksDone}</div>
        <div className="text-zinc-600 text-[10px] leading-tight">Tasks/Woche</div>
      </Link>

      {/* Level */}
      <Link href="/achievements" className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex flex-col items-center text-center gap-1 hover:border-zinc-700 transition-colors">
        <span className="text-xl">⭐</span>
        <div className="text-lg font-bold leading-none text-yellow-400">Lv.{level}</div>
        <div className="text-zinc-600 text-[10px] leading-tight">Level</div>
      </Link>
    </div>
  );
}

// ─── Daily Plan Strip ─────────────────────────────────────────────────────────

const FOCUS_AREAS = [
  { value: "health", label: "Gesundheit" },
  { value: "fitness", label: "Fitness" },
  { value: "business", label: "Business" },
  { value: "personal", label: "Persönlich" },
  { value: "finance", label: "Finanzen" },
  { value: "learning", label: "Lernen" },
];

function DailyPlanStrip() {
  const { mutate } = useSWRConfig();
  const { data: context, isLoading } = useDailyContext();
  const [energy, setEnergy] = useState<number | null>(null);
  const [hours, setHours] = useState<number | null>(null);
  const [focusArea, setFocusArea] = useState("");
  const [generating, setGenerating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const plan = context?.daily_plan;
  const hasPlan = !!plan && plan.top_tasks.length > 0;

  async function handleGenerate() {
    if (energy === null || hours === null || !focusArea) return;
    setGenerating(true);
    try {
      await api.saveDailyContext({ energy, hours_available: hours, focus_area: focusArea });
      await api.generateDailyPlan();
      await mutate("daily-context");
      setShowForm(false);
    } catch { /* ignore */ }
    finally { setGenerating(false); }
  }

  async function handleRegenerate() {
    setGenerating(true);
    try {
      await api.generateDailyPlan();
      await mutate("daily-context");
    } catch { /* ignore */ }
    finally { setGenerating(false); }
  }

  if (isLoading) return null;

  // Plan already exists — show motivational kickoff + regen button
  if (hasPlan) {
    return (
      <div className="bg-gradient-to-r from-blue-950/40 to-indigo-950/40 border border-blue-800/30 rounded-xl p-4 mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-blue-400 text-xs font-semibold uppercase tracking-wide mb-1">🎯 KI-Fokus heute</div>
            {plan.motivational_kickoff && (
              <p className="text-zinc-200 text-sm leading-relaxed">{plan.motivational_kickoff}</p>
            )}
            {plan.focus_block && (
              <div className="text-zinc-500 text-xs mt-1.5">
                Focus Block: {plan.focus_block.suggested_start} · {plan.focus_block.duration_minutes} min
              </div>
            )}
          </div>
          <button
            onClick={handleRegenerate}
            disabled={generating}
            className="shrink-0 text-blue-500 hover:text-blue-300 text-xs transition-colors disabled:opacity-50 mt-0.5"
          >
            {generating ? "…" : "↺"}
          </button>
        </div>
      </div>
    );
  }

  // No plan — collapsed or expanded form
  if (!showForm) {
    return (
      <button
        onClick={() => setShowForm(true)}
        className="w-full flex items-center justify-between bg-zinc-900/60 border border-zinc-800 border-dashed hover:border-zinc-600 rounded-xl px-4 py-3 mb-5 transition-colors group"
      >
        <span className="text-zinc-500 text-sm group-hover:text-zinc-300 transition-colors">
          ✨ KI-Tagesplan generieren…
        </span>
        <span className="text-zinc-600 text-xs">Starten →</span>
      </button>
    );
  }

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 mb-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2">
          🌅 Wie startest du heute?
        </h2>
        <button onClick={() => setShowForm(false)} className="text-zinc-600 hover:text-zinc-400 text-xs">✕</button>
      </div>

      {/* Energy */}
      <div className="mb-3">
        <div className="text-zinc-500 text-xs mb-2">Energie</div>
        <div className="flex gap-2">
          {[{ val: 3, label: "Niedrig", icon: "😴" }, { val: 6, label: "Mittel", icon: "⚙️" }, { val: 9, label: "Hoch", icon: "⚡" }].map((o) => (
            <button key={o.val} onClick={() => setEnergy(o.val)}
              className={cn("flex-1 flex flex-col items-center gap-0.5 py-2 rounded-lg border text-xs transition-colors",
                energy === o.val ? "bg-blue-600/20 border-blue-500 text-blue-300" : "border-zinc-700 text-zinc-400 hover:border-zinc-600")}>
              <span className="text-base">{o.icon}</span>{o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Hours */}
      <div className="mb-3">
        <div className="text-zinc-500 text-xs mb-2">Verfügbare Zeit</div>
        <div className="flex gap-2">
          {[1, 2, 4, 6].map((h) => (
            <button key={h} onClick={() => setHours(h)}
              className={cn("flex-1 py-2 rounded-lg border text-xs transition-colors",
                hours === h ? "bg-blue-600/20 border-blue-500 text-blue-300" : "border-zinc-700 text-zinc-400 hover:border-zinc-600")}>
              {h === 6 ? "6h+" : `${h}h`}
            </button>
          ))}
        </div>
      </div>

      {/* Focus */}
      <div className="mb-4">
        <div className="text-zinc-500 text-xs mb-2">Fokus</div>
        <select value={focusArea} onChange={(e) => setFocusArea(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 text-zinc-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500">
          <option value="">Bereich wählen…</option>
          {FOCUS_AREAS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
        </select>
      </div>

      <button onClick={handleGenerate} disabled={generating || energy === null || hours === null || !focusArea}
        className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm font-medium py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2">
        {generating ? <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />Generiert…</> : "✨ Plan erstellen"}
      </button>
    </div>
  );
}

// ─── Quick Links ──────────────────────────────────────────────────────────────

function QuickLinks() {
  const { data } = useDashboard();
  const shoppingCount = data?.stats?.shopping_items ?? 0;

  const links = [
    { href: "/calendar", icon: "📅", label: "Kalender" },
    { href: "/tasks", icon: "📋", label: "Tasks" },
    { href: "/objectives", icon: "🎯", label: "Ziele" },
    { href: "/fitness", icon: "💪", label: "Fitness" },
    { href: "/shopping", icon: "🛒", label: "Einkauf", badge: shoppingCount > 0 ? shoppingCount : undefined },
    { href: "/brain-dumps", icon: "📝", label: "Brain Dump" },
    { href: "/finance", icon: "💶", label: "Finanzen" },
    { href: "/relationships", icon: "👥", label: "Kontakte" },
  ];

  return (
    <div className="grid grid-cols-4 gap-2">
      {links.map((item) => (
        <Link key={item.href} href={item.href}
          className="relative flex flex-col items-center gap-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl py-3 px-2 transition-colors">
          <span className="text-xl">{item.icon}</span>
          <span className="text-zinc-400 text-[11px] text-center leading-tight">{item.label}</span>
          {item.badge !== undefined && (
            <span className="absolute top-1.5 right-1.5 bg-yellow-500 text-black text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
              {item.badge}
            </span>
          )}
        </Link>
      ))}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: dash, error: dashError, isLoading: dashLoading } = useDashboard();
  const { data: calData } = useCalendar(2, 0);
  const { data: gamification } = useGamificationStats();

  if (dashLoading) return <LoadingSpinner />;
  if (dashError) {
    if (dashError.message === "UNAUTHORIZED") {
      return <ErrorState message="Ungültiger API Token. Bitte in den Einstellungen aktualisieren." />;
    }
    return <ErrorState message={dashError.message} />;
  }
  if (!dash) return <LoadingSpinner />;

  const stats = dash?.stats;
  const user = dash?.user;
  const events: CalendarEvent[] = calData?.events ?? [];

  const now = new Date();
  const greeting = now.getHours() < 12 ? "Guten Morgen" : now.getHours() < 18 ? "Guten Tag" : "Guten Abend";
  const dayStr = now.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });

  const streakDays = stats?.streak_days ?? 0;
  const streakFlame = streakDays >= 30 ? "🔥🔥🔥" : streakDays >= 14 ? "🔥🔥" : "🔥";

  // Next upcoming event today
  const nextEvent = events
    .filter((e) => isToday(e.start_time) && isFuture(e.start_time) && e.event_type !== "routine")
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())[0];

  return (
    <div className="space-y-5">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">
            {greeting}{user?.first_name ? `, ${user.first_name}` : ""} 👋
          </h1>
          <p className="text-zinc-500 text-sm mt-0.5">{dayStr}</p>
          {nextEvent && (
            <div className="flex items-center gap-1.5 mt-1.5">
              <span className="text-xs text-zinc-500">Nächstes:</span>
              <span className="text-xs font-medium text-zinc-300">
                {formatTime(nextEvent.start_time)} · {nextEvent.title}
              </span>
            </div>
          )}
        </div>
        {streakDays > 0 && (
          <div className="bg-orange-950/60 border border-orange-800/40 rounded-xl px-3 py-2 text-center shrink-0">
            <div className="text-lg leading-none">{streakFlame}</div>
            <div className="text-orange-400 font-bold text-base leading-none mt-0.5">{streakDays}</div>
            <div className="text-orange-700 text-[10px]">Tage</div>
          </div>
        )}
      </div>

      {/* XP Bar */}
      {stats?.total_xp !== undefined && (
        <XPBar
          level={stats.level}
          levelTitle={stats.level_title}
          totalXp={stats.total_xp}
          xpProgress={stats.xp_progress}
          xpToNext={stats.xp_to_next}
        />
      )}

      {/* ── KI-Tagesplan ────────────────────────────────────────────────────── */}
      <DailyPlanStrip />

      {/* ── Heute im Überblick (Kalender + Tasks) ───────────────────────────── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        {/* Tab header */}
        <TodayTabs events={events} />
      </div>

      {/* ── Routinen ────────────────────────────────────────────────────────── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <RoutinesToday />
      </div>

      {/* ── Key Stats ───────────────────────────────────────────────────────── */}
      <KeyStats />

      {/* ── Quick Links ─────────────────────────────────────────────────────── */}
      <div>
        <h2 className="text-zinc-500 text-xs font-semibold uppercase tracking-wider mb-2">Schnellzugriff</h2>
        <QuickLinks />
      </div>

      {/* ── Recent Achievements ─────────────────────────────────────────────── */}
      {gamification && gamification.recent_achievements.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h2 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
            <span>🏆</span> Letzte Erfolge
            <Link href="/achievements" className="text-xs text-blue-400 hover:text-blue-300 ml-auto transition-colors">
              Alle →
            </Link>
          </h2>
          <div className="space-y-2">
            {gamification.recent_achievements.slice(0, 3).map((a) => (
              <div key={a.id} className="flex items-center gap-3">
                <span className="text-lg w-7 text-center shrink-0">{a.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-medium truncate">{a.title}</div>
                </div>
                <span className="text-yellow-500 text-xs font-medium shrink-0">+{a.xp_reward} XP</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Today Tabs (Termine / Tasks) ────────────────────────────────────────────

function TodayTabs({ events }: { events: CalendarEvent[] }) {
  const [tab, setTab] = useState<"termine" | "tasks">("termine");

  const todayEventCount = events.filter(
    (e) => isToday(e.start_time) && e.event_type !== "routine"
  ).length;

  return (
    <>
      {/* Tab bar */}
      <div className="flex border-b border-zinc-800">
        <button
          onClick={() => setTab("termine")}
          className={cn(
            "flex-1 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2",
            tab === "termine"
              ? "text-white border-b-2 border-blue-500 -mb-px"
              : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          📅 Heute
          {todayEventCount > 0 && (
            <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-bold",
              tab === "termine" ? "bg-blue-500/20 text-blue-400" : "bg-zinc-800 text-zinc-500")}>
              {todayEventCount}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("tasks")}
          className={cn(
            "flex-1 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2",
            tab === "tasks"
              ? "text-white border-b-2 border-blue-500 -mb-px"
              : "text-zinc-500 hover:text-zinc-300"
          )}
        >
          ✅ Tasks
        </button>
      </div>

      {/* Tab content */}
      <div className="p-4">
        {tab === "termine" ? (
          <TodayTimeline events={events} />
        ) : (
          <TopTasksSection />
        )}
      </div>
    </>
  );
}
