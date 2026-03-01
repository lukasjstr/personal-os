"use client";

import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import CircularProgress from "@/components/CircularProgress";
import { useRoutines } from "@/hooks/useApi";
import { cn } from "@/lib/utils";

export default function RoutinesPage() {
  const { data, error, isLoading } = useRoutines();

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const routines = data?.routines ?? [];
  const active = routines.filter((r) => r.status === "active");
  const paused = routines.filter((r) => r.status === "paused");
  const doneToday = active.filter((r) => r.completed_today).length;
  const pct = active.length > 0 ? Math.round((doneToday / active.length) * 100) : 0;

  return (
    <div>
      <Header
        title="🔄 Routinen"
        subtitle={`${doneToday}/${active.length} heute erledigt · ${pct}%`}
      />

      {active.length > 0 && (
        <>
          {/* Progress overview */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6 flex items-center gap-5">
            <CircularProgress
              value={pct}
              size={72}
              strokeWidth={7}
              color="#22c55e"
              label={`${pct}%`}
            />
            <div>
              <div className="text-white font-semibold text-lg">{doneToday} / {active.length}</div>
              <div className="text-zinc-400 text-sm">Routinen heute erledigt</div>
              {doneToday === active.length && active.length > 0 && (
                <div className="text-green-400 text-xs mt-1">🎉 Alle Routinen abgehakt!</div>
              )}
            </div>
          </div>

          {/* Routine grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
            {active.map((r) => (
              <div
                key={r.id}
                className={cn(
                  "flex items-center gap-4 p-4 rounded-xl border transition-all",
                  r.completed_today
                    ? "bg-green-950/40 border-green-900/50"
                    : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
                )}
              >
                <div className="shrink-0">
                  {r.completed_today ? (
                    <CircularProgress value={100} size={44} strokeWidth={4} color="#22c55e" label="✓" />
                  ) : (
                    <CircularProgress value={0} size={44} strokeWidth={4} color="#3f3f46" label="☐" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div
                    className={cn(
                      "font-medium text-sm",
                      r.completed_today ? "text-zinc-400 line-through" : "text-white"
                    )}
                  >
                    {r.title}
                  </div>
                  {r.description && (
                    <p className="text-zinc-500 text-xs mt-0.5 truncate">{r.description}</p>
                  )}
                  {r.frequency_human && (
                    <p className="text-zinc-600 text-xs mt-0.5">{r.frequency_human}</p>
                  )}
                </div>
                <div className="shrink-0">
                  {r.completed_today ? (
                    <span className="text-green-400 text-xs font-medium bg-green-950/60 px-2 py-1 rounded-full border border-green-900/60">
                      Done ✅
                    </span>
                  ) : (
                    <span className="text-zinc-500 text-xs bg-zinc-800 px-2 py-1 rounded-full">
                      Offen
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Paused */}
      {paused.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-3 flex items-center gap-2">
            <span>⏸️</span> Pausierte Routinen
          </h2>
          <div className="space-y-2">
            {paused.map((r) => (
              <div key={r.id} className="flex items-center gap-4 p-3 rounded-lg bg-zinc-800/30 border border-zinc-800">
                <span className="text-xl opacity-40">⏸</span>
                <div className="flex-1 min-w-0">
                  <div className="text-zinc-500 font-medium text-sm">{r.title}</div>
                  {r.frequency_human && (
                    <div className="text-zinc-600 text-xs">{r.frequency_human}</div>
                  )}
                </div>
                <span className="text-yellow-400 text-xs bg-yellow-900/40 border border-yellow-800/40 px-2 py-0.5 rounded-full">
                  Pausiert
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {routines.length === 0 && (
        <EmptyState emoji="🔄" message="Keine Routinen — per Telegram erstellen!" />
      )}
    </div>
  );
}
