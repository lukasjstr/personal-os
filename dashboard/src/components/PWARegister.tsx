"use client";

import { useEffect } from "react";
import { api } from "@/lib/api";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

async function subscribeToPush(registration: ServiceWorkerRegistration) {
  try {
    // Check if already subscribed
    const existing = await registration.pushManager.getSubscription();
    if (existing) {
      console.log("[PWA] Already subscribed to push");
      return;
    }

    // Get VAPID public key from server
    const { publicKey } = await api.vapidKey();
    if (!publicKey) {
      console.log("[PWA] No VAPID key configured on server");
      return;
    }

    // Subscribe
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
    });

    // Send subscription to server
    const subJson = subscription.toJSON();
    await api.pushSubscribe({
      endpoint: subJson.endpoint!,
      keys: subJson.keys as Record<string, string>,
    });

    console.log("[PWA] Push subscription registered");
  } catch (err) {
    console.warn("[PWA] Push subscription failed:", err);
  }
}

export default function PWARegister() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;

    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        console.log("[PWA] Service worker registered:", reg.scope);

        // Auto-subscribe if permission already granted
        if (Notification.permission === "granted") {
          subscribeToPush(reg);
        }
      })
      .catch((err) => {
        console.warn("[PWA] Service worker registration failed:", err);
      });
  }, []);

  return null;
}

export { subscribeToPush };
