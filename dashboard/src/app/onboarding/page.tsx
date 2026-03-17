"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ChevronRight, Check } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Area {
  id: string;
  emoji: string;
  label: string;
}

interface SuggestedGoal {
  area: string;
  goals: string[];
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const AREAS: Area[] = [
  { id: "fitness", emoji: "💪", label: "Fitness & Körper" },
  { id: "learning", emoji: "🧠", label: "Lernen & Wachstum" },
  { id: "finance", emoji: "💰", label: "Finanzen" },
  { id: "relationships", emoji: "🤝", label: "Beziehungen" },
  { id: "health", emoji: "🧘", label: "Gesundheit" },
  { id: "productivity", emoji: "⚡", label: "Produktivität" },
  { id: "personal", emoji: "🎯", label: "Persönlichkeit" },
];

const GOAL_SUGGESTIONS: SuggestedGoal[] = [
  { area: "fitness", goals: ["Körperkraft aufbauen", "Ausdauer verbessern", "10 kg abnehmen"] },
  { area: "learning", goals: ["Neue Programmiersprache lernen", "Buch pro Monat lesen", "Online-Kurs abschließen"] },
  { area: "finance", goals: ["Notgroschen aufbauen", "Investmentstrategie entwickeln", "Schulden abbauen"] },
  { area: "relationships", goals: ["Freundschaften pflegen", "Netzwerk ausbauen", "Mehr Zeit mit Familie"] },
  { area: "health", goals: ["Stressreduktion", "Besser schlafen", "Gesünder ernähren"] },
  { area: "productivity", goals: ["Morning Routine aufbauen", "Deep Work Gewohnheit", "Inbox Zero erreichen"] },
  { area: "personal", goals: ["Selbstvertrauen stärken", "Neue Gewohnheit etablieren", "Komfortzone erweitern"] },
];

const MORNING_ROUTINES = [
  { id: "frueh_aufstehen", emoji: "☀️", label: "Früh aufstehen" },
  { id: "journaling", emoji: "📖", label: "Journaling" },
  { id: "meditation", emoji: "🧘", label: "Meditation" },
  { id: "sport", emoji: "🏃", label: "Sport" },
  { id: "gesundes_fruehstueck", emoji: "🥗", label: "Gesundes Frühstück" },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const totalSteps = 5;

  // Form state
  const [name, setName] = useState("");
  const [selectedAreas, setSelectedAreas] = useState<string[]>([]);
  const [selectedGoal, setSelectedGoal] = useState<string | null>(null);
  const [customGoal, setCustomGoal] = useState("");
  const [wakeupTime, setWakeupTime] = useState("07:00");
  const [selectedRoutines, setSelectedRoutines] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Derived: suggested goals based on selected areas
  const suggestedGoals = GOAL_SUGGESTIONS.filter((s) =>
    selectedAreas.includes(s.area)
  ).flatMap((s) => s.goals).slice(0, 6);

  const toggleArea = (id: string) => {
    setSelectedAreas((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
    // Reset goal when areas change
    setSelectedGoal(null);
    setCustomGoal("");
  };

  const toggleRoutine = (id: string) => {
    setSelectedRoutines((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    );
  };

  const canProceed = () => {
    if (step === 1) return true;
    if (step === 2) return selectedAreas.length > 0;
    if (step === 3) return !!(selectedGoal || customGoal.trim());
    if (step === 4) return true;
    return true;
  };

  const handleNext = () => {
    if (step < totalSteps) setStep((s) => s + 1);
  };

  const handleBack = () => {
    if (step > 1) setStep((s) => s - 1);
  };

  const handleFinish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.completeOnboarding({
        name: name.trim() || undefined,
        selected_areas: selectedAreas,
        first_goal: selectedGoal || customGoal.trim() || null,
        wakeup_time: wakeupTime,
        morning_routines: selectedRoutines,
      });
      router.push("/");
    } catch (e) {
      setError("Fehler beim Speichern. Bitte erneut versuchen.");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-zinc-500 text-xs">Schritt {step} von {totalSteps}</span>
            <span className="text-zinc-500 text-xs">{Math.round((step / totalSteps) * 100)}%</span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-500"
              style={{ width: `${(step / totalSteps) * 100}%` }}
            />
          </div>
          <div className="flex gap-1 mt-2">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <div
                key={i}
                className={cn(
                  "flex-1 h-0.5 rounded-full transition-colors",
                  i < step ? "bg-indigo-500" : "bg-zinc-800"
                )}
              />
            ))}
          </div>
        </div>

        {/* Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl">

          {/* ── Step 1: Willkommen ── */}
          {step === 1 && (
            <div className="text-center">
              <div className="text-6xl mb-6">🤖</div>
              <h1 className="text-2xl font-bold text-white mb-3">
                Willkommen bei Personal OS
              </h1>
              <p className="text-zinc-400 mb-8">
                Dein persönlicher KI-COO richtet sich jetzt für dich ein.
                Nur 5 kurze Schritte.
              </p>
              <div className="mb-8">
                <label className="text-zinc-400 text-sm mb-2 block text-left">
                  Wie heißt du?
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Dein Name"
                  autoFocus
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-base placeholder-zinc-500 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
            </div>
          )}

          {/* ── Step 2: Lebensbereiche ── */}
          {step === 2 && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Lebensbereiche</h2>
              <p className="text-zinc-400 text-sm mb-6">
                Welche Bereiche willst du verbessern? Wähle alle die zutreffen.
              </p>
              <div className="grid grid-cols-2 gap-3">
                {AREAS.map((area) => {
                  const selected = selectedAreas.includes(area.id);
                  return (
                    <button
                      key={area.id}
                      onClick={() => toggleArea(area.id)}
                      className={cn(
                        "flex items-center gap-3 p-4 rounded-xl border text-left transition-all",
                        selected
                          ? "bg-indigo-900/40 border-indigo-500 text-white"
                          : "bg-zinc-800/50 border-zinc-700 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800"
                      )}
                    >
                      <span className="text-2xl">{area.emoji}</span>
                      <span className="text-sm font-medium leading-tight">{area.label}</span>
                      {selected && (
                        <Check size={14} className="ml-auto text-indigo-400 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
              {selectedAreas.length === 0 && (
                <p className="text-zinc-600 text-xs text-center mt-4">
                  Wähle mindestens einen Bereich aus
                </p>
              )}
            </div>
          )}

          {/* ── Step 3: Erstes Ziel ── */}
          {step === 3 && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Dein erstes Ziel</h2>
              <p className="text-zinc-400 text-sm mb-6">
                Wähle ein Ziel oder gib dein eigenes ein.
              </p>

              {suggestedGoals.length > 0 && (
                <div className="grid gap-2 mb-4">
                  {suggestedGoals.map((goal) => (
                    <button
                      key={goal}
                      onClick={() => {
                        setSelectedGoal(goal);
                        setCustomGoal("");
                      }}
                      className={cn(
                        "flex items-center gap-3 p-3.5 rounded-xl border text-left transition-all text-sm",
                        selectedGoal === goal
                          ? "bg-indigo-900/40 border-indigo-500 text-white"
                          : "bg-zinc-800/50 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                      )}
                    >
                      <span className="text-lg">🎯</span>
                      <span>{goal}</span>
                      {selectedGoal === goal && (
                        <Check size={14} className="ml-auto text-indigo-400 shrink-0" />
                      )}
                    </button>
                  ))}
                </div>
              )}

              <div>
                <label className="text-zinc-500 text-xs mb-2 block">
                  Oder eigenes Ziel eingeben:
                </label>
                <input
                  type="text"
                  value={customGoal}
                  onChange={(e) => {
                    setCustomGoal(e.target.value);
                    setSelectedGoal(null);
                  }}
                  placeholder="Mein Ziel ist…"
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
            </div>
          )}

          {/* ── Step 4: Tagesstruktur ── */}
          {step === 4 && (
            <div>
              <h2 className="text-xl font-bold text-white mb-2">Tagesstruktur</h2>
              <p className="text-zinc-400 text-sm mb-6">
                Wann startest du deinen Tag und was gehört zu deiner Morgenroutine?
              </p>

              <div className="mb-6">
                <label className="text-zinc-400 text-sm mb-2 block">
                  Wann stehst du auf?
                </label>
                <input
                  type="time"
                  value={wakeupTime}
                  onChange={(e) => setWakeupTime(e.target.value)}
                  className="bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-base focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              <div>
                <label className="text-zinc-400 text-sm mb-3 block">
                  Welche Morgenroutinen willst du?
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {MORNING_ROUTINES.map((r) => {
                    const selected = selectedRoutines.includes(r.id);
                    return (
                      <button
                        key={r.id}
                        onClick={() => toggleRoutine(r.id)}
                        className={cn(
                          "flex items-center gap-2.5 p-3 rounded-xl border text-left transition-all text-sm",
                          selected
                            ? "bg-indigo-900/40 border-indigo-500 text-white"
                            : "bg-zinc-800/50 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                        )}
                      >
                        <span className="text-xl">{r.emoji}</span>
                        <span className="text-sm">{r.label}</span>
                        {selected && (
                          <Check size={13} className="ml-auto text-indigo-400 shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── Step 5: Fertig ── */}
          {step === 5 && (
            <div className="text-center">
              <div className="text-6xl mb-6">🚀</div>
              <h2 className="text-2xl font-bold text-white mb-3">
                Dein Personal OS ist bereit!
              </h2>
              <p className="text-zinc-400 mb-8 text-sm">
                Hier ist was wir eingerichtet haben:
              </p>

              <div className="bg-zinc-800/50 rounded-xl p-5 mb-8 text-left space-y-3">
                {name && (
                  <div className="flex items-center gap-3">
                    <span className="text-xl">👤</span>
                    <div>
                      <div className="text-zinc-400 text-xs">Name</div>
                      <div className="text-white text-sm font-medium">{name}</div>
                    </div>
                  </div>
                )}
                {selectedAreas.length > 0 && (
                  <div className="flex items-start gap-3">
                    <span className="text-xl">🎯</span>
                    <div>
                      <div className="text-zinc-400 text-xs">Lebensbereiche</div>
                      <div className="text-white text-sm font-medium">
                        {selectedAreas
                          .map((a) => AREAS.find((area) => area.id === a)?.label ?? a)
                          .join(", ")}
                      </div>
                    </div>
                  </div>
                )}
                {(selectedGoal || customGoal.trim()) && (
                  <div className="flex items-center gap-3">
                    <span className="text-xl">⭐</span>
                    <div>
                      <div className="text-zinc-400 text-xs">Erstes Ziel</div>
                      <div className="text-white text-sm font-medium">{selectedGoal || customGoal}</div>
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <span className="text-xl">⏰</span>
                  <div>
                    <div className="text-zinc-400 text-xs">Aufstehzeit</div>
                    <div className="text-white text-sm font-medium">{wakeupTime} Uhr</div>
                  </div>
                </div>
                {selectedRoutines.length > 0 && (
                  <div className="flex items-start gap-3">
                    <span className="text-xl">🌅</span>
                    <div>
                      <div className="text-zinc-400 text-xs">Morgenroutinen</div>
                      <div className="text-white text-sm font-medium">
                        {selectedRoutines
                          .map((r) => MORNING_ROUTINES.find((mr) => mr.id === r)?.label ?? r)
                          .join(", ")}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {error && (
                <div className="bg-red-900/30 border border-red-800 rounded-xl p-3 mb-4 text-red-400 text-sm">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Navigation buttons */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-zinc-800">
            {step > 1 ? (
              <button
                onClick={handleBack}
                className="px-4 py-2.5 text-zinc-400 hover:text-white transition-colors text-sm"
              >
                ← Zurück
              </button>
            ) : (
              <div />
            )}

            {step < totalSteps ? (
              <button
                onClick={handleNext}
                disabled={!canProceed()}
                className={cn(
                  "flex items-center gap-2 px-6 py-2.5 rounded-xl font-medium text-sm transition-all",
                  canProceed()
                    ? "bg-indigo-600 hover:bg-indigo-500 text-white"
                    : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                )}
              >
                {step === 1 ? "Los geht's" : "Weiter"}
                <ChevronRight size={16} />
              </button>
            ) : (
              <button
                onClick={handleFinish}
                disabled={submitting}
                className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-all"
              >
                {submitting ? "Speichere…" : "Dashboard öffnen"}
                <ChevronRight size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
