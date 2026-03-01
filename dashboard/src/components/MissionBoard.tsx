import CircularProgress from "./CircularProgress";
import { cn } from "@/lib/utils";
import type { Routine, Task } from "@/lib/api";

interface Props {
  routines: Routine[];
  tasks: Task[];
}

export default function MissionBoard({ routines, tasks }: Props) {
  const top3Tasks = tasks.slice(0, 3);
  const totalMissions = routines.length + top3Tasks.length;
  const doneMissions = routines.filter((r) => r.completed_today).length;
  const pct = totalMissions > 0 ? Math.round((doneMissions / totalMissions) * 100) : 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center gap-4 mb-4">
        <CircularProgress
          value={pct}
          size={52}
          strokeWidth={5}
          color="#22c55e"
          label={`${doneMissions}/${totalMissions}`}
        />
        <div>
          <h2 className="text-white font-semibold">Heutige Missionen</h2>
          <p className="text-zinc-500 text-xs">
            {doneMissions} von {totalMissions} erledigt · {pct}%
          </p>
        </div>
      </div>

      {/* Daily Quests — routines */}
      {routines.length > 0 && (
        <div className="mb-4">
          <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-2">
            Daily Quests
          </div>
          <div className="space-y-1.5">
            {routines.map((r) => (
              <div
                key={r.id}
                className={cn(
                  "flex items-center gap-3 py-2 px-3 rounded-lg",
                  r.completed_today
                    ? "bg-green-950/40 border border-green-900/40"
                    : "bg-zinc-800/50 border border-zinc-700/40"
                )}
              >
                <span className="text-sm shrink-0">
                  {r.completed_today ? "✅" : "☐"}
                </span>
                <span
                  className={cn(
                    "text-sm flex-1 min-w-0 truncate",
                    r.completed_today ? "text-zinc-500 line-through" : "text-white"
                  )}
                >
                  {r.title}
                </span>
                {r.frequency_human && (
                  <span className="text-xs text-zinc-600 shrink-0">{r.frequency_human}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Missions — top tasks */}
      {top3Tasks.length > 0 && (
        <div>
          <div className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-2">
            Hauptmissionen
          </div>
          <div className="space-y-1.5">
            {top3Tasks.map((t) => (
              <div
                key={t.id}
                className="flex items-center gap-3 py-2 px-3 rounded-lg bg-zinc-800/50 border border-zinc-700/40"
              >
                <div
                  className={cn(
                    "w-2 h-2 rounded-full shrink-0",
                    t.priority === 1 ? "bg-red-400" :
                    t.priority === 2 ? "bg-orange-400" :
                    t.priority === 3 ? "bg-yellow-400" : "bg-zinc-500"
                  )}
                />
                <span className="text-sm text-white flex-1 min-w-0 truncate">{t.title}</span>
                {t.category && t.category !== "general" && (
                  <span className="text-xs text-zinc-500 shrink-0">{t.category}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {totalMissions === 0 && (
        <p className="text-zinc-500 text-sm text-center py-4">
          Noch keine Missionen — erstelle Routinen & Tasks!
        </p>
      )}
    </div>
  );
}
