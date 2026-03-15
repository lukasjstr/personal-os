"use client";

import React from "react";
import { useHealthDaily } from "@/hooks/useApi";
import type { DailyHealthData, SupplementItem } from "@/lib/api";

const SLOT_LABEL: Record<string, string> = {
  morning: "Morgens",
  midday: "Mittags",
  evening: "Abends",
};

const SLOT_EMOJI: Record<string, string> = {
  morning: "🌅",
  midday: "☀️",
  evening: "🌙",
};

const SPLIT_COLOR: Record<string, string> = {
  Beine: "text-green-400",
  Pull: "text-blue-400",
  Push: "text-orange-400",
  Rest: "text-zinc-400",
};

function SupplementSlot({
  slot,
  items,
}: {
  slot: string;
  items: SupplementItem[];
}) {
  const [open, setOpen] = React.useState(slot === "morning");
  const [checked, setChecked] = React.useState<Set<number>>(new Set());

  const toggle = (i: number) =>
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  const done = checked.size;
  const total = items.length;

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-zinc-800/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span>{SLOT_EMOJI[slot] ?? "💊"}</span>
          <span className="text-zinc-300 text-sm font-medium">
            {SLOT_LABEL[slot] ?? slot}
          </span>
          {total > 0 && (
            <span
              className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                done === total
                  ? "bg-green-500/20 text-green-400"
                  : "bg-zinc-800 text-zinc-500"
              }`}
            >
              {done}/{total}
            </span>
          )}
        </div>
        <span className="text-zinc-600 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <ul className="px-3 pb-3 space-y-1.5">
          {items.map((item, i) => (
            <li
              key={i}
              className="flex items-start gap-2.5 cursor-pointer group"
              onClick={() => toggle(i)}
            >
              <span
                className={`mt-0.5 w-4 h-4 shrink-0 rounded border flex items-center justify-center text-[10px] font-bold transition-colors ${
                  checked.has(i)
                    ? "bg-green-500 border-green-500 text-white"
                    : "border-zinc-600 text-transparent group-hover:border-zinc-400"
                }`}
              >
                ✓
              </span>
              <div className="flex-1 min-w-0">
                <span
                  className={`text-sm transition-colors ${
                    checked.has(i)
                      ? "text-zinc-600 line-through"
                      : "text-zinc-200"
                  }`}
                >
                  {item.name}
                </span>
                {item.dose && (
                  <div className="text-zinc-500 text-xs mt-0.5 truncate">
                    {item.dose}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FitnessSection({ data }: { data: DailyHealthData["fitness"] }) {
  if (data.is_rest_day) {
    return (
      <div className="flex items-center gap-3 py-2">
        <span className="text-2xl">🛌</span>
        <div>
          <div className="text-zinc-300 text-sm font-medium">Rest Day</div>
          <div className="text-zinc-500 text-xs">Aktive Regeneration</div>
        </div>
      </div>
    );
  }

  const splitColor = SPLIT_COLOR[data.split ?? ""] ?? "text-white";

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className={`text-lg font-bold ${splitColor}`}>
          {data.split ?? "–"}
        </span>
        {data.focus && (
          <span className="text-zinc-500 text-xs">{data.focus}</span>
        )}
      </div>
      {data.exercises.length > 0 && (
        <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
          {data.exercises.map((ex, i) => (
            <li key={i} className="flex items-center gap-1.5 text-xs text-zinc-400">
              <span className="text-zinc-600">☐</span>
              <span className="truncate">{ex}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MacrosSection({ macros }: { macros: DailyHealthData["macros"] }) {
  const bars = [
    { label: "Protein", value: macros.protein, unit: "g", max: 200, color: "bg-blue-500" },
    { label: "Fett", value: macros.fat, unit: "g", max: 250, color: "bg-yellow-500" },
    { label: "Carbs", value: macros.carbs, unit: "g", max: 50, color: "bg-orange-500" },
  ];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-zinc-400 text-xs">Kalorien</span>
        <span className="text-zinc-200 text-sm font-semibold">
          {macros.calories} kcal
        </span>
      </div>
      {bars.map((b) => (
        <div key={b.label}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-zinc-500">{b.label}</span>
            <span className="text-zinc-400">
              {b.value}
              {b.unit}
            </span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full ${b.color} rounded-full`}
              style={{ width: `${Math.min(100, (b.value / b.max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
      <div className="flex items-center justify-between pt-1">
        <span className="text-zinc-500 text-xs">💧 Wasser</span>
        <span className="text-blue-400 text-xs font-medium">{macros.water}</span>
      </div>
    </div>
  );
}

export default function HealthCard() {
  const { data, error, isLoading } = useHealthDaily();
  const [tab, setTab] = React.useState<"fitness" | "supplements" | "macros">(
    "fitness"
  );

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl mb-6 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-zinc-800">
        <h2 className="text-white font-semibold flex items-center gap-2">
          <span>🏥</span> Health heute
        </h2>
        {data?.fitness.split && !data.fitness.is_rest_day && (
          <span
            className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
              data.fitness.split === "Beine"
                ? "border-green-700 text-green-400 bg-green-900/20"
                : data.fitness.split === "Pull"
                ? "border-blue-700 text-blue-400 bg-blue-900/20"
                : "border-orange-700 text-orange-400 bg-orange-900/20"
            }`}
          >
            {data.fitness.split}
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-zinc-800">
        {(
          [
            { id: "fitness", label: "💪 Training" },
            { id: "supplements", label: "🧪 Supplemente" },
            { id: "macros", label: "🥩 Makros" },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 text-xs font-medium transition-colors ${
              tab === t.id
                ? "text-white border-b-2 border-blue-500 bg-blue-950/20"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="px-5 py-4">
        {isLoading && (
          <p className="text-zinc-500 text-sm text-center py-4">Lädt…</p>
        )}
        {error && (
          <p className="text-red-400 text-sm text-center py-4">
            Fehler beim Laden der Health-Daten
          </p>
        )}
        {data && (
          <>
            {tab === "fitness" && (
              <FitnessSection data={data.fitness} />
            )}

            {tab === "supplements" && (
              <div className="space-y-2">
                {(["morning", "midday", "evening"] as const).map((slot) => (
                  <SupplementSlot
                    key={slot}
                    slot={slot}
                    items={data.supplements[slot]}
                  />
                ))}
              </div>
            )}

            {tab === "macros" && (
              <MacrosSection macros={data.macros} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
