"use client";

import { useState } from "react";
import useSWR from "swr";
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import Header from "@/components/Header";
import LoadingSpinner, { EmptyState, ErrorState } from "@/components/LoadingSpinner";
import { useAchievements } from "@/hooks/useApi";
import { mutate } from "swr";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Achievement } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  onboarding: "Onboarding",
  tasks: "Aufgaben & Aktivität",
  goals: "Ziele & OKRs",
  streaks: "Streaks",
  reflection: "Reflexion",
  fun: "Besonderes",
};

const CATEGORY_ORDER = ["onboarding", "streaks", "tasks", "goals", "reflection", "fun"];

function ProgressBar({ current, target }: { current: number; target: number }) {
  const pct = Math.min(100, Math.round((current / target) * 100));
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-zinc-500 mb-1">
        <span>{current.toLocaleString("de-DE")} / {target.toLocaleString("de-DE")}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function AchievementCard({ achievement }: { achievement: Achievement }) {
  const { unlocked, emoji, title, description, xp_reward, unlocked_at, progress } = achievement;
  const hasProgress = progress.current !== null && progress.target !== null && !unlocked;

  return (
    <div
      className={cn(
        "relative rounded-xl border p-4 transition-all",
        unlocked
          ? "bg-zinc-900 border-yellow-500/40 shadow-sm shadow-yellow-500/10"
          : "bg-zinc-900/60 border-zinc-800 opacity-60"
      )}
    >
      {/* Unlocked glow badge */}
      {unlocked && (
        <div className="absolute top-3 right-3">
          <span className="text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-1.5 py-0.5 rounded-full font-medium">
            ✓ Unlocked
          </span>
        </div>
      )}

      <div className="flex items-start gap-3">
        <div
          className={cn(
            "text-2xl w-10 h-10 flex items-center justify-center rounded-xl shrink-0",
            unlocked ? "bg-yellow-500/15" : "bg-zinc-800"
          )}
        >
          {emoji}
        </div>

        <div className="flex-1 min-w-0 pr-16">
          <div className={cn("font-semibold text-sm", unlocked ? "text-white" : "text-zinc-400")}>
            {title}
          </div>
          <div className="text-zinc-500 text-xs mt-0.5 leading-relaxed">{description}</div>

          {unlocked && unlocked_at && (
            <div className="text-zinc-600 text-xs mt-1">
              {new Date(unlocked_at).toLocaleDateString("de-DE", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
              })}
            </div>
          )}

          {hasProgress && (
            <ProgressBar current={progress.current!} target={progress.target!} />
          )}
        </div>
      </div>

      <div className={cn(
        "mt-3 pt-2 border-t flex items-center justify-between",
        unlocked ? "border-yellow-500/20" : "border-zinc-800"
      )}>
        <span className={cn(
          "text-xs font-medium",
          unlocked ? "text-yellow-400" : "text-zinc-600"
        )}>
          +{xp_reward} XP
        </span>
        {!unlocked && hasProgress && (
          <span className="text-xs text-zinc-600">
            {Math.min(100, Math.round((progress.current! / progress.target!) * 100))}% erreicht
          </span>
        )}
        {!unlocked && !hasProgress && (
          <span className="text-xs text-zinc-700">Gesperrt</span>
        )}
      </div>
    </div>
  );
}

export default function AchievementsPage() {
  const { data, error, isLoading } = useAchievements();
  const [checking, setChecking] = useState(false);
  const [newlyUnlocked, setNewlyUnlocked] = useState<{ emoji: string; title: string }[]>([]);

  const handleCheck = async () => {
    setChecking(true);
    setNewlyUnlocked([]);
    try {
      const res = await api.checkAchievements();
      if (res.count > 0) {
        setNewlyUnlocked(res.newly_unlocked);
        await mutate(() => true, undefined, { revalidate: true });
      }
    } catch {
      // fail silently
    } finally {
      setChecking(false);
    }
  };

  const { data: xpHistoryData } = useSWR("xp-history-30", () => api.xpHistory(30));

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  const achievements = data?.achievements ?? [];
  const unlockedCount = achievements.filter((a) => a.unlocked).length;
  const totalXP = achievements.filter((a) => a.unlocked).reduce((sum, a) => sum + a.xp_reward, 0);

  // Group by category
  const byCategory: Record<string, Achievement[]> = {};
  for (const a of achievements) {
    if (!byCategory[a.category]) byCategory[a.category] = [];
    byCategory[a.category].push(a);
  }

  const categories = CATEGORY_ORDER.filter((c) => byCategory[c]?.length > 0);

  return (
    <div>
      <Header
        title="🏆 Erfolge"
        subtitle={`${unlockedCount} / ${achievements.length} freigeschaltet · ${totalXP.toLocaleString("de-DE")} XP gesammelt`}
        action={
          <button
            onClick={handleCheck}
            disabled={checking}
            className="px-3 py-1.5 rounded-lg text-sm bg-zinc-800 hover:bg-zinc-700 text-zinc-300 disabled:opacity-50 transition-colors"
          >
            {checking ? "Prüfe..." : "🔍 Prüfen"}
          </button>
        }
      />
      {newlyUnlocked.length > 0 && (
        <div className="bg-yellow-950/40 border border-yellow-500/40 rounded-xl px-4 py-3 mb-4 flex items-center gap-3">
          <span className="text-yellow-400 text-sm font-medium">
            {newlyUnlocked.length} neue Erfolge freigeschaltet!
          </span>
          <span className="text-yellow-500/70 text-sm">
            {newlyUnlocked.map((a) => `${a.emoji} ${a.title}`).join(" · ")}
          </span>
        </div>
      )}

      {/* Summary bar */}
      {achievements.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-zinc-400 text-sm">Gesamtfortschritt</span>
            <span className="text-white font-semibold text-sm">
              {unlockedCount} / {achievements.length}
            </span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-yellow-500 to-yellow-400 rounded-full transition-all duration-700"
              style={{ width: `${(unlockedCount / achievements.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* XP history chart (F2) */}
      {xpHistoryData && xpHistoryData.history.some((d) => d.xp > 0) && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-white font-semibold text-sm">XP Verlauf (30 Tage)</h3>
            <span className="text-zinc-500 text-xs">{xpHistoryData.total_xp.toLocaleString("de-DE")} XP gesamt</span>
          </div>
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={xpHistoryData.history.slice(-30)} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" hide />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: "8px", fontSize: "11px", color: "#f4f4f5" }}
                formatter={(v) => [`${v} XP`, "XP"]}
                labelFormatter={(l) => new Date(l).toLocaleDateString("de-DE", { day: "2-digit", month: "short" })}
              />
              <Bar dataKey="xp" fill="#eab308" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Category sections */}
      {categories.map((category) => {
        const items = byCategory[category] ?? [];
        const catUnlocked = items.filter((a) => a.unlocked).length;
        return (
          <div key={category} className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold">
                {CATEGORY_LABELS[category] ?? category}
              </h3>
              <span className="text-zinc-500 text-sm">
                {catUnlocked} / {items.length}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((achievement) => (
                <AchievementCard key={achievement.id} achievement={achievement} />
              ))}
            </div>
          </div>
        );
      })}

      {achievements.length === 0 && (
        <EmptyState emoji="🏆" message="Noch keine Achievements geladen. Leg los!" />
      )}
    </div>
  );
}
