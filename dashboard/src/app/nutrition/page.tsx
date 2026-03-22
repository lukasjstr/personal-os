"use client";

import { useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useApi } from "@/hooks/useApi";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

// ── Types ──────────────────────────────────────────────────────────────────

interface NutritionTotals {
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  sodium_mg: number | null;
  sugar_g: number | null;
}

interface FoodItem {
  id: number;
  food_name: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  sodium_mg: number | null;
}

interface DailyNutrition {
  date: string;
  meals: Record<string, FoodItem[]>;
  totals: NutritionTotals;
  has_data: boolean;
  entry_count: number;
}

interface HistoryDay {
  date: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  sodium_mg: number | null;
}

// ── Macro Ring ─────────────────────────────────────────────────────────────

function MacroRing({
  value,
  max,
  label,
  unit,
  color,
  warning,
}: {
  value: number | null;
  max: number;
  label: string;
  unit: string;
  color: string;
  warning?: boolean;
}) {
  const pct = value ? Math.min((value / max) * 100, 100) : 0;
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-24 h-24">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 88 88">
          <circle cx="44" cy="44" r={radius} fill="none" stroke="#1e293b" strokeWidth="8" />
          <circle
            cx="44"
            cy="44"
            r={radius}
            fill="none"
            stroke={warning && pct > 80 ? "#ef4444" : color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: "stroke-dashoffset 0.5s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-slate-100">
            {value ? Math.round(value) : "—"}
          </span>
          <span className="text-xs text-slate-400">{unit}</span>
        </div>
      </div>
      <span className="text-sm text-slate-300 font-medium">{label}</span>
    </div>
  );
}

// ── Meal Section ──────────────────────────────────────────────────────────

const MEAL_CONFIG: Record<string, { label: string; emoji: string }> = {
  breakfast: { label: "Frühstück", emoji: "🌅" },
  lunch: { label: "Mittagessen", emoji: "☀️" },
  dinner: { label: "Abendessen", emoji: "🌙" },
  snack: { label: "Snacks", emoji: "🍎" },
};

function MealSection({
  mealType,
  items,
}: {
  mealType: string;
  items: FoodItem[];
}) {
  const config = MEAL_CONFIG[mealType] || { label: mealType, emoji: "🍴" };
  const totalCal = items.reduce((sum, i) => sum + (i.calories || 0), 0);

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{config.emoji}</span>
        <span className="font-semibold text-slate-200">{config.label}</span>
        {totalCal > 0 && (
          <span className="text-sm text-slate-400 ml-auto">{Math.round(totalCal)} kcal</span>
        )}
      </div>
      <div className="space-y-1 ml-7">
        {items.map((item) => (
          <div key={item.id} className="flex items-center justify-between">
            <span className="text-slate-300 text-sm">{item.food_name}</span>
            <div className="flex gap-3 text-xs text-slate-500">
              {item.calories && <span>{Math.round(item.calories)} kcal</span>}
              {item.protein_g && <span className="text-blue-400">P {Math.round(item.protein_g)}g</span>}
              {item.sodium_mg && item.sodium_mg > 200 && (
                <span className="text-orange-400">Na {Math.round(item.sodium_mg)}mg</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function NutritionPage() {
  const [historyDays, setHistoryDays] = useState(14);

  const { data: daily, isLoading: dailyLoading, error: dailyError } = useApi<DailyNutrition>(
    "/api/nutrition/daily"
  );
  const { data: history, isLoading: historyLoading } = useApi<HistoryDay[]>(
    `/api/nutrition/history?days=${historyDays}`
  );

  if (dailyLoading) return <LoadingSpinner />;
  if (dailyError) return <ErrorState message="Ernährungsdaten konnten nicht geladen werden." />;

  const totals = daily?.totals;
  const mealOrder = ["breakfast", "lunch", "dinner", "snack"];

  // Sodium risk
  const sodiumAlert = totals?.sodium_mg && totals.sodium_mg > 2300;

  // History chart data
  const chartData = (history || [])
    .slice(0, historyDays)
    .reverse()
    .map((d) => ({
      date: d.date.slice(5), // MM-DD
      calories: d.calories ? Math.round(d.calories) : null,
      protein: d.protein_g ? Math.round(d.protein_g) : null,
      sodium: d.sodium_mg ? Math.round(d.sodium_mg) : null,
    }));

  return (
    <div className="min-h-screen bg-slate-900">
      <Header title="Ernährung" />
      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">

        {/* ── Today's Summary ─────────────────────────────────────── */}
        <div className="bg-slate-800 rounded-2xl p-6">
          <h2 className="text-xl font-bold text-slate-100 mb-6">Heute</h2>

          {!daily?.has_data ? (
            <EmptyState
              title="Noch keine Mahlzeiten geloggt"
              description="Schreibe einfach an den Bot was du gegessen hast — die KI extrahiert die Nährwerte automatisch."
            />
          ) : (
            <>
              {/* Macro Rings */}
              <div className="flex justify-around mb-8">
                <MacroRing
                  value={totals?.calories ?? null}
                  max={2500}
                  label="Kalorien"
                  unit="kcal"
                  color="#f59e0b"
                />
                <MacroRing
                  value={totals?.protein_g ?? null}
                  max={180}
                  label="Protein"
                  unit="g"
                  color="#3b82f6"
                />
                <MacroRing
                  value={totals?.carbs_g ?? null}
                  max={300}
                  label="Kohlenhydrate"
                  unit="g"
                  color="#8b5cf6"
                />
                <MacroRing
                  value={totals?.fat_g ?? null}
                  max={80}
                  label="Fett"
                  unit="g"
                  color="#10b981"
                />
              </div>

              {/* Sodium Alert */}
              {sodiumAlert && (
                <div className="bg-red-900/30 border border-red-500/40 rounded-xl p-4 mb-6 flex items-start gap-3">
                  <span className="text-2xl">⚠️</span>
                  <div>
                    <p className="font-semibold text-red-300">Natrium-Warnung</p>
                    <p className="text-sm text-red-400 mt-1">
                      Heute {Math.round(totals?.sodium_mg || 0)}mg Natrium — über der empfohlenen Tagesmenge (2.300mg).
                      Das kann morgen Energie und Schlaf beeinflussen.
                    </p>
                  </div>
                </div>
              )}

              {/* Macro Bar */}
              <div className="mb-6">
                <div className="flex justify-between text-xs text-slate-400 mb-2">
                  <span>Makros</span>
                  <span>
                    {totals?.protein_g ? Math.round(totals.protein_g) : 0}g Protein ·{" "}
                    {totals?.carbs_g ? Math.round(totals.carbs_g) : 0}g Carbs ·{" "}
                    {totals?.fat_g ? Math.round(totals.fat_g) : 0}g Fett
                  </span>
                </div>
                <div className="flex h-3 rounded-full overflow-hidden bg-slate-700">
                  {totals?.protein_g && totals?.carbs_g && totals?.fat_g ? (() => {
                    const total = (totals.protein_g * 4) + (totals.carbs_g * 4) + (totals.fat_g * 9);
                    return total > 0 ? (
                      <>
                        <div
                          style={{ width: `${(totals.protein_g * 4 / total) * 100}%` }}
                          className="bg-blue-500"
                        />
                        <div
                          style={{ width: `${(totals.carbs_g * 4 / total) * 100}%` }}
                          className="bg-purple-500"
                        />
                        <div
                          style={{ width: `${(totals.fat_g * 9 / total) * 100}%` }}
                          className="bg-emerald-500"
                        />
                      </>
                    ) : null;
                  })() : null}
                </div>
                <div className="flex gap-4 mt-2 text-xs">
                  <span className="text-blue-400">● Protein</span>
                  <span className="text-purple-400">● Carbs</span>
                  <span className="text-emerald-400">● Fett</span>
                </div>
              </div>

              {/* Meal Breakdown */}
              <div className="border-t border-slate-700 pt-4">
                <h3 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-wide">
                  Mahlzeiten
                </h3>
                {mealOrder.map((mt) => {
                  const items = daily?.meals[mt];
                  if (!items || items.length === 0) return null;
                  return <MealSection key={mt} mealType={mt} items={items} />;
                })}
              </div>
            </>
          )}
        </div>

        {/* ── 14-Day History ──────────────────────────────────────── */}
        <div className="bg-slate-800 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-slate-100">Verlauf</h2>
            <div className="flex gap-2">
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => setHistoryDays(d)}
                  className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                    historyDays === d
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                  }`}
                >
                  {d}T
                </button>
              ))}
            </div>
          </div>

          {historyLoading ? (
            <LoadingSpinner />
          ) : chartData.length === 0 ? (
            <EmptyState
              title="Noch keine Verlaufsdaten"
              description="Logge regelmäßig deine Mahlzeiten um Trends zu sehen."
            />
          ) : (
            <div className="space-y-6">
              {/* Calories Chart */}
              <div>
                <p className="text-sm text-slate-400 mb-3">🔥 Kalorien (kcal)</p>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: 8 }}
                      labelStyle={{ color: "#94a3b8" }}
                    />
                    <ReferenceLine y={2000} stroke="#f59e0b" strokeDasharray="4 4" opacity={0.5} />
                    <Bar dataKey="calories" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Protein Chart */}
              <div>
                <p className="text-sm text-slate-400 mb-3">💪 Protein (g)</p>
                <ResponsiveContainer width="100%" height={100}>
                  <LineChart data={chartData} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: 8 }}
                      labelStyle={{ color: "#94a3b8" }}
                    />
                    <ReferenceLine y={150} stroke="#3b82f6" strokeDasharray="4 4" opacity={0.5} />
                    <Line
                      type="monotone"
                      dataKey="protein"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={{ r: 3, fill: "#3b82f6" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Sodium Chart */}
              <div>
                <p className="text-sm text-slate-400 mb-3">🧂 Natrium (mg) — Ziel: &lt; 2.300mg</p>
                <ResponsiveContainer width="100%" height={100}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: 8 }}
                      labelStyle={{ color: "#94a3b8" }}
                    />
                    <ReferenceLine y={2300} stroke="#ef4444" strokeDasharray="4 4" opacity={0.6} />
                    <Bar
                      dataKey="sodium"
                      fill="#f97316"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

        {/* ── Info Card ──────────────────────────────────────────────── */}
        <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700/50">
          <h3 className="font-semibold text-slate-200 mb-2">💡 Wie du loggst</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Schreib einfach an den Telegram-Bot was du gegessen hast —
            z.B. <em className="text-slate-300">"Mittag: Hähnchenbrust 200g mit Reis und Gemüse"</em>.
            Die KI schätzt alle Nährwerte automatisch. Für genauere Werte kannst du
            Mengen und Nährwerte direkt mitangeben.
          </p>
        </div>

      </main>
    </div>
  );
}
