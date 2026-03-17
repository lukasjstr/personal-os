"use client";

import { useState, useCallback, useEffect } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { useShopping, useShoppingDefaults } from "@/hooks/useApi";
import { api } from "@/lib/api";
import type { ShoppingDefault, Task } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Plus, Trash2, ToggleLeft, ToggleRight, CheckCircle2, Package, Star, ShoppingBag } from "lucide-react";

// ─── Category config ──────────────────────────────────────────────────────────

const CATEGORY_EMOJIS: Record<string, string> = {
  Gemüse: "🥬",
  Fleisch: "🥩",
  Basics: "🥫",
  Haushalt: "🧴",
  Milchprodukte: "🥛",
  Obst: "🍎",
  Getränke: "🥤",
  Sonstiges: "⭐",
};

const CATEGORY_COLORS: Record<string, string> = {
  Gemüse: "bg-green-900/40 text-green-400 border-green-800/50",
  Fleisch: "bg-red-900/40 text-red-400 border-red-800/50",
  Basics: "bg-yellow-900/40 text-yellow-400 border-yellow-800/50",
  Haushalt: "bg-blue-900/40 text-blue-400 border-blue-800/50",
  Milchprodukte: "bg-sky-900/40 text-sky-400 border-sky-800/50",
  Obst: "bg-orange-900/40 text-orange-400 border-orange-800/50",
  Getränke: "bg-purple-900/40 text-purple-400 border-purple-800/50",
};

function getCategoryEmoji(category: string | null): string {
  if (!category) return "⭐";
  return CATEGORY_EMOJIS[category] ?? "⭐";
}

function getCategoryStyle(category: string | null): string {
  if (!category) return "bg-zinc-800 text-zinc-400 border-zinc-700";
  return CATEGORY_COLORS[category] ?? "bg-zinc-800 text-zinc-400 border-zinc-700";
}

// ─── Tab type ─────────────────────────────────────────────────────────────────

type TabId = "jetzt" | "regulaer" | "besorgungen";

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ShoppingPage() {
  const [activeTab, setActiveTab] = useState<TabId>("jetzt");
  const [newItem, setNewItem] = useState("");
  const [addingItem, setAddingItem] = useState(false);
  const [completing, setCompleting] = useState<number | null>(null);
  const [loadingDefaults, setLoadingDefaults] = useState(false);
  const [savingToDefault, setSavingToDefault] = useState<number | null>(null);
  const [deletingDefault, setDeletingDefault] = useState<ShoppingDefault | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [addingDefaultToList, setAddingDefaultToList] = useState<number | null>(null);
  const [errands, setErrands] = useState<Task[]>([]);
  const [errandsLoading, setErrandsLoading] = useState(true);
  const [completingErrand, setCompletingErrand] = useState<number | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const {
    data: shoppingData,
    error: shoppingError,
    isLoading: shoppingLoading,
    mutate: mutateShopping,
  } = useShopping();
  const {
    data: defaultsData,
    isLoading: defaultsLoading,
    mutate: mutateDefaults,
  } = useShoppingDefaults();

  // Load errands
  useEffect(() => {
    setErrandsLoading(true);
    api.tasksByCategory("errand")
      .then((res) => setErrands(res.tasks ?? []))
      .catch(() => setErrands([]))
      .finally(() => setErrandsLoading(false));
  }, []);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleAddItem = useCallback(async () => {
    const title = newItem.trim();
    if (!title) return;
    setAddingItem(true);
    try {
      await api.createTask({ title, category: "shopping" });
      await mutateShopping();
      setNewItem("");
      addToast("Item hinzugefügt ✅", "success");
    } catch {
      addToast("Fehler beim Hinzufügen", "error");
    } finally {
      setAddingItem(false);
    }
  }, [newItem, mutateShopping, addToast]);

  const handleComplete = useCallback(
    async (itemId: number) => {
      setCompleting(itemId);
      mutateShopping(
        (prev) => (prev ? { items: prev.items.filter((i) => i.id !== itemId) } : prev),
        false
      );
      try {
        await api.completeTask(itemId);
        addToast("Erledigt ✅", "success");
      } catch {
        await mutateShopping();
        addToast("Fehler beim Abhaken", "error");
      } finally {
        setCompleting(null);
      }
    },
    [mutateShopping, addToast]
  );

  const handleCompleteErrand = useCallback(async (taskId: number) => {
    setCompletingErrand(taskId);
    setErrands((prev) => prev.filter((t) => t.id !== taskId));
    try {
      await api.completeTask(taskId);
      addToast("Besorgt ✅", "success");
    } catch {
      const res = await api.tasksByCategory("errand");
      setErrands(res.tasks ?? []);
      addToast("Fehler beim Abhaken", "error");
    } finally {
      setCompletingErrand(null);
    }
  }, [addToast]);

  const handleLoadDefaults = useCallback(async () => {
    setLoadingDefaults(true);
    try {
      const res = await api.loadShoppingDefaults();
      await mutateShopping();
      addToast(
        res.added === 0
          ? "Alle Standard-Items bereits auf der Liste"
          : `${res.added} Items hinzugefügt 🛒`,
        "success"
      );
    } catch {
      addToast("Fehler beim Laden", "error");
    } finally {
      setLoadingDefaults(false);
    }
  }, [mutateShopping, addToast]);

  const handleSaveAsDefault = useCallback(
    async (item: { id: number; title: string }) => {
      setSavingToDefault(item.id);
      try {
        await api.createShoppingDefault({ title: item.title });
        await mutateDefaults();
        addToast(`"${item.title}" als Standard gespeichert ⭐`, "success");
      } catch {
        addToast("Fehler beim Speichern", "error");
      } finally {
        setSavingToDefault(null);
      }
    },
    [mutateDefaults, addToast]
  );

  const handleAddDefaultToList = useCallback(
    async (def: ShoppingDefault) => {
      setAddingDefaultToList(def.id);
      try {
        await api.createTask({ title: def.title, category: "shopping" });
        await mutateShopping();
        addToast(`"${def.title}" zur Liste hinzugefügt`, "success");
      } catch {
        addToast("Fehler", "error");
      } finally {
        setAddingDefaultToList(null);
      }
    },
    [mutateShopping, addToast]
  );

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
      addToast("Aus Standards entfernt", "success");
      setDeletingDefault(null);
    } catch {
      await mutateDefaults();
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeleting(false);
    }
  }, [deletingDefault, mutateDefaults, addToast]);

  // ── Derived data ──────────────────────────────────────────────────────────

  const items = shoppingData?.items ?? [];
  const defaults = (defaultsData?.defaults ?? []).filter((d) => d.active);
  const defaultsByCategory = defaults.reduce<Record<string, ShoppingDefault[]>>((acc, d) => {
    const key = d.category ?? "Sonstiges";
    if (!acc[key]) acc[key] = [];
    acc[key].push(d);
    return acc;
  }, {});
  const activeErrands = errands.filter((t) => t.status !== "done");

  const tabs: { id: TabId; label: string; emoji: string; count: number }[] = [
    { id: "jetzt", label: "Jetzt kaufen", emoji: "🛍️", count: items.length },
    { id: "regulaer", label: "Regelmäßig", emoji: "⭐", count: defaults.length },
    { id: "besorgungen", label: "Aufgaben", emoji: "📦", count: activeErrands.length },
  ];

  if (shoppingLoading || defaultsLoading) return <LoadingSpinner />;

  return (
    <div>
      <Header
        title="🛒 Einkaufen"
        subtitle={`${items.length} aktiv · ${defaults.length} Standards · ${activeErrands.length} Besorgungen`}
      />

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-zinc-900 border border-zinc-800 rounded-xl p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "bg-indigo-600 text-white"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800"
            )}
          >
            <span>{tab.emoji}</span>
            <span className="hidden sm:inline">{tab.label}</span>
            {tab.count > 0 && (
              <span
                className={cn(
                  "text-xs px-1.5 py-0.5 rounded-full font-medium",
                  activeTab === tab.id ? "bg-white/20" : "bg-zinc-700 text-zinc-300"
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab A: Jetzt kaufen ── */}
      {activeTab === "jetzt" && (
        <div className="space-y-4">
          {/* Quick-add input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddItem()}
              placeholder="Item hinzufügen…"
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={handleAddItem}
              disabled={addingItem || !newItem.trim()}
              className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-sm font-medium transition-colors flex items-center gap-1.5"
            >
              <Plus size={16} />
              <span className="hidden sm:inline">Hinzufügen</span>
            </button>
          </div>

          {/* Load defaults shortcut */}
          {defaults.length > 0 && (
            <button
              onClick={handleLoadDefaults}
              disabled={loadingDefaults}
              className="w-full py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-zinc-400 hover:text-white hover:border-zinc-600 transition-colors text-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loadingDefaults ? (
                "⏳ Lade…"
              ) : (
                <>
                  <Star size={14} />
                  Standard-Liste laden ({defaults.length} Items)
                </>
              )}
            </button>
          )}

          {/* Current items */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800">
              <h2 className="text-white font-semibold text-sm flex items-center gap-2">
                <ShoppingBag size={15} className="text-indigo-400" />
                Aktuelle Liste
                {items.length > 0 && (
                  <span className="text-zinc-500 font-normal text-xs">({items.length})</span>
                )}
              </h2>
            </div>
            {items.length === 0 ? (
              <div className="px-5 py-8">
                <EmptyState emoji="✅" message="Einkaufsliste ist leer!" />
              </div>
            ) : (
              <div className="divide-y divide-zinc-800/60">
                {items.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 px-5 py-3 group hover:bg-zinc-800/30 transition-colors"
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
                      title="Als erledigt markieren"
                    >
                      {completing === item.id && (
                        <div className="w-2.5 h-2.5 rounded-full bg-zinc-500" />
                      )}
                    </button>
                    <div className="flex-1 text-white text-sm">{item.title}</div>
                    {/* Save as default */}
                    <button
                      onClick={() => handleSaveAsDefault(item)}
                      disabled={savingToDefault === item.id}
                      className="text-zinc-600 hover:text-yellow-400 transition-colors p-1 rounded opacity-0 group-hover:opacity-100"
                      title="Als Standard speichern"
                    >
                      <Star size={13} />
                    </button>
                    {/* Complete button */}
                    <button
                      onClick={() => handleComplete(item.id)}
                      disabled={completing === item.id}
                      className="shrink-0 px-3 py-1 bg-green-900/40 hover:bg-green-900/70 border border-green-800/50 text-green-400 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      Erledigt
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Tab B: Regelmäßig ── */}
      {activeTab === "regulaer" && (
        <div className="space-y-4">
          <p className="text-zinc-500 text-sm">
            Artikel die du regelmäßig kaufst. Toggle zum Hinzufügen zur aktuellen Liste.
          </p>

          {defaults.length === 0 ? (
            <EmptyState emoji="⭐" message="Noch keine Standard-Artikel. Füge ein Item aus der aktuellen Liste hinzu!" />
          ) : (
            <div className="space-y-4">
              {Object.entries(defaultsByCategory).map(([category, catDefaults]) => (
                <div key={category} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                  <div className="px-5 py-3 border-b border-zinc-800 flex items-center gap-2">
                    <span className="text-base">{getCategoryEmoji(category === "Sonstiges" ? null : category)}</span>
                    <h3 className="text-zinc-300 text-sm font-medium">{category}</h3>
                    <span
                      className={cn(
                        "text-xs px-1.5 py-0.5 rounded border",
                        getCategoryStyle(category === "Sonstiges" ? null : category)
                      )}
                    >
                      {catDefaults.length}
                    </span>
                  </div>
                  <div className="divide-y divide-zinc-800/60">
                    {catDefaults.map((d) => (
                      <div
                        key={d.id}
                        className="flex items-center gap-3 px-5 py-3 group hover:bg-zinc-800/20 transition-colors"
                      >
                        <span className="text-yellow-400 text-sm shrink-0">⭐</span>
                        <div className="flex-1 text-white text-sm">{d.title}</div>
                        {/* Toggle to add to current list */}
                        <button
                          onClick={() => handleAddDefaultToList(d)}
                          disabled={addingDefaultToList === d.id}
                          className={cn(
                            "shrink-0 px-3 py-1 rounded-lg text-xs font-medium transition-colors border disabled:opacity-50",
                            "bg-indigo-900/30 border-indigo-700/50 text-indigo-400 hover:bg-indigo-900/60"
                          )}
                          title="Zur Einkaufsliste hinzufügen"
                        >
                          {addingDefaultToList === d.id ? (
                            <ToggleRight size={14} className="animate-pulse" />
                          ) : (
                            "+ Liste"
                          )}
                        </button>
                        {/* Delete from defaults */}
                        <button
                          onClick={() => setDeletingDefault(d)}
                          className="text-zinc-600 hover:text-red-400 transition-colors p-1 rounded opacity-0 group-hover:opacity-100"
                          title="Aus Standards entfernen"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab C: Aufgaben & Besorgungen ── */}
      {activeTab === "besorgungen" && (
        <div className="space-y-4">
          <p className="text-zinc-500 text-sm">
            Nicht-Food Besorgungen und Einkaufs-Aufgaben (Kategorie: errand).
          </p>

          {errandsLoading ? (
            <LoadingSpinner />
          ) : activeErrands.length === 0 ? (
            <EmptyState emoji="📦" message="Keine offenen Besorgungen!" />
          ) : (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-zinc-800">
                <h2 className="text-white font-semibold text-sm flex items-center gap-2">
                  <Package size={15} className="text-zinc-400" />
                  Besorgungen & Aufgaben
                  <span className="text-zinc-500 font-normal text-xs">({activeErrands.length})</span>
                </h2>
              </div>
              <div className="divide-y divide-zinc-800/60">
                {activeErrands.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center gap-3 px-5 py-3 group hover:bg-zinc-800/30 transition-colors"
                  >
                    <CheckCircle2
                      size={16}
                      className="text-zinc-600 shrink-0"
                    />
                    <div className="flex-1">
                      <div className="text-white text-sm">{task.title}</div>
                      {task.description && (
                        <div className="text-zinc-500 text-xs mt-0.5">{task.description}</div>
                      )}
                    </div>
                    {task.due_date && (
                      <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full border shrink-0",
                        task.is_overdue
                          ? "bg-red-900/40 text-red-400 border-red-800/50"
                          : "bg-zinc-800 text-zinc-400 border-zinc-700"
                      )}>
                        {task.due_date}
                      </span>
                    )}
                    <button
                      onClick={() => handleCompleteErrand(task.id)}
                      disabled={completingErrand === task.id}
                      className="shrink-0 px-3 py-1 bg-green-900/40 hover:bg-green-900/70 border border-green-800/50 text-green-400 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      Erledigt
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

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
