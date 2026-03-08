"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { mutate } from "swr";
import Header from "@/components/Header";
import { clearToken, setToken, api, UserSettings, SettingsUpdateBody, ActiveHoursResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { key: "health", label: "Gesundheit" },
  { key: "business", label: "Business" },
  { key: "personal", label: "Persönlich" },
  { key: "fitness", label: "Fitness" },
  { key: "finance", label: "Finanzen" },
  { key: "learning", label: "Lernen" },
];

const WEEKDAYS = [
  { value: "monday", label: "Montag" },
  { value: "tuesday", label: "Dienstag" },
  { value: "wednesday", label: "Mittwoch" },
  { value: "thursday", label: "Donnerstag" },
  { value: "friday", label: "Freitag" },
  { value: "saturday", label: "Samstag" },
  { value: "sunday", label: "Sonntag" },
];

const TOGGLE_LABELS: Record<string, { label: string; desc: string }> = {
  priorities_enabled: {
    label: "Priorities",
    desc: "Tägliche Top-Prioritäten im Morning Brief",
  },
  review_enabled: {
    label: "Evening Review",
    desc: "Abendliches Tages-Review und Check-in",
  },
  proactive_enabled: {
    label: "Proaktive Nachrichten",
    desc: "KI sendet unaufgefordert Tipps und Erinnerungen",
  },
  reflection_enabled: {
    label: "Weekly Reflection",
    desc: "Wöchentliche Reflexions-Session am Wochenende",
  },
};

function Toggle({
  checked,
  onChange,
  saving,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  saving?: boolean;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      disabled={saving}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full transition-colors shrink-0",
        checked ? "bg-blue-600" : "bg-zinc-600",
        saving && "opacity-50 cursor-wait"
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
          checked ? "translate-x-6" : "translate-x-1"
        )}
      />
    </button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <h2 className="text-white font-semibold mb-4">{title}</h2>
      {children}
    </div>
  );
}

function SaveButton({
  onClick,
  saving,
  saved,
  label = "Speichern",
}: {
  onClick: () => void;
  saving: boolean;
  saved: boolean;
  label?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={saving}
      className={cn(
        "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
        saved
          ? "bg-green-700 text-white"
          : saving
          ? "bg-zinc-700 text-zinc-400 cursor-wait"
          : "bg-blue-600 hover:bg-blue-700 text-white"
      )}
    >
      {saved ? "✓ Gespeichert" : saving ? "..." : label}
    </button>
  );
}

export default function SettingsPage() {
  const { data: settings, error: settingsError, isLoading: settingsLoading } = useSWR<UserSettings>("/api/settings", api.getSettings);
  const { data: activeHours } = useSWR<ActiveHoursResponse>("active-hours", () => api.autopilotActiveHours(30));
  const [saveError, setSaveError] = useState<string | null>(null);

  // Token
  const [token, setTokenInput] = useState("");
  const [tokenSaved, setTokenSaved] = useState(false);
  const [health, setHealth] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  // Profile
  const [firstName, setFirstName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  // Token regeneration
  const [regenerating, setRegenerating] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);

  // Toggles
  const [toggles, setToggles] = useState({
    priorities_enabled: true,
    review_enabled: true,
    proactive_enabled: true,
    reflection_enabled: false,
  });
  const [togglingSaving, setToggleSaving] = useState<string | null>(null);

  // Times
  const [times, setTimes] = useState({
    morning_brief_time: "06:30",
    evening_review_time: "21:00",
    weekly_reflection_day: "sunday",
    weekly_reflection_time: "19:00",
  });
  const [timesSaving, setTimesSaving] = useState(false);
  const [timesSaved, setTimesSaved] = useState(false);

  // Quiet hours
  const [quietStart, setQuietStart] = useState(22);
  const [quietEnd, setQuietEnd] = useState(8);
  const [quietSaving, setQuietSaving] = useState(false);
  const [quietSaved, setQuietSaved] = useState(false);

  // Category weights
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [weightsSaving, setWeightsSaving] = useState(false);
  const [weightsSaved, setWeightsSaved] = useState(false);

  // Export / Delete
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("api_token") ?? "";
    setTokenInput(t);
  }, []);

  useEffect(() => {
    if (settings) {
      setFirstName(
        settings.profile.first_name ||
          settings.profile.telegram_username ||
          ""
      );
      setTimezone(settings.profile.timezone || "");
      setToggles(settings.toggles);
      setTimes(settings.times);
      setQuietStart(settings.times.quiet_hour_start ?? 22);
      setQuietEnd(settings.times.quiet_hour_end ?? 8);
      const w: Record<string, number> = {};
      CATEGORIES.forEach((c) => {
        w[c.key] = settings.category_weights[c.key] ?? 5;
      });
      setWeights(w);
    }
  }, [settings]);

  const saveToken = () => {
    if (token.trim()) {
      setToken(token.trim());
      setTokenSaved(true);
      setTimeout(() => setTokenSaved(false), 2000);
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
    } catch {
      setHealth("❌ API nicht erreichbar");
    } finally {
      setChecking(false);
    }
  };

  const saveProfile = async () => {
    setProfileSaving(true);
    setSaveError(null);
    try {
      await api.updateProfile({ first_name: firstName, timezone: timezone || undefined });
      setProfileSaved(true);
      await mutate(() => true, undefined, { revalidate: true });
      setTimeout(() => setProfileSaved(false), 2000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setProfileSaving(false);
    }
  };

  const regenerateToken = async () => {
    setRegenerating(true);
    setSaveError(null);
    try {
      const res = await api.generateToken();
      setNewToken(res.token);
      setToken(res.token);
      setTokenInput(res.token);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Token-Generierung fehlgeschlagen");
    } finally {
      setRegenerating(false);
    }
  };

  const handleToggle = async (key: string, value: boolean) => {
    setToggles((prev) => ({ ...prev, [key]: value }));
    setToggleSaving(key);
    try {
      await api.updateSettings({ [key]: value } as SettingsUpdateBody);
    } catch {
      setToggles((prev) => ({ ...prev, [key]: !value }));
    } finally {
      setToggleSaving(null);
    }
  };

  const saveTimes = async () => {
    setTimesSaving(true);
    setSaveError(null);
    try {
      await api.updateSettings(times);
      setTimesSaved(true);
      setTimeout(() => setTimesSaved(false), 2000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setTimesSaving(false);
    }
  };

  const saveQuietHours = async () => {
    setQuietSaving(true);
    setSaveError(null);
    try {
      await api.updateSettings({ quiet_hour_start: quietStart, quiet_hour_end: quietEnd });
      setQuietSaved(true);
      setTimeout(() => setQuietSaved(false), 2000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setQuietSaving(false);
    }
  };

  const saveWeights = async () => {
    setWeightsSaving(true);
    setSaveError(null);
    try {
      await api.updateSettings({ category_weights: weights });
      setWeightsSaved(true);
      setTimeout(() => setWeightsSaved(false), 2000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setWeightsSaving(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setSaveError(null);
    try {
      const data = await api.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `personal-os-export-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  };

  const [exportingCsv, setExportingCsv] = useState(false);

  const handleExportCsv = async () => {
    setExportingCsv(true);
    setSaveError(null);
    try {
      const csv = await api.exportDataCsv();
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `personal-os-tasks-${new Date().toISOString().split("T")[0]}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Export fehlgeschlagen");
    } finally {
      setExportingCsv(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== "LÖSCHEN") return;
    setDeleting(true);
    setSaveError(null);
    try {
      await api.deleteAccount();
      clearToken();
      window.location.reload();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Löschen fehlgeschlagen");
      setDeleting(false);
    }
  };

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <div>
      <Header title="⚙️ Einstellungen" />

      {settingsLoading && (
        <div className="text-zinc-500 text-sm mb-4">Einstellungen laden…</div>
      )}
      {settingsError && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-4 py-3 mb-4 flex items-center justify-between">
          <span className="text-red-400 text-sm">Einstellungen konnten nicht geladen werden</span>
          <button onClick={() => window.location.reload()} className="text-xs text-zinc-400 hover:text-white ml-4">
            Neu laden
          </button>
        </div>
      )}
      {saveError && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-lg px-4 py-3 mb-4 flex items-center justify-between">
          <span className="text-red-400 text-sm">{saveError}</span>
          <button onClick={() => setSaveError(null)} className="text-zinc-500 hover:text-white ml-4 text-lg leading-none">×</button>
        </div>
      )}

      <div className="space-y-6 max-w-lg">
        {/* ── Profil ────────────────────────────────────────────── */}
        <Section title="👤 Profil">
          <div className="space-y-4">
            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">
                Dein Name
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveProfile()}
                  placeholder="Dein Name..."
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
                <SaveButton
                  onClick={saveProfile}
                  saving={profileSaving}
                  saved={profileSaved}
                />
              </div>
            </div>

            {settings?.profile.telegram_username && (
              <div>
                <label className="text-zinc-400 text-xs mb-1.5 block">
                  Telegram Username
                </label>
                <div className="flex items-center gap-2 bg-zinc-800/50 border border-zinc-700/50 rounded-lg px-3 py-2">
                  <span className="text-zinc-500 text-sm">@</span>
                  <span className="text-zinc-300 text-sm">
                    {settings.profile.telegram_username}
                  </span>
                  <span className="ml-auto text-zinc-600 text-xs">read-only</span>
                </div>
              </div>
            )}

            <div>
              <label className="text-zinc-400 text-xs mb-1.5 block">
                Zeitzone
              </label>
              <input
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="z.B. Europe/Berlin"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>
        </Section>

        {/* ── Benachrichtigungen ────────────────────────────────── */}
        <Section title="🔔 Benachrichtigungen">
          <div className="space-y-4">
            {(Object.keys(TOGGLE_LABELS) as (keyof typeof toggles)[]).map((key) => (
              <div key={key} className="flex items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-medium">
                    {TOGGLE_LABELS[key].label}
                  </div>
                  <div className="text-zinc-500 text-xs mt-0.5">
                    {TOGGLE_LABELS[key].desc}
                  </div>
                </div>
                <Toggle
                  checked={toggles[key]}
                  onChange={(v) => handleToggle(key, v)}
                  saving={togglingSaving === key}
                />
              </div>
            ))}
            <div className="border-t border-zinc-800 pt-4">
              <div className="text-white text-sm font-medium mb-1">Ruhestunden</div>
              <div className="text-zinc-500 text-xs mb-3">Keine Benachrichtigungen in diesem Zeitraum</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 text-xs mb-1.5 block">Von (Stunde)</label>
                  <select
                    value={quietStart}
                    onChange={(e) => setQuietStart(parseInt(e.target.value))}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, "0")}:00</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-zinc-400 text-xs mb-1.5 block">Bis (Stunde)</label>
                  <select
                    value={quietEnd}
                    onChange={(e) => setQuietEnd(parseInt(e.target.value))}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, "0")}:00</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex justify-end mt-3">
                <SaveButton
                  onClick={saveQuietHours}
                  saving={quietSaving}
                  saved={quietSaved}
                />
              </div>
            </div>
          </div>
        </Section>

        {/* ── Zeiten ───────────────────────────────────────────── */}
        <Section title="🕐 Zeiten">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-zinc-400 text-xs mb-1.5 block">
                  Morning Brief
                </label>
                <input
                  type="time"
                  value={times.morning_brief_time}
                  onChange={(e) =>
                    setTimes((p) => ({ ...p, morning_brief_time: e.target.value }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              <div>
                <label className="text-zinc-400 text-xs mb-1.5 block">
                  Evening Review
                </label>
                <input
                  type="time"
                  value={times.evening_review_time}
                  onChange={(e) =>
                    setTimes((p) => ({ ...p, evening_review_time: e.target.value }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-zinc-400 text-xs mb-1.5 block">
                  Reflexions-Tag
                </label>
                <select
                  value={times.weekly_reflection_day}
                  onChange={(e) =>
                    setTimes((p) => ({ ...p, weekly_reflection_day: e.target.value }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                >
                  {WEEKDAYS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-zinc-400 text-xs mb-1.5 block">
                  Reflexions-Zeit
                </label>
                <input
                  type="time"
                  value={times.weekly_reflection_time}
                  onChange={(e) =>
                    setTimes((p) => ({
                      ...p,
                      weekly_reflection_time: e.target.value,
                    }))
                  }
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <SaveButton
                onClick={saveTimes}
                saving={timesSaving}
                saved={timesSaved}
              />
            </div>
          </div>
        </Section>

        {/* ── Kategorien-Gewichtung ─────────────────────────────── */}
        <Section title="⚖️ Kategorien-Gewichtung">
          <p className="text-zinc-500 text-xs mb-4">
            Wie wichtig ist jede Kategorie für dich? Beeinflusst die Priorisierung.
          </p>
          <div className="space-y-3">
            {CATEGORIES.map((c) => (
              <div key={c.key}>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-zinc-300 text-sm">{c.label}</span>
                  <span className="text-blue-400 text-sm font-mono w-4 text-right">
                    {weights[c.key] ?? 5}
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={weights[c.key] ?? 5}
                  onChange={(e) =>
                    setWeights((p) => ({
                      ...p,
                      [c.key]: parseInt(e.target.value),
                    }))
                  }
                  className="w-full h-1.5 bg-zinc-700 rounded-full appearance-none cursor-pointer accent-blue-500"
                />
              </div>
            ))}
          </div>
          <div className="flex justify-end mt-4">
            <SaveButton
              onClick={saveWeights}
              saving={weightsSaving}
              saved={weightsSaved}
            />
          </div>
        </Section>

        {/* ── API Token ────────────────────────────────────────── */}
        <Section title="🔑 API Token">
          <p className="text-zinc-500 text-sm mb-4">
            Bearer Token für die API-Authentifizierung. Aus dem Telegram Bot via{" "}
            <code className="bg-zinc-800 px-1 py-0.5 rounded text-xs">/token</code>.
          </p>
          <div className="flex gap-2 mb-3">
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
                tokenSaved
                  ? "bg-green-700 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              )}
            >
              {tokenSaved ? "✓ Gespeichert" : "Speichern"}
            </button>
          </div>
          <div className="border-t border-zinc-800 pt-3">
            <p className="text-zinc-500 text-xs mb-2">Neuen Token generieren (invalidiert den alten):</p>
            <button
              onClick={regenerateToken}
              disabled={regenerating}
              className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {regenerating ? "Generiere..." : "🔄 Token regenerieren"}
            </button>
            {newToken && (
              <div className="mt-3 p-3 bg-green-950/40 border border-green-800/50 rounded-lg">
                <p className="text-green-400 text-xs mb-1.5">Neuer Token (bereits gespeichert):</p>
                <code className="text-green-300 text-xs break-all">{newToken}</code>
              </div>
            )}
          </div>
        </Section>

        {/* ── API Verbindung ───────────────────────────────────── */}
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

        {/* ── Daten-Export ─────────────────────────────────────── */}
        <Section title="📦 Daten-Export">
          <p className="text-zinc-500 text-sm mb-4">
            Alle deine Daten als JSON-Datei herunterladen (Objectives, Tasks,
            Logs, Routinen, Brain Dumps, Kalender). Tasks auch als CSV.
          </p>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {exporting ? "Exportiere..." : "📥 JSON exportieren"}
            </button>
            <button
              onClick={handleExportCsv}
              disabled={exportingCsv}
              className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {exportingCsv ? "Exportiere..." : "📊 CSV exportieren"}
            </button>
          </div>
        </Section>

        {/* ── Optimale Aktivzeiten (E4) ────────────────────────── */}
        {activeHours && activeHours.total_events > 0 && (
          <Section title="🕐 Optimale Aktivzeiten">
            <p className="text-zinc-500 text-xs mb-3">
              Basierend auf {activeHours.total_events} Aktionen der letzten {activeHours.days_analyzed} Tage.
            </p>
            {activeHours.peak_hour !== null && (
              <p className="text-zinc-300 text-sm mb-3">
                Aktivster Zeitraum:{" "}
                <span className="text-blue-400 font-medium">
                  {activeHours.peak_hour}:00 – {(activeHours.peak_hour + 1) % 24}:00 Uhr
                </span>
              </p>
            )}
            {activeHours.recommended_windows.length > 0 && (
              <div>
                <p className="text-zinc-500 text-xs mb-2">Empfohlene Nudge-Fenster:</p>
                <div className="flex flex-wrap gap-2">
                  {activeHours.recommended_windows.map((w, i) => (
                    <span
                      key={i}
                      className="text-xs px-2.5 py-1 bg-zinc-800 border border-zinc-700 rounded-full text-zinc-300"
                    >
                      {w.start_hour}:00 – {w.end_hour}:00
                    </span>
                  ))}
                </div>
              </div>
            )}
          </Section>
        )}

        {/* ── Über Personal OS ─────────────────────────────────── */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-3">ℹ️ Über Personal OS</h2>
          <div className="space-y-1 text-sm text-zinc-400">
            <div className="flex justify-between">
              <span>Version</span>
              <span className="text-zinc-300">8.0.0 (Phase 8 — Autopilot)</span>
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

        {/* ── Abmelden ─────────────────────────────────────────── */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-1">🚪 Abmelden</h2>
          <p className="text-zinc-500 text-sm mb-4">
            API Token entfernen und zur Login-Seite zurückkehren.
          </p>
          <button
            onClick={logout}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-red-400 rounded-lg text-sm transition-colors"
          >
            Abmelden
          </button>
        </div>

        {/* ── Account löschen ──────────────────────────────────── */}
        <div className="bg-zinc-900 border border-red-900/50 rounded-xl p-5">
          <h2 className="text-white font-semibold mb-1">🗑️ Account löschen</h2>
          <p className="text-zinc-500 text-sm mb-4">
            Löscht deinen Account und{" "}
            <strong className="text-red-400">alle zugehörigen Daten</strong>{" "}
            unwiderruflich (Objectives, Tasks, Logs, Routinen, etc.).
          </p>

          {!showDeleteConfirm ? (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="px-4 py-2 bg-red-900/40 hover:bg-red-900/60 text-red-400 border border-red-900/60 rounded-lg text-sm transition-colors"
            >
              Account löschen
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-red-400 text-sm font-medium">
                Tippe{" "}
                <code className="bg-red-900/30 px-1.5 py-0.5 rounded">
                  LÖSCHEN
                </code>{" "}
                zur Bestätigung:
              </p>
              <input
                type="text"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="LÖSCHEN"
                className="w-full bg-zinc-800 border border-red-900/60 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-red-500 transition-colors"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleDeleteAccount}
                  disabled={deleteConfirmText !== "LÖSCHEN" || deleting}
                  className="px-4 py-2 bg-red-700 hover:bg-red-600 text-white rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {deleting ? "Lösche..." : "Endgültig löschen"}
                </button>
                <button
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeleteConfirmText("");
                  }}
                  className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 rounded-lg text-sm transition-colors"
                >
                  Abbrechen
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
