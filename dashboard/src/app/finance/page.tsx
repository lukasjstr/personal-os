"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, FinanceSummary, FinanceTransaction, FinanceBudget } from "@/lib/api";

const CATEGORY_ICONS: Record<string, string> = {
  essen: "🍽️",
  fitness: "💪",
  bildung: "📚",
  abonnements: "📱",
  transport: "🚗",
  unterhaltung: "🎬",
  shopping: "🛍️",
  gesundheit: "💊",
  wohnen: "🏠",
  sonstiges: "📦",
  einnahmen: "💰",
};

type Tab = "overview" | "transactions" | "budgets";

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-gray-900 rounded-xl p-4 text-center">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

export default function FinancePage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const { data: summary, isLoading: summaryLoading } = useSWR<FinanceSummary>(
    "finance-summary",
    () => api.financeSummary(),
    { refreshInterval: 60_000 }
  );
  const { data: transactions, isLoading: txLoading } = useSWR<FinanceTransaction[]>(
    "finance-transactions",
    () => api.financeTransactions(),
    { refreshInterval: 60_000 }
  );
  const { data: budgets, isLoading: budgetsLoading } = useSWR<FinanceBudget[]>(
    "finance-budgets",
    () => api.financeBudgets(),
    { refreshInterval: 120_000 }
  );

  const loading = summaryLoading || txLoading || budgetsLoading;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
      </div>
    );
  }

  const budgetMap: Record<string, number> = {};
  (budgets || []).forEach((b) => (budgetMap[b.category] = b.monthly_limit));

  const byCategory = summary?.by_category || {};
  const txList = transactions || [];

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">💰 Finanzen</h1>
      {summary && (
        <p className="text-gray-400 mb-6 text-sm">{summary.month}</p>
      )}

      {/* Top Stats */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Einnahmen" value={`${summary.total_income.toFixed(0)}€`} color="text-emerald-400" />
          <StatCard label="Ausgaben" value={`${summary.total_expenses.toFixed(0)}€`} color="text-red-400" />
          <StatCard
            label="Balance"
            value={`${summary.balance >= 0 ? "+" : ""}${summary.balance.toFixed(0)}€`}
            color={summary.balance >= 0 ? "text-emerald-400" : "text-red-400"}
          />
          <StatCard
            label="Sparquote"
            value={`${summary.savings_rate.toFixed(0)}%`}
            color={
              summary.savings_rate >= 20
                ? "text-emerald-400"
                : summary.savings_rate >= 10
                ? "text-yellow-400"
                : "text-red-400"
            }
          />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {(["overview", "transactions", "budgets"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-emerald-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {tab === "overview" ? "Übersicht" : tab === "transactions" ? "Transaktionen" : "Budgets"}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div className="space-y-3">
          {Object.entries(byCategory)
            .sort(([, a], [, b]) => b - a)
            .map(([cat, spent]) => {
              const limit = budgetMap[cat];
              const pct = limit ? Math.min(100, (spent / limit) * 100) : null;
              return (
                <div key={cat} className="bg-gray-900 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">
                      {CATEGORY_ICONS[cat] ?? "📦"} {cat}
                    </span>
                    <span className="text-gray-300 text-sm">
                      {spent.toFixed(0)}€{limit ? ` / ${limit.toFixed(0)}€` : ""}
                    </span>
                  </div>
                  {pct !== null && (
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-yellow-500" : "bg-emerald-500"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          {Object.keys(byCategory).length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <p className="text-4xl mb-3">💸</p>
              <p className="mb-2">Noch keine Ausgaben diesen Monat.</p>
              <p className="text-sm">
                Sag dem Bot:{" "}
                <span className="text-emerald-400 font-mono">&quot;Kaffee 3€&quot;</span> oder{" "}
                <span className="text-emerald-400 font-mono">&quot;Gym-Abo 29.99€&quot;</span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* Transactions Tab */}
      {activeTab === "transactions" && (
        <div className="space-y-2">
          {txList.map((t) => (
            <div key={t.id} className="bg-gray-900 rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span>{CATEGORY_ICONS[t.category] ?? "📦"}</span>
                  <span className="font-medium text-sm">{t.description}</span>
                  {t.is_recurring && (
                    <span className="text-xs bg-blue-900/60 text-blue-300 px-2 py-0.5 rounded-full">
                      🔁 Abo
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  {t.category} · {t.date}
                </p>
              </div>
              <span className={`font-bold ${t.type === "income" ? "text-emerald-400" : "text-red-400"}`}>
                {t.type === "income" ? "+" : "-"}
                {t.amount.toFixed(2)}€
              </span>
            </div>
          ))}
          {txList.length === 0 && (
            <p className="text-gray-500 text-center py-8">Keine Transaktionen gefunden.</p>
          )}
        </div>
      )}

      {/* Budgets Tab */}
      {activeTab === "budgets" && (
        <div className="space-y-3">
          {(budgets || []).map((b) => {
            const spent = byCategory[b.category] || 0;
            const pct = Math.min(100, (spent / b.monthly_limit) * 100);
            return (
              <div key={b.id} className="bg-gray-900 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">
                    {CATEGORY_ICONS[b.category] ?? "📦"} {b.category}
                  </span>
                  <span className="text-emerald-400 font-bold">{b.monthly_limit.toFixed(0)}€/Monat</span>
                </div>
                {spent > 0 && (
                  <>
                    <div className="w-full bg-gray-700 rounded-full h-2 mb-1">
                      <div
                        className={`h-2 rounded-full ${
                          pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-yellow-500" : "bg-emerald-500"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-400">
                      {spent.toFixed(0)}€ ausgegeben ({pct.toFixed(0)}%)
                    </p>
                  </>
                )}
              </div>
            );
          })}
          {(budgets || []).length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <p className="text-4xl mb-3">🎯</p>
              <p className="mb-2">Noch keine Budgets gesetzt.</p>
              <p className="text-sm">
                Sag: <span className="text-emerald-400 font-mono">&quot;Budget Essen 300€&quot;</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
