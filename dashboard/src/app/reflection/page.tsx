"use client";

import { useState, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import Header from "@/components/Header";
import LoadingSpinner, { EmptyState, ErrorState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useReflections } from "@/hooks/useApi";
import type { WeeklyReflection } from "@/lib/api";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Trash2 } from "lucide-react";

// ─── Score color helper ──────────────────────────────────────────────────────

function scoreColor(score: number | null): string {
  if (!score) return "text-zinc-500";
  if (score >= 8) return "text-emerald-400";
  if (score >= 6) return "text-yellow-400";
  if (score >= 4) return "text-orange-400";
  return "text-red-400";
}

function scoreBg(score: number | null): string {
  if (!score) return "bg-zinc-800";
  if (score >= 8) return "bg-emerald-500/15 border-emerald-500/30";
  if (score >= 6) return "bg-yellow-500/15 border-yellow-500/30";
  if (score >= 4) return "bg-orange-500/15 border-orange-500/30";
  return "bg-red-500/15 border-red-500/30";
}

// ─── Detail Modal ─────────────────────────────────────────────────────────────

function ReflectionDetail({
  reflection,
  onClose,
}: {
  reflection: WeeklyReflection;
  onClose: () => void;
}) {
  const weekLabel = `KW${reflection.week_number}/${reflection.year}`;
  const dateLabel = new Date(reflection.week_start).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  const [aiSummary, setAiSummary] = useState(reflection.ai_summary);
  const [regenerating, setRegenerating] = useState(false);
  const [regenError, setRegenError] = useState<string | null>(null);
  const ai = aiSummary;
  const raw = reflection.raw_answers || {};

  const handleRegenerate = useCallback(async () => {
    setRegenerating(true);
    setRegenError(null);
    try {
      const res = await api.regenerateReflectionInsights(reflection.id);
      if (res.ai_summary) setAiSummary(res.ai_summary as unknown as WeeklyReflection["ai_summary"]);
    } catch {
      setRegenError("Insights konnten nicht neu generiert werden.");
    } finally {
      setRegenerating(false);
    }
  }, [reflection.id]);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-2xl mt-8 mb-8">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-zinc-800">
          <div>
            <h2 className="text-white font-bold text-lg">🪞 Reflexion {weekLabel}</h2>
            <p className="text-zinc-500 text-sm mt-0.5">Woche ab {dateLabel}</p>
          </div>
          <div className="flex items-center gap-2">
            {reflection.week_score && (
              <div className={cn(
                "border rounded-xl px-3 py-1.5 text-sm font-bold",
                scoreBg(reflection.week_score),
                scoreColor(reflection.week_score),
              )}>
                {reflection.week_score}/10
              </div>
            )}
            {reflection.status === "completed" && (
              <button
                onClick={handleRegenerate}
                disabled={regenerating}
                title="AI-Insights neu generieren"
                className="px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white rounded-lg text-xs transition-colors disabled:opacity-50"
              >
                {regenerating ? "..." : "🤖 Neu"}
              </button>
            )}
            <button
              onClick={onClose}
              className="text-zinc-500 hover:text-white transition-colors text-xl leading-none"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {regenError && (
            <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-3 py-2 text-red-400 text-xs">
              {regenError}
            </div>
          )}
          {/* Answers */}
          {reflection.biggest_win && (
            <Section label="💪 Größter Erfolg" content={reflection.biggest_win} />
          )}
          {reflection.biggest_blocker && (
            <Section label="🚧 Größter Blocker" content={reflection.biggest_blocker} />
          )}
          {reflection.key_learning && (
            <Section label="💡 Wichtigste Erkenntnis" content={reflection.key_learning} />
          )}
          {typeof raw.q5 === "string" && raw.q5 && (
            <Section label="🎯 Vorsatz nächste Woche" content={raw.q5} />
          )}
          {typeof raw.q7_input === "string" && raw.q7_input && (
            <Section label="🗓 4-Wochen-Ziele" content={raw.q7_input} />
          )}

          {/* AI Summary */}
          {ai && (
            <div className="border border-blue-500/20 bg-blue-500/5 rounded-xl p-4 space-y-4">
              <div className="text-blue-400 font-semibold text-sm">🤖 AI-Analyse</div>

              {ai.recommendations && ai.recommendations.length > 0 && (
                <div>
                  <div className="text-zinc-400 text-xs uppercase tracking-wide mb-2">
                    Top Empfehlungen
                  </div>
                  <ol className="space-y-1">
                    {ai.recommendations.map((rec, i) => (
                      <li key={i} className="flex gap-2 text-sm text-zinc-300">
                        <span className="text-blue-400 font-bold shrink-0">{i + 1}.</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {ai.goal_adjustments && ai.goal_adjustments.length > 0 && (
                <div>
                  <div className="text-zinc-400 text-xs uppercase tracking-wide mb-2">
                    Ziel-Anpassungen
                  </div>
                  <ul className="space-y-1">
                    {ai.goal_adjustments.map((adj, i) => (
                      <li key={i} className="flex gap-2 text-sm text-zinc-300">
                        <span className="text-orange-400 shrink-0">•</span>
                        <span>{adj}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {ai.motivation && (
                <div className="border-t border-blue-500/20 pt-3">
                  <p className="text-zinc-300 text-sm italic">{ai.motivation}</p>
                </div>
              )}
            </div>
          )}

          {reflection.status === "in_progress" && (
            <div className="flex items-center gap-2 text-yellow-400 text-sm bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">
              <span>⏳</span>
              <span>Reflexion noch in Bearbeitung</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ label, content }: { label: string; content: string }) {
  return (
    <div>
      <div className="text-zinc-400 text-xs uppercase tracking-wide mb-1">{label}</div>
      <p className="text-zinc-200 text-sm leading-relaxed">{content}</p>
    </div>
  );
}

// ─── Reflection Card ──────────────────────────────────────────────────────────

function ReflectionCard({
  reflection,
  onClick,
  onDelete,
}: {
  reflection: WeeklyReflection;
  onClick: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const weekLabel = `KW${reflection.week_number}`;
  const dateLabel = new Date(reflection.week_start).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
  const isComplete = reflection.status === "completed";

  return (
    <div className={cn(
      "relative rounded-xl border transition-all group",
      isComplete ? "bg-zinc-900 border-zinc-800" : "bg-zinc-900/60 border-zinc-800/60 opacity-75"
    )}>
      <button
        onClick={onClick}
        className="w-full text-left p-4 hover:bg-zinc-800/20 rounded-xl transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-white font-semibold text-sm">{weekLabel}</span>
              {!isComplete && (
                <span className="text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-1.5 py-0.5 rounded-full">
                  Offen
                </span>
              )}
            </div>
            <div className="text-zinc-500 text-xs">{dateLabel}</div>
            {reflection.biggest_win && (
              <p className="text-zinc-400 text-xs mt-2 line-clamp-2">
                💪 {reflection.biggest_win}
              </p>
            )}
          </div>

          {reflection.week_score ? (
            <div className={cn(
              "shrink-0 rounded-xl border px-3 py-1.5 text-sm font-bold",
              scoreBg(reflection.week_score),
              scoreColor(reflection.week_score),
            )}>
              {reflection.week_score}/10
            </div>
          ) : (
            <div className="shrink-0 rounded-xl border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-600">
              —
            </div>
          )}
        </div>
      </button>
      <button
        onClick={onDelete}
        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-zinc-800 transition-all"
        title="Reflexion löschen"
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}

// ─── Score Trend Chart ────────────────────────────────────────────────────────

function ScoreTrendChart({ reflections }: { reflections: WeeklyReflection[] }) {
  const chartData = reflections
    .filter((r) => r.week_score !== null && r.status === "completed")
    .map((r) => ({
      week: `KW${r.week_number}`,
      score: r.week_score,
    }))
    .reverse(); // chronological order

  if (chartData.length < 2) return null;

  const avg =
    chartData.reduce((s, d) => s + (d.score ?? 0), 0) / chartData.length;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold text-sm">📈 Wochen-Score Verlauf</h3>
        <span className="text-zinc-500 text-xs">Ø {avg.toFixed(1)}/10</span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="week" tick={{ fill: "#71717a", fontSize: 11 }} />
          <YAxis domain={[0, 10]} tick={{ fill: "#71717a", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: "8px",
              color: "#f4f4f5",
              fontSize: "12px",
            }}
            formatter={(value) => [`${value}/10`, "Score"]}
          />
          <ReferenceLine
            y={avg}
            stroke="#3b82f6"
            strokeDasharray="4 4"
            strokeOpacity={0.5}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ fill: "#3b82f6", r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ReflectionPage() {
  const { data, error, isLoading, mutate } = useReflections();
  const [selected, setSelected] = useState<WeeklyReflection | null>(null);
  const [deletingReflection, setDeletingReflection] = useState<WeeklyReflection | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { toasts, addToast, dismissToast } = useToast();

  const handleDelete = useCallback(async () => {
    if (!deletingReflection) return;
    setDeleting(true);
    try {
      await api.deleteReflection(deletingReflection.id);
      await mutate();
      addToast("Reflexion gelöscht", "success");
      setDeletingReflection(null);
    } catch {
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
    }
  }, [deletingReflection, mutate, addToast]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;
  if (!data) return <LoadingSpinner />;

  const reflections = data?.reflections ?? [];
  const completed = reflections.filter((r) => r.status === "completed");
  const avgScore =
    completed.length > 0 && completed.some((r) => r.week_score !== null)
      ? (
          completed.reduce((s, r) => s + (r.week_score ?? 0), 0) /
          completed.filter((r) => r.week_score !== null).length
        ).toFixed(1)
      : null;

  return (
    <div>
      <Header
        title="🪞 Reflexion"
        subtitle={
          completed.length > 0
            ? `${completed.length} Reflexionen · ${avgScore ? `Ø ${avgScore}/10` : ""}`
            : "Noch keine Reflexionen"
        }
      />

      {/* Score trend chart */}
      {reflections.length >= 2 && <ScoreTrendChart reflections={reflections} />}

      {/* Stats row */}
      {reflections.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-white">{reflections.length}</div>
            <div className="text-zinc-500 text-xs mt-0.5">Gesamt</div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-white">{completed.length}</div>
            <div className="text-zinc-500 text-xs mt-0.5">Abgeschlossen</div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 text-center">
            <div className={cn("text-2xl font-bold", scoreColor(avgScore ? parseFloat(avgScore) : null))}>
              {avgScore ?? "—"}
            </div>
            <div className="text-zinc-500 text-xs mt-0.5">Ø Score</div>
          </div>
        </div>
      )}

      {/* Recurring patterns */}
      {completed.length >= 2 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <h3 className="text-white font-semibold text-sm mb-3">🔍 Wiederkehrende Muster</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {completed.slice(0, 4).some((r) => r.biggest_blocker) && (
              <div>
                <div className="text-zinc-500 text-xs uppercase tracking-wide mb-2">Letzte Blocker</div>
                <div className="space-y-1">
                  {completed.slice(0, 3).filter((r) => r.biggest_blocker).map((r) => (
                    <div key={r.id} className="flex items-start gap-2">
                      <span className="text-red-400 text-xs mt-0.5 shrink-0">•</span>
                      <span className="text-zinc-400 text-xs line-clamp-2">{r.biggest_blocker}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {completed.slice(0, 4).some((r) => r.biggest_win) && (
              <div>
                <div className="text-zinc-500 text-xs uppercase tracking-wide mb-2">Letzte Erfolge</div>
                <div className="space-y-1">
                  {completed.slice(0, 3).filter((r) => r.biggest_win).map((r) => (
                    <div key={r.id} className="flex items-start gap-2">
                      <span className="text-emerald-400 text-xs mt-0.5 shrink-0">✓</span>
                      <span className="text-zinc-400 text-xs line-clamp-2">{r.biggest_win}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reflection list */}
      {reflections.length === 0 ? (
        <EmptyState
          emoji="🪞"
          message="Noch keine Reflexionen vorhanden. Die erste Reflexion startet automatisch jeden Sonntag Abend."
        />
      ) : (
        <div className="space-y-3">
          {reflections.map((r) => (
            <ReflectionCard
              key={r.id}
              reflection={r}
              onClick={() => setSelected(r)}
              onDelete={(e) => { e.stopPropagation(); setDeletingReflection(r); }}
            />
          ))}
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <ReflectionDetail
          reflection={selected}
          onClose={() => setSelected(null)}
        />
      )}

      <ConfirmDialog
        open={!!deletingReflection}
        title="Reflexion löschen?"
        message={`Reflexion KW${deletingReflection?.week_number}/${deletingReflection?.year} wird dauerhaft gelöscht.`}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeletingReflection(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
