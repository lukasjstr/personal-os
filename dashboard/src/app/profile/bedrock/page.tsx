"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import LoadingSpinner from "@/components/LoadingSpinner";
import { Save, RotateCcw, Code2, FormInput, Plus, X } from "lucide-react";

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

// Strongly-typed bedrock model — matches scripts/seed_lukas_bedrock.py
type Identity = {
  name?: string;
  current_location?: string;
  home_country?: string;
  company?: string;
  co_founders?: string[];
  launch_target?: string;
  birthdays?: { self?: string; dad?: string };
};

type LifeAreaSpec = { name: string; vision: string };
type SkillLever = { name: string; description: string; priority: number };

type Bedrock = {
  identity?: Identity;
  core_line?: string;
  leitspruch?: string;
  life_areas?: LifeAreaSpec[];
  skill_levers?: SkillLever[];
  self_leadership_competencies?: string[];
  strengths?: string[];
  weaknesses?: string[];
  bottleneck?: string;
  language?: string;
  communication_style?: string;
};

type BedrockResponse = {
  bedrock: Bedrock;
  updated_at: string | null;
  history_count: number;
};

const EMPTY: Bedrock = {
  identity: { co_founders: [], birthdays: {} },
  core_line: "",
  leitspruch: "",
  life_areas: [],
  skill_levers: [],
  self_leadership_competencies: [],
  strengths: [],
  weaknesses: [],
  bottleneck: "",
  communication_style: "",
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 space-y-3">
      <h2 className="text-white font-semibold text-sm">{title}</h2>
      {children}
    </section>
  );
}

function TextInput({
  label,
  value,
  onChange,
  placeholder,
  textarea = false,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (s: string) => void;
  placeholder?: string;
  textarea?: boolean;
  rows?: number;
}) {
  const cls =
    "w-full bg-black border border-zinc-800 text-zinc-200 text-xs rounded-lg p-2 outline-none focus:border-indigo-600";
  return (
    <label className="block">
      <div className="text-zinc-500 text-[11px] mb-1">{label}</div>
      {textarea ? (
        <textarea
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={rows}
          className={cls}
        />
      ) : (
        <input
          type="text"
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cls}
        />
      )}
    </label>
  );
}

function StringList({
  label,
  items,
  setItems,
}: {
  label: string;
  items: string[];
  setItems: (next: string[]) => void;
}) {
  return (
    <div>
      <div className="text-zinc-500 text-[11px] mb-1">{label}</div>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="flex gap-1">
            <input
              type="text"
              value={item}
              onChange={(e) => {
                const next = [...items];
                next[i] = e.target.value;
                setItems(next);
              }}
              className="flex-1 bg-black border border-zinc-800 text-zinc-200 text-xs rounded-lg p-2 outline-none focus:border-indigo-600"
            />
            <button
              onClick={() => setItems(items.filter((_, idx) => idx !== i))}
              className="bg-zinc-800 hover:bg-red-900/40 text-zinc-400 hover:text-red-300 rounded-lg px-2"
              title="Entfernen"
            >
              <X size={12} />
            </button>
          </div>
        ))}
        <button
          onClick={() => setItems([...items, ""])}
          className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
        >
          <Plus size={12} /> hinzufügen
        </button>
      </div>
    </div>
  );
}

export default function BedrockPage() {
  const [bedrock, setBedrock] = useState<Bedrock>(EMPTY);
  const [original, setOriginal] = useState<Bedrock>(EMPTY);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [historyCount, setHistoryCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [mode, setMode] = useState<"form" | "json">("form");
  const [jsonText, setJsonText] = useState<string>("{}");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<BedrockResponse>("/api/life-profile/bedrock");
      const b = { ...EMPTY, ...(data.bedrock || {}) };
      setBedrock(b);
      setOriginal(b);
      setJsonText(JSON.stringify(data.bedrock || {}, null, 2));
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

  const save = async () => {
    setError(null);
    const payload =
      mode === "json"
        ? (() => {
            try {
              return JSON.parse(jsonText);
            } catch (e) {
              setError("JSON ungültig: " + (e instanceof Error ? e.message : String(e)));
              return null;
            }
          })()
        : bedrock;
    if (payload === null) return;
    setSaving(true);
    try {
      await apiFetch("/api/life-profile/bedrock", {
        method: "PATCH",
        body: JSON.stringify({ bedrock: payload }),
      });
      await load();
      setSuccessMsg("Bedrock gespeichert. Vorherige Version archiviert.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e) {
      setError("Speichern fehlgeschlagen: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setBedrock(original);
    setJsonText(JSON.stringify(original, null, 2));
    setError(null);
  };

  const setField = <K extends keyof Bedrock>(key: K, value: Bedrock[K]) => {
    setBedrock((prev) => ({ ...prev, [key]: value }));
  };

  const setIdentity = <K extends keyof Identity>(key: K, value: Identity[K]) => {
    setBedrock((prev) => ({
      ...prev,
      identity: { ...(prev.identity || {}), [key]: value },
    }));
  };

  return (
    <>
      <Header
        title="🪨 Bedrock"
        subtitle="Hand-kuratierte Identität — fließt in jeden AI-Call"
      />
      <div className="p-4 space-y-4">
        {loading && <LoadingSpinner />}

        {!loading && (
          <>
            {/* Toolbar */}
            <div className="flex items-center justify-between gap-3 bg-zinc-900 border border-zinc-800 rounded-2xl p-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setMode("form")}
                  className={
                    "flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs " +
                    (mode === "form"
                      ? "bg-indigo-600 text-white"
                      : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700")
                  }
                >
                  <FormInput size={12} /> Formular
                </button>
                <button
                  onClick={() => {
                    setJsonText(JSON.stringify(bedrock, null, 2));
                    setMode("json");
                  }}
                  className={
                    "flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs " +
                    (mode === "json"
                      ? "bg-indigo-600 text-white"
                      : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700")
                  }
                >
                  <Code2 size={12} /> JSON
                </button>
              </div>
              <div className="text-xs text-zinc-500 text-right">
                {updatedAt ? (
                  <>Stand: {new Date(updatedAt).toLocaleString("de-DE")}</>
                ) : (
                  <>noch nie gespeichert</>
                )}
                <br />
                History: {historyCount}
              </div>
            </div>

            {/* Messages */}
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

            {mode === "json" ? (
              <Section title="JSON-Editor">
                <textarea
                  value={jsonText}
                  onChange={(e) => setJsonText(e.target.value)}
                  spellCheck={false}
                  className="w-full min-h-[520px] bg-black border border-zinc-800 text-zinc-200 text-xs font-mono rounded-xl p-3 outline-none focus:border-indigo-600"
                />
              </Section>
            ) : (
              <div className="space-y-4">
                {/* Identity */}
                <Section title="Identität">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <TextInput
                      label="Name"
                      value={bedrock.identity?.name || ""}
                      onChange={(v) => setIdentity("name", v)}
                    />
                    <TextInput
                      label="Aktueller Ort"
                      value={bedrock.identity?.current_location || ""}
                      onChange={(v) => setIdentity("current_location", v)}
                    />
                    <TextInput
                      label="Heimatland"
                      value={bedrock.identity?.home_country || ""}
                      onChange={(v) => setIdentity("home_country", v)}
                    />
                    <TextInput
                      label="Company"
                      value={bedrock.identity?.company || ""}
                      onChange={(v) => setIdentity("company", v)}
                    />
                    <TextInput
                      label="Launch-Target"
                      value={bedrock.identity?.launch_target || ""}
                      onChange={(v) => setIdentity("launch_target", v)}
                    />
                    <TextInput
                      label="Geburtstag (selbst)"
                      value={bedrock.identity?.birthdays?.self || ""}
                      onChange={(v) =>
                        setIdentity("birthdays", {
                          ...(bedrock.identity?.birthdays || {}),
                          self: v,
                        })
                      }
                    />
                  </div>
                  <StringList
                    label="Co-Founders"
                    items={bedrock.identity?.co_founders || []}
                    setItems={(next) => setIdentity("co_founders", next)}
                  />
                </Section>

                {/* Leitspruch + core_line */}
                <Section title="Leitspruch & Core-Line">
                  <TextInput
                    label="Core Line (scharfes Zitat, 1 Zeile)"
                    value={bedrock.core_line || ""}
                    onChange={(v) => setField("core_line", v)}
                    placeholder="z.B. Cut kommt vor Expansion."
                  />
                  <TextInput
                    label="Leitspruch (mehrzeilig)"
                    value={bedrock.leitspruch || ""}
                    onChange={(v) => setField("leitspruch", v)}
                    textarea
                    rows={5}
                  />
                </Section>

                {/* Life areas */}
                <Section title="9 Lebensbereiche">
                  {(bedrock.life_areas || []).map((area, i) => (
                    <div
                      key={i}
                      className="flex flex-col gap-2 bg-black/40 rounded-lg p-2"
                    >
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <TextInput
                          label="Name"
                          value={area.name}
                          onChange={(v) => {
                            const next = [...(bedrock.life_areas || [])];
                            next[i] = { ...next[i], name: v };
                            setField("life_areas", next);
                          }}
                        />
                        <TextInput
                          label="Vision"
                          value={area.vision}
                          onChange={(v) => {
                            const next = [...(bedrock.life_areas || [])];
                            next[i] = { ...next[i], vision: v };
                            setField("life_areas", next);
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </Section>

                {/* Skill levers */}
                <Section title="4 Skill-Hebel">
                  {(bedrock.skill_levers || [])
                    .map((l, idx) => ({ ...l, _idx: idx }))
                    .sort((a, b) => a.priority - b.priority)
                    .map((l) => (
                      <div
                        key={l._idx}
                        className="grid grid-cols-12 gap-2 bg-black/40 rounded-lg p-2"
                      >
                        <div className="col-span-2">
                          <TextInput
                            label="P"
                            value={String(l.priority)}
                            onChange={(v) => {
                              const next = [...(bedrock.skill_levers || [])];
                              next[l._idx] = { ...next[l._idx], priority: parseInt(v, 10) || 5 };
                              setField("skill_levers", next);
                            }}
                          />
                        </div>
                        <div className="col-span-4">
                          <TextInput
                            label="Name"
                            value={l.name}
                            onChange={(v) => {
                              const next = [...(bedrock.skill_levers || [])];
                              next[l._idx] = { ...next[l._idx], name: v };
                              setField("skill_levers", next);
                            }}
                          />
                        </div>
                        <div className="col-span-6">
                          <TextInput
                            label="Description"
                            value={l.description}
                            onChange={(v) => {
                              const next = [...(bedrock.skill_levers || [])];
                              next[l._idx] = { ...next[l._idx], description: v };
                              setField("skill_levers", next);
                            }}
                          />
                        </div>
                      </div>
                    ))}
                </Section>

                {/* Lists */}
                <Section title="Stärken & Schwächen">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <StringList
                      label="Stärken"
                      items={bedrock.strengths || []}
                      setItems={(n) => setField("strengths", n)}
                    />
                    <StringList
                      label="Schwächen"
                      items={bedrock.weaknesses || []}
                      setItems={(n) => setField("weaknesses", n)}
                    />
                  </div>
                  <TextInput
                    label="Bottleneck"
                    value={bedrock.bottleneck || ""}
                    onChange={(v) => setField("bottleneck", v)}
                  />
                </Section>

                <Section title="Selbstführungs-Kompetenzen">
                  <StringList
                    label="10 Kompetenzen"
                    items={bedrock.self_leadership_competencies || []}
                    setItems={(n) => setField("self_leadership_competencies", n)}
                  />
                </Section>

                <Section title="Kommunikation">
                  <TextInput
                    label="Kommunikations-Stil"
                    value={bedrock.communication_style || ""}
                    onChange={(v) => setField("communication_style", v)}
                    textarea
                    rows={2}
                  />
                  <TextInput
                    label="Sprache"
                    value={bedrock.language || ""}
                    onChange={(v) => setField("language", v)}
                  />
                </Section>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 sticky bottom-2">
              <button
                onClick={save}
                disabled={saving}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl px-4 py-2 text-sm font-semibold"
              >
                <Save size={14} />
                {saving ? "Speichere…" : "Speichern"}
              </button>
              <button
                onClick={reset}
                disabled={saving}
                className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-300 rounded-xl px-4 py-2 text-sm font-medium"
              >
                <RotateCcw size={14} />
                Zurücksetzen
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
