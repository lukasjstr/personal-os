"use client";

import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import { useShopping } from "@/hooks/useApi";

export default function ShoppingPage() {
  const { data, error, isLoading } = useShopping();

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const items = data?.items ?? [];

  return (
    <div>
      <Header title="🛒 Einkaufsliste" subtitle={`${items.length} Items`} />

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        {items.length === 0 ? (
          <EmptyState emoji="🛒" message="Einkaufsliste ist leer — per Telegram hinzufügen!" />
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 py-2.5 border-b border-zinc-800 last:border-0"
              >
                <span className="text-xl">🛍️</span>
                <div className="flex-1">
                  <div className="text-white">{item.title}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <p className="text-zinc-600 text-xs text-center mt-4">
        Artikel per Telegram hinzufügen: &ldquo;kauf [Artikel]&rdquo;
      </p>
    </div>
  );
}
