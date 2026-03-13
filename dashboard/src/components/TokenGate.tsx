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
  const [showForceSave, setShowForceSave] = useState(false);

  useEffect(() => {
    const check = async () => {
      if (!hasToken()) {
        setAuthed(false);
        setChecked(true);
        return;
      }
      // Validate stored token against the server
      const storedToken = localStorage.getItem("api_token") ?? "";
      const valid = await validateToken(storedToken).catch(() => false);
      if (!valid) {
        // Token is stale — clear it so user is prompted to re-enter
        localStorage.removeItem("api_token");
        setAuthed(false);
      } else {
        setAuthed(true);
      }
      setChecked(true);
    };
    check();
  }, []);

  const cleanToken = (raw: string) =>
    raw
      .trim()
      .replace(/[\u200B-\u200D\uFEFF]/g, "")
      .replace(/[“”]/g, '"')
      .replace(/[‘’]/g, "'")
      .replace(/^['"`]+|['"`]+$/g, "");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = cleanToken(input);
    setInput(token);
    setShowForceSave(false);
    if (!token) {
      setError("Bitte Token eingeben");
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
      setError("Token konnte nicht verifiziert werden. Wenn du sicher bist, dass er korrekt ist, speichere ihn trotzdem.");
      setShowForceSave(true);
    }
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setInput(text.trim());
    } catch {
      // clipboard not available
    }
  };

  if (!checked) return null;
  if (authed) return <>{children}</>;

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600 to-blue-800 mb-4 shadow-xl shadow-blue-900/30">
            <span className="text-4xl">🤖</span>
          </div>
          <h1 className="text-white text-2xl font-bold">Personal OS</h1>
          <p className="text-zinc-400 text-sm mt-1">Verbinde dein Dashboard</p>
        </div>

        {/* Steps */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 mb-4">
          <div className="text-zinc-400 text-xs font-medium uppercase tracking-wider mb-3">
            So geht&apos;s
          </div>
          <div className="space-y-3">
            {[
              {
                step: "1",
                icon: <TelegramIcon className="w-4 h-4 text-[#229ED9]" />,
                text: (
                  <>
                    Öffne{" "}
                    <span className="text-[#229ED9] font-medium">
                      @PersonalOperatingSystem_Bot
                    </span>{" "}
                    auf Telegram
                  </>
                ),
              },
              {
                step: "2",
                icon: <span className="text-sm">💬</span>,
                text: (
                  <>
                    Schreib{" "}
                    <code className="bg-zinc-800 text-[#229ED9] px-1.5 py-0.5 rounded font-mono text-xs">
                      /token
                    </code>
                  </>
                ),
              },
              {
                step: "3",
                icon: <span className="text-sm">📋</span>,
                text: "Füge den Token unten ein und klick Verbinden",
              },
            ].map(({ step, icon, text }) => (
              <div key={step} className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 mt-0.5">
                  <span className="text-zinc-400 text-xs font-bold">{step}</span>
                </div>
                <div className="flex items-center gap-2 flex-1">
                  <span className="shrink-0">{icon}</span>
                  <span className="text-zinc-300 text-sm">{text}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Login form */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-zinc-300 text-xs font-medium mb-2">
                API Token
              </label>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Token hier einfügen..."
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3.5 text-white text-base focus:outline-none focus:border-blue-500 transition-colors placeholder:text-zinc-600 font-mono"
              />
              <button
                type="button"
                onClick={handlePaste}
                className="mt-2 w-full flex items-center justify-center gap-2 px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-700 active:bg-zinc-600 transition-colors text-sm font-medium"
              >
                <span>📋</span>
                <span>Einfügen</span>
              </button>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-xs bg-red-950/50 border border-red-800/40 rounded-lg px-3 py-2">
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg py-2.5 text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Prüfe Token...
                </>
              ) : (
                "Verbinden →"
              )}
            </button>

            {showForceSave && (
              <button
                type="button"
                onClick={() => {
                  const token = cleanToken(input);
                  if (!token) return;
                  setToken(token);
                  setAuthed(true);
                }}
                className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg py-2.5 text-sm font-medium transition-colors"
              >
                Trotzdem speichern
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
