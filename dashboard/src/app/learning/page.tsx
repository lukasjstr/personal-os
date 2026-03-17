"use client";

import { useState, useCallback } from "react";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState } from "@/components/LoadingSpinner";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { cn } from "@/lib/utils";
import { Plus, BookOpen, Zap, Star, ChevronDown, ChevronUp, Trash2 } from "lucide-react";

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

type LearningItem = {
  id: number;
  title: string;
  content?: string;
  item_type: string;
  source?: string;
  skill_level: number;
  next_review_at?: string;
  review_count: number;
  last_reviewed_at?: string;
  ease_factor: number;
  ai_summary?: string;
  tags: string[];
  created_at: string;
};

type Tab = "all" | "due" | "skills";

const TYPE_COLORS: Record<string, string> = {
  book: "bg-blue-900/60 text-blue-300",
  article: "bg-purple-900/60 text-purple-300",
  concept: "bg-yellow-900/60 text-yellow-300",
  skill: "bg-green-900/60 text-green-300",
  note: "bg-zinc-700 text-zinc-300",
};

const QUALITY_BUTTONS = [
  { label: "Schlecht", quality: 1, color: "bg-red-900/60 hover:bg-red-800 text-red-300" },
  { label: "Ok", quality: 3, color: "bg-yellow-900/60 hover:bg-yellow-800 text-yellow-300" },
  { label: "Gut", quality: 4, color: "bg-blue-900/60 hover:bg-blue-800 text-blue-300" },
  { label: "Sehr gut", quality: 5, color: "bg-green-900/60 hover:bg-green-800 text-green-300" },
];

function SkillBar({ level }: { level: number }) {
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className={cn(
            "h-2 w-5 rounded-sm",
            i <= level ? "bg-green-500" : "bg-zinc-700"
          )}
        />
      ))}
    </div>
  );
}

function ItemCard({
  item,
  onReview,
  onDelete,
  showReviewButtons,
}: {
  item: LearningItem;
  onReview?: (id: number, quality: number) => void;
  onDelete?: (id: number) => void;
  showReviewButtons?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDue = item.next_review_at && new Date(item.next_review_at) <= new Date();

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-zinc-700 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", TYPE_COLORS[item.item_type] || TYPE_COLORS.note)}>
              {item.item_type}
            </span>
            {isDue && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-orange-900/60 text-orange-300 font-medium">
                fällig
              </span>
            )}
            {item.tags?.map((tag) => (
              <span key={tag} className="text-xs px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                {tag}
              </span>
            ))}
          </div>
          <h3 className="font-semibold text-white text-sm leading-tight">{item.title}</h3>
          {item.source && (
            <p className="text-xs text-zinc-500 mt-0.5">Quelle: {item.source}</p>
          )}
          {item.item_type === "skill" && (
            <div className="mt-2">
              <SkillBar level={item.skill_level} />
              <span className="text-xs text-zinc-400 mt-1 block">Level {item.skill_level}/5</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 text-zinc-400 hover:text-white transition-colors"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {onDelete && (
            <button
              onClick={() => onDelete(item.id)}
              className="p-1.5 text-zinc-600 hover:text-red-400 transition-colors"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-zinc-800 text-xs text-zinc-400 space-y-2">
          {item.ai_summary && (
            <p className="text-zinc-300 bg-zinc-800 rounded p-2 italic">{item.ai_summary}</p>
          )}
          {item.content && !item.ai_summary && (
            <p className="text-zinc-400">{item.content.slice(0, 400)}</p>
          )}
          <div className="flex gap-4 text-zinc-500">
            <span>Wiederholungen: {item.review_count}</span>
            <span>Ease: {item.ease_factor?.toFixed(2)}</span>
            {item.next_review_at && (
              <span>
                Nächste: {new Date(item.next_review_at).toLocaleDateString("de-DE")}
              </span>
            )}
          </div>
        </div>
      )}

      {showReviewButtons && onReview && (
        <div className="mt-3 flex gap-2 flex-wrap">
          {QUALITY_BUTTONS.map((btn) => (
            <button
              key={btn.quality}
              onClick={() => onReview(item.id, btn.quality)}
              className={cn("px-3 py-1.5 rounded-lg text-xs font-medium transition-colors", btn.color)}
            >
              {btn.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function AddItemModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [itemType, setItemType] = useState("note");
  const [source, setSource] = useState("");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/api/learning", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim() || null,
          item_type: itemType,
          source: source.trim() || null,
          tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        }),
      });
      onSave();
      onClose();
    } catch (e) {
      setError("Fehler beim Speichern");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-md p-6">
        <h2 className="text-lg font-bold text-white mb-4">Neues Lern-Item</h2>
        <div className="space-y-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Titel *"
            className="w-full bg-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm outline-none border border-zinc-700 focus:border-indigo-500"
          />
          <select
            value={itemType}
            onChange={(e) => setItemType(e.target.value)}
            className="w-full bg-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm outline-none border border-zinc-700"
          >
            <option value="note">Notiz</option>
            <option value="book">Buch</option>
            <option value="article">Artikel</option>
            <option value="concept">Konzept</option>
            <option value="skill">Skill</option>
          </select>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Inhalt / Notizen"
            rows={3}
            className="w-full bg-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm outline-none border border-zinc-700 focus:border-indigo-500 resize-none"
          />
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Quelle (optional)"
            className="w-full bg-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm outline-none border border-zinc-700 focus:border-indigo-500"
          />
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="Tags (kommagetrennt)"
            className="w-full bg-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm outline-none border border-zinc-700 focus:border-indigo-500"
          />
        </div>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button
            onClick={handleSave}
            disabled={saving || !title.trim()}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl py-2.5 font-semibold text-sm transition-colors"
          >
            {saving ? "Speichern…" : (["book", "article"].includes(itemType) ? "Speichern + AI-Zusammenfassung" : "Speichern")}
          </button>
          <button onClick={onClose} className="px-4 py-2.5 text-zinc-400 hover:text-white text-sm transition-colors">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

export default function LearningPage() {
  const [tab, setTab] = useState<Tab>("all");
  const [items, setItems] = useState<LearningItem[]>([]);
  const [dueItems, setDueItems] = useState<LearningItem[]>([]);
  const [skills, setSkills] = useState<LearningItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [reviewingId, setReviewingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [allRes, dueRes, skillsRes] = await Promise.all([
        apiFetch<{ items: LearningItem[] }>("/api/learning"),
        apiFetch<{ count: number; items: LearningItem[] }>("/api/learning/due"),
        apiFetch<{ skills: LearningItem[] }>("/api/learning/skills"),
      ]);
      setItems(allRes.items);
      setDueItems(dueRes.items);
      setSkills(skillsRes.skills);
      setError(null);
    } catch (e) {
      setError("Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, []);

  useAutoRefresh(load, 30000);

  useState(() => { load(); });

  const handleReview = async (itemId: number, quality: number) => {
    setReviewingId(itemId);
    try {
      await apiFetch(`/api/learning/${itemId}/review`, {
        method: "POST",
        body: JSON.stringify({ quality }),
      });
      await load();
    } catch (e) {
      // ignore
    } finally {
      setReviewingId(null);
    }
  };

  const handleDelete = async (itemId: number) => {
    try {
      await apiFetch(`/api/learning/${itemId}`, { method: "DELETE" });
      await load();
    } catch (e) {
      // ignore
    }
  };

  const tabItems = tab === "all" ? items : tab === "due" ? dueItems : skills;

  return (
    <>
      <Header title="📚 Wissen & Lernen" subtitle={`${items.length} Items · ${dueItems.length} fällig heute`} />
      <div className="p-4 space-y-4">
        {/* Tabs */}
        <div className="flex gap-1 bg-zinc-900 rounded-xl p-1 border border-zinc-800">
          {([
            { key: "all", label: "Alle Items", icon: BookOpen },
            { key: "due", label: `Heute fällig (${dueItems.length})`, icon: Zap },
            { key: "skills", label: "Skills", icon: Star },
          ] as const).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-colors",
                tab === key ? "bg-indigo-600 text-white" : "text-zinc-400 hover:text-white"
              )}
            >
              <Icon size={13} />
              <span className="hidden sm:inline">{label}</span>
              <span className="sm:hidden">{key === "all" ? "Alle" : key === "due" ? `Fällig (${dueItems.length})` : "Skills"}</span>
            </button>
          ))}
        </div>

        {/* Add button */}
        <button
          onClick={() => setShowAdd(true)}
          className="w-full flex items-center justify-center gap-2 bg-zinc-900 border border-zinc-700 hover:border-indigo-500 text-zinc-400 hover:text-indigo-400 rounded-xl py-3 text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Neues Lern-Item hinzufügen
        </button>

        {loading && <LoadingSpinner />}
        {error && <ErrorState message={error} />}

        {!loading && !error && tabItems.length === 0 && (
          <div className="text-center text-zinc-500 py-12 text-sm">
            {tab === "due" ? "Keine fälligen Wiederholungen — alles up to date! 🎉" :
             tab === "skills" ? "Noch keine Skills hinzugefügt." :
             "Noch keine Lern-Items. Füge dein erstes Item hinzu!"}
          </div>
        )}

        <div className="space-y-3">
          {tabItems.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              onReview={handleReview}
              onDelete={handleDelete}
              showReviewButtons={tab === "due"}
            />
          ))}
        </div>
      </div>

      {showAdd && (
        <AddItemModal
          onClose={() => setShowAdd(false)}
          onSave={load}
        />
      )}
    </>
  );
}
