"use client";

import Header from "@/components/Header";
import Badge from "@/components/Badge";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
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

  return (
    <div>
      <Header
        title="🔄 Routinen"
        subtitle={`${doneToday}/${active.length} heute erledigt`}
      />

      {/* Today's progress */}
      {active.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold">Heute</h2>
            <span className="text-zinc-400 text-sm">
              {doneToday}/{active.length}
            </span>
          </div>
          <div className="space-y-3">
            {active.map((r) => (
              <div
                key={r.id}
                className={cn(
                  "flex items-center gap-4 p-4 rounded-lg border transition-all",
                  r.completed_today
                    ? "bg-green-950/50 border-green-900"
                    : "bg-zinc-800/50 border-zinc-700"
                )}
              >
                <span className="text-2xl">{r.completed_today ? "✅" : "☐"}</span>
                <div className="flex-1 min-w-0">
                  <div
                    className={cn(
                      "font-medium",
                      r.completed_today ? "text-zinc-400 line-through" : "text-white"
                    )}
                  >
                    {r.title}
                  </div>
                  {r.description && (
                    <p className="text-zinc-500 text-sm mt-0.5">{r.description}</p>
                  )}
                  {r.frequency_human && (
                    <p className="text-zinc-500 text-xs mt-0.5">{r.frequency_human}</p>
                  )}
                </div>
                {r.completed_today ? (
                  <Badge variant="green">Erledigt</Badge>
                ) : (
                  <Badge variant="outline">Ausstehend</Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Paused */}
      {paused.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-3 flex items-center gap-2">
            <span>⏸️</span> Pausierte Routinen
          </h2>
          <div className="space-y-2">
            {paused.map((r) => (
              <div
                key={r.id}
                className="flex items-center gap-4 p-3 rounded-lg bg-zinc-800/30 border border-zinc-800"
              >
                <span className="text-xl opacity-50">⏸</span>
                <div className="flex-1 min-w-0">
                  <div className="text-zinc-500 font-medium">{r.title}</div>
                  {r.frequency_human && (
                    <div className="text-zinc-600 text-xs">{r.frequency_human}</div>
                  )}
                </div>
                <Badge variant="yellow">Pausiert</Badge>
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
