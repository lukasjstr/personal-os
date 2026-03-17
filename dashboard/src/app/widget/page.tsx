"use client";

import { useState, useEffect } from "react";

const API_URL = typeof window !== "undefined" ? window.location.origin : "";

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("api_token") || "";
}

interface AutopilotToday {
  top_tasks?: Array<{ title: string; priority?: number }>;
  next_routine?: { title: string; time_of_day?: string } | null;
  focus_sentence?: string;
  date?: string;
}

export default function WidgetPage() {
  const [data, setData] = useState<AutopilotToday | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = async () => {
    const token = getToken();
    try {
      const res = await fetch(`${API_URL}/api/autopilot/today`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
        setLastUpdated(new Date());
      }
    } catch (e) {
      console.warn("Widget data fetch failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const today = new Date().toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "#0f172a", fontFamily: "-apple-system, BlinkMacSystemFont, sans-serif" }}
    >
      {/* Header */}
      <div className="px-5 pt-8 pb-4">
        <div className="text-indigo-400 text-xs font-semibold uppercase tracking-widest mb-1">Personal OS</div>
        <div className="text-white text-2xl font-bold">{today}</div>
        {loading && (
          <div className="text-zinc-500 text-xs mt-1">Lädt...</div>
        )}
        {lastUpdated && !loading && (
          <div className="text-zinc-600 text-xs mt-1">
            Aktualisiert: {lastUpdated.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
          </div>
        )}
      </div>

      {/* Focus Sentence */}
      {data?.focus_sentence && (
        <div className="mx-5 mb-4 px-4 py-3 bg-indigo-900/40 border border-indigo-700/50 rounded-2xl">
          <div className="text-indigo-300 text-xs font-medium uppercase tracking-wide mb-1">Fokus</div>
          <div className="text-white text-base leading-snug">{data.focus_sentence}</div>
        </div>
      )}

      {/* Top 3 Tasks */}
      <div className="mx-5 mb-4">
        <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wide mb-3">Top Aufgaben heute</div>
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-zinc-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : data?.top_tasks?.length ? (
          <div className="space-y-2">
            {data.top_tasks.slice(0, 3).map((task, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-4 py-3 bg-zinc-800/80 rounded-xl"
              >
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  i === 0 ? "bg-indigo-400" : i === 1 ? "bg-zinc-400" : "bg-zinc-600"
                }`} />
                <span className="text-white text-sm leading-tight">{task.title}</span>
                {task.priority && task.priority <= 2 && (
                  <span className="ml-auto text-xs bg-indigo-900/60 text-indigo-300 px-2 py-0.5 rounded-full flex-shrink-0">
                    P{task.priority}
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-zinc-500 text-sm px-4 py-3 bg-zinc-800/40 rounded-xl">
            Keine Tasks für heute
          </div>
        )}
      </div>

      {/* Next Routine */}
      {data?.next_routine && (
        <div className="mx-5 mb-4">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wide mb-3">Nächste Routine</div>
          <div className="flex items-center gap-3 px-4 py-3 bg-zinc-800/80 rounded-xl">
            <span className="text-2xl">🔄</span>
            <div>
              <div className="text-white text-sm font-medium">{data.next_routine.title}</div>
              {data.next_routine.time_of_day && (
                <div className="text-zinc-400 text-xs capitalize">{data.next_routine.time_of_day}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Refresh hint */}
      <div className="mt-auto px-5 pb-8">
        <button
          onClick={fetchData}
          className="w-full py-3 text-zinc-500 text-xs text-center rounded-xl active:bg-zinc-800 transition-colors"
        >
          Tippen zum Aktualisieren
        </button>
      </div>
    </div>
  );
}
