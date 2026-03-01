"use client";

import { useState, useEffect } from "react";
import { hasToken, setToken, validateToken } from "@/lib/api";

interface Props {
  children: React.ReactNode;
}

function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.869 4.326-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.829.941z" />
    </svg>
  );
}

export default function TokenGate({ children }: Props) {
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setAuthed(hasToken());
    setChecked(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = input.trim();
    if (!token) {
      setError("Bitte API Token eingeben");
      return;
    }
    setLoading(true);
    setError("");
    const valid = await validateToken(token);
    setLoading(false);
    if (valid) {
      setToken(token);
      setAuthed(true);
    } else {
      setError("Ungültiger Token. Bitte nochmal versuchen.");
    }
  };

  if (!checked) return null;
  if (authed) return <>{children}</>;

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 mb-4">
            <span className="text-3xl">🤖</span>
          </div>
          <h1 className="text-white text-2xl font-bold">Personal OS</h1>
          <p className="text-zinc-400 text-sm mt-1">Dein persönlicher COO</p>
        </div>

        {/* Instruction card */}
        <div className="bg-[#229ED9]/10 border border-[#229ED9]/30 rounded-xl p-4 mb-6 flex items-start gap-3">
          <TelegramIcon className="w-5 h-5 text-[#229ED9] shrink-0 mt-0.5" />
          <div>
            <p className="text-white text-sm font-medium">Token via Telegram holen</p>
            <p className="text-zinc-400 text-xs mt-0.5">
              Schreib{" "}
              <code className="bg-zinc-800 text-[#229ED9] px-1.5 py-0.5 rounded font-mono text-xs">/token</code>
              {" "}an{" "}
              <span className="text-[#229ED9] font-medium">@PersonalOperatingSystem_Bot</span>
              {" "}auf Telegram
            </p>
          </div>
        </div>

        {/* Login form */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-zinc-300 text-xs font-medium mb-1.5">
                API Token
              </label>
              <input
                type="password"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Füge deinen Token hier ein..."
                autoComplete="off"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors placeholder:text-zinc-600"
              />
            </div>
            {error && (
              <div className="flex items-center gap-2 text-red-400 text-xs bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
                <span>⚠️</span> {error}
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg py-2.5 text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Prüfe Token...
                </>
              ) : (
                "Verbinden"
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
