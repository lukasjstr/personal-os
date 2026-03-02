"use client";

import { useState, useCallback } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useShopping, useShoppingDefaults } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { ShoppingDefault } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Trash2 } from "lucide-react";

// ─── Category config ──────────────────────────────────────────────────────────

const CATEGORY_EMOJIS: Record<string, string> = {
  Gemüse: "🥬",
  Fleisch: "🥩",
  Basics: "🥫",
  Haushalt: "🧴",
  Milchprodukte: "🥛",
  Obst: "🍎",
  Getränke: "🥤",
};

function getCategoryEmoji(category: string | null): string {
  if (!category) return "⭐";
  return CATEGORY_EMOJIS[category] ?? "⭐";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ShoppingPage() {
  const {
    data: shoppingData,
    error: shoppingError,
    isLoading: shoppingLoading,
    mutate: mutateShopping,
  } = useShopping();
  const {
    data: defaultsData,
    error: defaultsError,
    isLoading: defaultsLoading,
    mutate: mutateDefaults,
  } = useShoppingDefaults();

  const [completing, setCompleting] = useState<number | null>(null);
  const [loadingDefaults, setLoadingDefaults] = useState(false);
  const [deletingDefault, setDeletingDefault] = useState<ShoppingDefault | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { toasts, addToast, dismissToast } = useToast();

  const handleComplete = useCallback(
    async (itemId: number) => {
      setCompleting(itemId);
      mutateShopping(
        (prev) => (prev ? { items: prev.items.filter((i) => i.id !== itemId) } : prev),
        false
      );
      try {
        await api.completeTask(itemId);
        addToast("Item abgehakt ✅", "success");
      } catch {
        await mutateShopping();
        addToast("Fehler beim Abhaken", "error");
      } finally {
        setCompleting(null);
      }
    },
    [mutateShopping, addToast]
  );

  const handleLoadDefaults = useCallback(async () => {
    setLoadingDefaults(true);
    try {
      const res = await api.loadShoppingDefaults();
      await mutateShopping();
      if (res.added === 0) {
        addToast("Alle Standard-Items bereits auf der Liste", "success");
      } else {
        addToast(`${res.added} Standard-Items hinzugefügt 🛒`, "success");
      }
    } catch {
      addToast("Fehler beim Laden der Standard-Liste", "error");
    } finally {
      setLoadingDefaults(false);
    }
  }, [mutateShopping, addToast]);

  const handleDeleteDefault = useCallback(async () => {
    if (!deletingDefault) return;
    setDeleting(true);
    mutateDefaults(
      (prev) =>
        prev ? { defaults: prev.defaults.filter((d) => d.id !== deletingDefault.id) } : prev,
      false
    );
    try {
      await api.deleteShoppingDefault(deletingDefault.id);
      addToast("Standard-Item gelöscht", "success");
      setDeletingDefault(null);
    } catch {
      await mutateDefaults();
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
    }
  }, [deletingDefault, mutateDefaults, addToast]);

  if (shoppingLoading || defaultsLoading) return <LoadingSpinner />;
  if (shoppingError || defaultsError)
    return <ErrorState message={(shoppingError ?? defaultsError).message} />;

  const items = shoppingData?.items ?? [];
  const defaults = defaultsData?.defaults ?? [];
  const activeDefaults = defaults.filter((d) => d.active);

  // Group defaults by category
  const defaultsByCategory = activeDefaults.reduce<Record<string, ShoppingDefault[]>>(
    (acc, d) => {
      const key = d.category ?? "Sonstiges";
      if (!acc[key]) acc[key] = [];
      acc[key].push(d);
      return acc;
    },
    {}
  );

  return (
    <div>
      <Header
        title="🛒 Einkaufsliste"
        subtitle={`${items.length} Items${activeDefaults.length > 0 ? ` · ${activeDefaults.length} Standard-Artikel` : ""}`}
      />

      {/* Load Defaults Button */}
      {activeDefaults.length > 0 && (
        <div className="mb-6">
          <button
            onClick={handleLoadDefaults}
            disabled={loadingDefaults}
            className="w-full py-3 rounded-xl bg-blue-900/40 border border-blue-700/50 text-blue-300 hover:bg-blue-900/60 transition-colors font-medium text-sm flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loadingDefaults ? (
              <>⏳ Lade Standard-Liste…</>
            ) : (
              <>⭐ Standard-Liste laden ({activeDefaults.length} Items)</>
            )}
          </button>
        </div>
      )}

      {/* Current Shopping Items */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
        <h2 className="text-white font-semibold mb-3 text-sm">🛍️ Aktuelle Einkaufsliste</h2>
        {items.length === 0 ? (
          <EmptyState emoji="✅" message="Einkaufsliste ist leer!" />
        ) : (
          <div className="space-y-1">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 py-2.5 px-1 border-b border-zinc-800 last:border-0"
              >
                <button
                  onClick={() => handleComplete(item.id)}
                  disabled={completing === item.id}
                  className={cn(
                    "shrink-0 w-7 h-7 rounded-lg border-2 flex items-center justify-center transition-all",
                    completing === item.id
                      ? "border-zinc-600 bg-zinc-800 animate-pulse"
                      : "border-zinc-600 bg-zinc-800 hover:border-green-500 hover:bg-green-950/40 cursor-pointer"
                  )}
                  title="Als gekauft markieren"
                >
                  {completing === item.id && (
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-500" />
                  )}
                </button>
                <div className="flex-1 text-white text-sm">{item.title}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Shopping Defaults by Category */}
      {Object.keys(defaultsByCategory).length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-4 text-sm flex items-center gap-2">
            ⭐ Standard-Artikel
            <span className="text-zinc-500 font-normal text-xs">({activeDefaults.length})</span>
          </h2>
          <div className="space-y-5">
            {Object.entries(defaultsByCategory).map(([category, catDefaults]) => (
              <div key={category}>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-base">
                    {getCategoryEmoji(category === "Sonstiges" ? null : category)}
                  </span>
                  <h3 className="text-zinc-400 text-xs font-medium uppercase tracking-wider">
                    {category}
                  </h3>
                </div>
                <div className="space-y-1.5">
                  {catDefaults.map((d) => (
                    <div
                      key={d.id}
                      className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-800/40 border border-zinc-800 group"
                    >
                      <span className="text-yellow-400 text-sm shrink-0">⭐</span>
                      <div className="flex-1 text-white text-sm">{d.title}</div>
                      <button
                        onClick={() => setDeletingDefault(d)}
                        className="text-zinc-600 hover:text-red-400 transition-colors p-1 rounded opacity-0 group-hover:opacity-100"
                        title="Aus Standard-Liste entfernen"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {items.length === 0 && activeDefaults.length === 0 && (
        <EmptyState emoji="🛒" message="Keine Einkaufsitems — per Telegram hinzufügen!" />
      )}

      <p className="text-zinc-600 text-xs text-center mt-4">
        Items per Telegram: &ldquo;Milch kaufen&rdquo; · Standard: &ldquo;Milch ist immer auf meiner Liste&rdquo;
      </p>

      <ConfirmDialog
        open={!!deletingDefault}
        title="Standard-Item löschen?"
        message={`"${deletingDefault?.title}" wird aus den Standard-Artikeln entfernt.`}
        loading={deleting}
        onConfirm={handleDeleteDefault}
        onCancel={() => setDeletingDefault(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
