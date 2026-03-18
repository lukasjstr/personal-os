"use client";

import { useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import useSWR from "swr";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Sun, CloudSun, Moon, Pill, Droplets, Flame, RefreshCw } from "lucide-react";

interface Supplement {
  name: string;
  dose: string;
  note?: string;
  cycle_key?: string;
}

interface Protocol {
  meta: { name: string; version: number; cycle_anchor_date: string };
  macro_targets: { calories_kcal: number; protein_g: number; net_carbs_max_g: number; fat_g: number };
  hydration: { water_l_min: number; water_l_max: number; electrolytes: string };
  micro_targets: Record<string, string>;
  stacks: { daily: Supplement[]; morning: Supplement[]; midday: Supplement[]; evening: Supplement[]; optional: Supplement[] };
  cycles: { key: string; label: string; days_on: number; days_off: number }[];
}

const STACK_CONFIG = [
  { key: "morning", label: "Morgens", sublabel: "Fasten / Fokusphase", icon: Sun, color: "text-amber-400", bg: "bg-amber-950/30 border-amber-800/30" },
  { key: "midday", label: "Mittags", sublabel: "Leistungsphase", icon: CloudSun, color: "text-blue-400", bg: "bg-blue-950/30 border-blue-800/30" },
  { key: "evening", label: "Abends", sublabel: "Regeneration", icon: Moon, color: "text-indigo-400", bg: "bg-indigo-950/30 border-indigo-800/30" },
  { key: "daily", label: "Ganztags", sublabel: "Basis", icon: Droplets, color: "text-cyan-400", bg: "bg-cyan-950/30 border-cyan-800/30" },
  { key: "optional", label: "Optional", sublabel: "Nach Bedarf", icon: Pill, color: "text-zinc-400", bg: "bg-zinc-800/50 border-zinc-700/50" },
] as const;

function CycleIndicator({ cycle, anchorDate }: { cycle: { key: string; label: string; days_on: number; days_off: number }; anchorDate: string }) {
  const anchor = new Date(anchorDate);
  const now = new Date();
  const daysSince = Math.floor((now.getTime() - anchor.getTime()) / (1000 * 60 * 60 * 24));
  const totalCycle = cycle.days_on + cycle.days_off;
  const dayInCycle = daysSince % totalCycle;
  const isOn = dayInCycle < cycle.days_on;
  const daysLeft = isOn ? cycle.days_on - dayInCycle : cycle.days_off - (dayInCycle - cycle.days_on);

  return (
    <span className={cn(
      "text-[10px] font-semibold px-1.5 py-0.5 rounded-full border",
      isOn ? "bg-green-950/60 text-green-400 border-green-800/50" : "bg-red-950/60 text-red-400 border-red-800/50"
    )}>
      {isOn ? `ON (${daysLeft}d)` : `OFF (${daysLeft}d)`}
    </span>
  );
}

function MacroBar({ label, value, unit, max, color }: { label: string; value: number; unit: string; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-zinc-400 text-xs">{label}</span>
        <span className="text-white text-xs font-medium">{value} {unit}</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function SupplementsPage() {
  const { data, isLoading, error } = useSWR("protocol-supplements", () =>
    fetch(`${window.location.origin}/api/protocols/supplements`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("api_token")}` },
    }).then((r) => r.json()) as Promise<Protocol>
  );

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message="Supplement-Protokoll konnte nicht geladen werden" />;
  if (!data || !data.stacks) return <ErrorState message="Kein Protokoll vorhanden" />;

  const protocol = data;
  const cycleMap = Object.fromEntries((protocol.cycles || []).map((c) => [c.key, c]));

  return (
    <div>
      <Header
        title="💊 Supplement-Protokoll"
        subtitle={protocol.meta?.name || "Keto Supplements"}
      />

      {/* Macro Targets */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Flame className="h-4 w-4 text-orange-400" />
          <h3 className="text-white font-semibold text-sm">Tages-Makros</h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MacroBar label="Kalorien" value={protocol.macro_targets.calories_kcal} unit="kcal" max={3000} color="bg-orange-500" />
          <MacroBar label="Protein" value={protocol.macro_targets.protein_g} unit="g" max={200} color="bg-red-500" />
          <MacroBar label="Netto-Carbs" value={protocol.macro_targets.net_carbs_max_g} unit="g" max={50} color="bg-yellow-500" />
          <MacroBar label="Fett" value={protocol.macro_targets.fat_g} unit="g" max={250} color="bg-blue-500" />
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
          <Droplets className="h-3 w-3" />
          Wasser: {protocol.hydration.water_l_min}–{protocol.hydration.water_l_max}L / Tag
        </div>
      </div>

      {/* Supplement Stacks */}
      <div className="space-y-4 mb-6">
        {STACK_CONFIG.map(({ key, label, sublabel, icon: Icon, color, bg }) => {
          const items = (protocol.stacks as Record<string, Supplement[]>)[key] || [];
          if (items.length === 0) return null;

          return (
            <div key={key} className={cn("rounded-xl border p-5", bg)}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className={cn("h-5 w-5", color)} />
                <div>
                  <h3 className={cn("font-semibold text-sm", color)}>{label}</h3>
                  <p className="text-zinc-500 text-xs">{sublabel}</p>
                </div>
                <span className="ml-auto text-zinc-600 text-xs">{items.length} Supplements</span>
              </div>

              <div className="space-y-2">
                {items.map((item, i) => (
                  <div key={i} className="flex items-start gap-3 py-2 border-b border-white/5 last:border-0">
                    <div className="w-1.5 h-1.5 rounded-full bg-current mt-2 shrink-0" style={{ color: "var(--tw-text-opacity, 1)" }} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-white text-sm font-medium">{item.name}</span>
                        {item.cycle_key && cycleMap[item.cycle_key] && (
                          <CycleIndicator
                            cycle={cycleMap[item.cycle_key]}
                            anchorDate={protocol.meta.cycle_anchor_date}
                          />
                        )}
                      </div>
                      <div className="text-zinc-400 text-xs mt-0.5">{item.dose}</div>
                      {item.note && <div className="text-zinc-600 text-xs italic mt-0.5">{item.note}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Cycles Overview */}
      {protocol.cycles && protocol.cycles.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <RefreshCw className="h-4 w-4 text-purple-400" />
            <h3 className="text-white font-semibold text-sm">Zyklen</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {protocol.cycles.map((cycle) => (
              <div key={cycle.key} className="flex items-center justify-between bg-zinc-800/50 rounded-lg px-3 py-2.5">
                <div>
                  <div className="text-white text-sm">{cycle.label}</div>
                  <div className="text-zinc-500 text-xs">{cycle.days_on}d on / {cycle.days_off}d off</div>
                </div>
                <CycleIndicator cycle={cycle} anchorDate={protocol.meta.cycle_anchor_date} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Micro Targets */}
      {protocol.micro_targets && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-white font-semibold text-sm mb-3">Mikronährstoff-Ziele</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1.5">
            {Object.entries(protocol.micro_targets).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between py-1">
                <span className="text-zinc-400 text-xs capitalize">{key.replace(/_/g, " ").replace(/mg$/, " mg").replace(/g$/, " g").replace(/mcg$/, " mcg").replace(/iu$/, " IE")}</span>
                <span className="text-zinc-200 text-xs font-medium">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
