"use client";

import React from "react";
import { useHealthDaily } from "@/hooks/useApi";

const SLOTS = [
  { key: "morning" as const, label: "Morgens", emoji: "🌅" },
  { key: "midday" as const, label: "Mittags", emoji: "☀️" },
  { key: "evening" as const, label: "Abends", emoji: "🌙" },
];

export default function SupplementsCard() {
  const { data, isLoading, error } = useHealthDaily();
  const [activeSlot, setActiveSlot] = React.useState<"morning" | "midday" | "evening">("morning");

  if (isLoading || error || !data) return null;

  const supplements = data.supplements;
  const totalCount = SLOTS.reduce((n, s) => n + supplements[s.key].length, 0);
  if (totalCount === 0) return null;

  const items = supplements[activeSlot];

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl mb-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
        <h2 className="text-white font-semibold text-sm flex items-center gap-2">
          🧪 Supplemente heute
        </h2>
        <span className="text-zinc-500 text-xs">{totalCount} gesamt</span>
      </div>

      {/* Slot tabs */}
      <div className="flex border-b border-zinc-800">
        {SLOTS.map((s) => {
          const count = supplements[s.key].length;
          return (
            <button
              key={s.key}
              onClick={() => setActiveSlot(s.key)}
              className={`flex-1 py-2 text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${
                activeSlot === s.key
                  ? "text-white border-b-2 border-blue-500 bg-zinc-800/40"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <span>{s.emoji}</span>
              <span>{s.label}</span>
              {count > 0 && (
                <span className="bg-zinc-700 text-zinc-400 text-[10px] px-1.5 rounded-full">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Items */}
      <div className="px-4 py-3">
        {items.length === 0 ? (
          <p className="text-zinc-600 text-xs text-center py-2">Keine Supplemente für diesen Slot</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {items.map((item, i) => (
              <div key={i} className="flex items-start gap-2 py-1">
                <span className="text-zinc-600 mt-0.5 shrink-0 text-xs">☐</span>
                <div className="min-w-0">
                  <span className="text-zinc-200 text-sm">{item.name}</span>
                  {item.dose && (
                    <div className="text-zinc-500 text-xs truncate">{item.dose}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
