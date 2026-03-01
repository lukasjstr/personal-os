"use client";

import { useState, useEffect } from "react";
import Header from "@/components/Header";
import { clearToken, setToken, api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const [token, setTokenInput] = useState("");
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("api_token") ?? "";
    setTokenInput(t);
  }, []);

  const saveToken = () => {
    if (token.trim()) {
      setToken(token.trim());
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  const logout = () => {
    clearToken();
    window.location.reload();
  };

  const checkHealth = async () => {
    setChecking(true);
    try {
      const res = await api.health();
      setHealth(`✅ API erreichbar — ${res.status}`);
    } catch (e) {
      setHealth(`❌ API nicht erreichbar`);
    } finally {
      setChecking(false);
    }
  };

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <div>
      <Header title="⚙️ Einstellungen" />

      <div className="space-y-6 max-w-lg">
        {/* API Token */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-1">🔑 API Token</h2>
          <p className="text-zinc-500 text-sm mb-4">
            Bearer Token für die API-Authentifizierung. Aus dem Telegram Bot via /token Befehl.
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={token}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="API Token..."
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              onClick={saveToken}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                saved ? "bg-green-700 text-white" : "bg-blue-600 hover:bg-blue-700 text-white"
              )}
            >
              {saved ? "✓ Gespeichert" : "Speichern"}
            </button>
          </div>
        </div>

        {/* API Status */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-1">🌐 API Verbindung</h2>
          <p className="text-zinc-500 text-sm mb-3">
            API URL:{" "}
            <code className="bg-zinc-800 px-1.5 py-0.5 rounded text-xs text-zinc-300">
              {apiUrl}
            </code>
          </p>
          <button
            onClick={checkHealth}
            disabled={checking}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {checking ? "Prüfe..." : "Verbindung testen"}
          </button>
          {health && (
            <p className="mt-2 text-sm text-zinc-300">{health}</p>
          )}
        </div>

        {/* About */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-3">ℹ️ Über Personal OS</h2>
          <div className="space-y-1 text-sm text-zinc-400">
            <div className="flex justify-between">
              <span>Version</span>
              <span className="text-zinc-300">2.0.0 (Phase 2)</span>
            </div>
            <div className="flex justify-between">
              <span>Stack</span>
              <span className="text-zinc-300">Next.js 14 + FastAPI</span>
            </div>
            <div className="flex justify-between">
              <span>KI</span>
              <span className="text-zinc-300">GPT-4o</span>
            </div>
          </div>
        </div>

        {/* Logout */}
        <div className="bg-zinc-900 border border-red-900/50 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-1">🚪 Abmelden</h2>
          <p className="text-zinc-500 text-sm mb-4">
            API Token entfernen und zur Login-Seite zurückkehren.
          </p>
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-900 hover:bg-red-800 text-red-300 rounded-lg text-sm transition-colors"
          >
            Abmelden
          </button>
        </div>
      </div>
    </div>
  );
}
