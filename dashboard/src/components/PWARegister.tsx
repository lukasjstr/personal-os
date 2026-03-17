"use client";

import { useEffect } from "react";

export default function PWARegister() {
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => {
          console.log("[PWA] Service worker registered:", reg.scope);
        })
        .catch((err) => {
          console.warn("[PWA] Service worker registration failed:", err);
        });
    }
  }, []);

  return null;
}
