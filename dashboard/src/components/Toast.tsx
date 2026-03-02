"use client";

import { useState, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";

export interface ToastItem {
  id: string;
  message: string;
  type: "success" | "error";
}

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast.id), 3500);
    return () => clearTimeout(t);
  }, [toast.id, onDismiss]);

  return (
    <div
      onClick={() => onDismiss(toast.id)}
      className={cn(
        "flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-lg border text-sm cursor-pointer",
        toast.type === "success"
          ? "bg-zinc-900 border-green-800 text-green-300"
          : "bg-zinc-900 border-red-800 text-red-300"
      )}
    >
      <span className="font-bold">{toast.type === "success" ? "✓" : "✕"}</span>
      <span>{toast.message}</span>
    </div>
  );
}

export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback(
    (message: string, type: "success" | "error" = "success") => {
      const id = Math.random().toString(36).slice(2);
      setToasts((prev) => [...prev, { id, message, type }]);
    },
    []
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, addToast, dismissToast };
}
