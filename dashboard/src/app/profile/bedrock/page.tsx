"use client";

import { useState, useCallback, useEffect } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";
import { Save, RotateCcw, ShieldAlert } from "lucide-react";

const API_URL = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("api_token");
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

type BedrockResponse = {
  bedrock: Record<string, unknown>;
  updated_at: string | null;
  history_count: number;
};

export default function BedrockPage() {
  const [bedrock, setBedrock] = useState<Record<string, unknown>>({});
  const [text, setText] = useState<string>("{}");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [historyCount, setHistoryCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<BedrockResponse>("/api/life-profile/bedrock");
      setBedrock(data.bedrock || {});
      setText(JSON.stringify(data.bedrock || {}, null, 2));
      setUpdatedAt(data.updated_at);
      setHistoryCount(data.history_count);
      setError(null);
    } catch {
      setError("Bedrock konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async () => {
    setError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      setError("JSON ungültig: " + (e instanceof Error ? e.message : String(e)));
      return;
    }
    if (typeof parsed !== "object" || Array.isArray(parsed) || parsed === null) {
      setError("Bedrock muss ein JSON-Objekt sein.");
      return;
    }
    setSaving(true);
    try {
      await apiFetch<{ ok: boolean; updated_at: string; history_count: number }>(
        "/api/life-profile/bedrock",
        { method: "PATCH", body: JSON.stringify({ bedrock: parsed }) },
      );
      await load();
      setSuccessMsg("Bedrock gespeichert. Vorherige Version archiviert.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (e) {
      setError("Speichern fehlgeschlagen: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setText(JSON.stringify(bedrock, null, 2));
    setError(null);
  };

  return (
    <>
      <Header
        title="🪨 Bedrock"
        subtitle="Hand-kuratierte Identität — Lebensbereiche, Hebel, Leitspruch. Geht in jeden AI-Call."
      />
      <div className="p-4 space-y-4">
        {loading && <LoadingSpinner />}

        {!loading && (
          <>
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <ShieldAlert size={18} className="text-amber-400" />
                  <h2 className="text-white font-semibold">JSON-Editor</h2>
                </div>
                <div className="text-xs text-zinc-500 text-right">
                  {updatedAt ? (
                    <>Stand: {new Date(updatedAt).toLocaleString("de-DE")}</>
                  ) : (
                    <>noch nie gespeichert</>
                  )}
                  <br />
                  History-Snapshots: {historyCount}
                </div>
              </div>
              <p className="text-xs text-zinc-500 mb-3">
                Schema: identity, life_areas[], skill_levers[], self_leadership_competencies[],
                leitspruch, strengths[], weaknesses[], bottleneck, language, communication_style.
              </p>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                spellCheck={false}
                className="w-full min-h-[520px] bg-black border border-zinc-800 text-zinc-200 text-xs font-mono rounded-xl p-3 outline-none focus:border-indigo-600"
              />
              <div className="flex gap-2 mt-3">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
                >
                  <Save size={14} />
                  {saving ? "Speichere…" : "Speichern"}
                </button>
                <button
                  onClick={handleReset}
                  disabled={saving}
                  className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-300 rounded-xl px-4 py-2 text-sm font-medium transition-colors"
                >
                  <RotateCcw size={14} />
                  Zurücksetzen
                </button>
              </div>
            </div>

            {successMsg && (
              <div className="bg-green-900/30 border border-green-700 rounded-xl p-3 text-green-300 text-sm">
                ✅ {successMsg}
              </div>
            )}
            {error && (
              <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 text-red-300 text-sm">
                ❌ {error}
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
