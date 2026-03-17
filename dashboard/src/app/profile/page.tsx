"use client";

import { useState, useCallback, useEffect } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";
import { RefreshCw, Brain, Zap, Target } from "lucide-react";

const API_URL = typeof window !== "undefined" ? window.location.origin : "http://localhost:8000";
function getToken() {
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
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

type LifeProfile = {
  id: number;
  summary: string;
  strengths: string[];
  patterns: string[];
  current_focus: string;
  last_updated: string;
  update_count: number;
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<LifeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ profile: LifeProfile | null }>("/api/life-profile");
      setProfile(data.profile);
      setError(null);
    } catch (e) {
      setError("Profil konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRegenerate = async () => {
    setRegenerating(true);
    setSuccessMsg(null);
    try {
      await apiFetch("/api/life-profile/regenerate", { method: "POST" });
      await load();
      setSuccessMsg("Profil wurde erfolgreich aktualisiert!");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (e) {
      setError("Regenerierung fehlgeschlagen.");
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <>
      <Header
        title="🧠 Lebens-Profil"
        subtitle="KI-generiertes Langzeit-Gedächtnis — wird wöchentlich aktualisiert"
      />
      <div className="p-4 space-y-4">
        {loading && <LoadingSpinner />}

        {!loading && !profile && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 text-center">
            <Brain size={40} className="mx-auto text-zinc-600 mb-4" />
            <h2 className="text-white font-semibold mb-2">Noch kein Profil vorhanden</h2>
            <p className="text-zinc-400 text-sm mb-6">
              Das Lebens-Profil wird aus deinen Zielen, Tasks, Reflexionen und Mustern generiert.
              Klicke unten, um dein erstes Profil zu erstellen.
            </p>
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl px-6 py-3 font-semibold text-sm transition-colors flex items-center gap-2 mx-auto"
            >
              <RefreshCw size={16} className={regenerating ? "animate-spin" : ""} />
              {regenerating ? "Generiere Profil…" : "Profil jetzt erstellen"}
            </button>
          </div>
        )}

        {!loading && profile && (
          <>
            {/* Header card */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Brain size={18} className="text-indigo-400" />
                    <h2 className="text-white font-semibold">Lebens-Profil</h2>
                  </div>
                  <p className="text-xs text-zinc-500">
                    Stand: {profile.last_updated ? new Date(profile.last_updated).toLocaleDateString("de-DE", {
                      day: "numeric", month: "long", year: "numeric"
                    }) : "unbekannt"} · Update #{profile.update_count}
                  </p>
                </div>
                <button
                  onClick={handleRegenerate}
                  disabled={regenerating}
                  className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-300 rounded-xl px-3 py-2 text-xs font-medium transition-colors shrink-0"
                >
                  <RefreshCw size={12} className={regenerating ? "animate-spin" : ""} />
                  {regenerating ? "Aktualisiere…" : "Aktualisieren"}
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

            {/* Summary */}
            {profile.summary && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <Brain size={15} className="text-indigo-400" />
                  Profil-Zusammenfassung
                </h3>
                <p className="text-zinc-300 text-sm leading-relaxed whitespace-pre-line">
                  {profile.summary}
                </p>
              </div>
            )}

            {/* Current Focus */}
            {profile.current_focus && (
              <div className="bg-indigo-950/40 border border-indigo-800/50 rounded-2xl p-5">
                <h3 className="text-sm font-semibold text-indigo-300 mb-2 flex items-center gap-2">
                  <Target size={15} />
                  Aktueller Fokus
                </h3>
                <p className="text-white text-sm leading-relaxed">{profile.current_focus}</p>
              </div>
            )}

            {/* Strengths */}
            {profile.strengths && profile.strengths.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <Zap size={15} className="text-yellow-400" />
                  Stärken
                </h3>
                <div className="flex flex-wrap gap-2">
                  {profile.strengths.map((strength, i) => (
                    <span
                      key={i}
                      className="bg-yellow-900/30 border border-yellow-800/40 text-yellow-300 text-xs px-3 py-1.5 rounded-full"
                    >
                      {strength}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Behavioral Patterns */}
            {profile.patterns && profile.patterns.length > 0 && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <RefreshCw size={15} className="text-blue-400" />
                  Verhaltens-Muster
                </h3>
                <ul className="space-y-2">
                  {profile.patterns.map((pattern, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                      <span className="text-blue-400 shrink-0 mt-0.5">•</span>
                      <span>{pattern}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
