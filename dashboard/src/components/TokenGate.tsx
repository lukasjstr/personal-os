"use client";

import { useState, useEffect } from "react";
import { hasToken, setToken } from "@/lib/api";

interface Props {
  children: React.ReactNode;
}

export default function TokenGate({ children }: Props) {
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setAuthed(hasToken());
    setChecked(true);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) {
      setError("Bitte API Token eingeben");
      return;
    }
    setToken(input.trim());
    setAuthed(true);
    setError("");
  };

  if (!checked) return null;

  if (authed) return <>{children}</>;

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="text-5xl mb-3">🤖</div>
          <h1 className="text-white text-xl font-bold">Personal OS</h1>
          <p className="text-zinc-400 text-sm mt-1">API Token eingeben</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-zinc-400 text-xs mb-1.5">API Token</label>
            <input
              type="password"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Bearer Token aus dem Telegram Bot"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 text-sm font-medium transition-colors"
          >
            Einloggen
          </button>
        </form>

        <p className="text-zinc-600 text-xs text-center mt-4">
          Token via Telegram: /token
        </p>
      </div>
    </div>
  );
}
