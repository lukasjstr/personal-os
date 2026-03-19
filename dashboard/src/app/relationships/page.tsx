"use client";

import { useState, useEffect, useCallback } from "react";
import { Users, Plus, Trash2, MessageCircle, CheckSquare, Calendar, PhoneCall } from "lucide-react";

const API_URL = typeof window !== "undefined" ? window.location.origin : "";

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("api_token") || "";
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

interface Contact {
  id: number;
  name: string;
  nickname: string | null;
  relationship_type: string;
  contact_frequency_days: number;
  last_contacted_at: string | null;
  days_since_contact: number | null;
  overdue_days: number | null;
  is_overdue: boolean;
  phone: string | null;
  email: string | null;
  notes: string | null;
  birthday: string | null;
}

interface Commitment {
  id: number;
  description: string;
  contact_id: number | null;
  contact_name: string | null;
  due_date: string | null;
  status: string;
  completed_at: string | null;
}

const RELATION_LABELS: Record<string, string> = {
  friend: "Freund",
  family: "Familie",
  colleague: "Kollege",
  mentor: "Mentor",
  partner: "Partner",
};

const INTERACTION_TYPES = ["call", "message", "meeting", "email", "other"];
const INTERACTION_LABELS: Record<string, string> = {
  call: "Anruf",
  message: "Nachricht",
  meeting: "Treffen",
  email: "E-Mail",
  other: "Sonstiges",
};

export default function RelationshipsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"contacts" | "commitments">("contacts");
  const [showNewContact, setShowNewContact] = useState(false);
  const [showNewCommitment, setShowNewCommitment] = useState(false);
  const [interactionContactId, setInteractionContactId] = useState<number | null>(null);
  const [interactionType, setInteractionType] = useState("call");
  const [interactionNotes, setInteractionNotes] = useState("");

  const [newContact, setNewContact] = useState({
    name: "",
    relationship_type: "friend",
    contact_frequency_days: 30,
    phone: "",
    email: "",
    notes: "",
  });
  const [newCommitment, setNewCommitment] = useState({
    description: "",
    contact_id: "",
    due_date: "",
  });

  const loadData = useCallback(async () => {
    try {
      const [c, cm] = await Promise.all([
        apiFetch<Contact[]>("/api/contacts"),
        apiFetch<Commitment[]>("/api/commitments"),
      ]);
      setContacts(c);
      setCommitments(cm);
    } catch (e) {
      console.error("Failed to load relationships data", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createContact = async () => {
    if (!newContact.name.trim()) return;
    try {
      await apiFetch("/api/contacts", {
        method: "POST",
        body: JSON.stringify(newContact),
      });
      await loadData();
      setShowNewContact(false);
      setNewContact({ name: "", relationship_type: "friend", contact_frequency_days: 30, phone: "", email: "", notes: "" });
    } catch (e) {
      alert("Fehler beim Erstellen des Kontakts");
    }
  };

  const deleteContact = async (id: number) => {
    if (!confirm("Kontakt löschen?")) return;
    try {
      await apiFetch(`/api/contacts/${id}`, { method: "DELETE" });
      await loadData();
    } catch (e) {
      alert("Fehler beim Löschen");
    }
  };

  const logInteraction = async () => {
    if (!interactionContactId) return;
    try {
      await apiFetch(`/api/contacts/${interactionContactId}/interaction`, {
        method: "POST",
        body: JSON.stringify({ interaction_type: interactionType, notes: interactionNotes }),
      });
      await loadData();
      setInteractionContactId(null);
      setInteractionNotes("");
    } catch (e) {
      alert("Fehler beim Loggen der Interaktion");
    }
  };

  const createCommitment = async () => {
    if (!newCommitment.description.trim()) return;
    try {
      await apiFetch("/api/commitments", {
        method: "POST",
        body: JSON.stringify({
          description: newCommitment.description,
          contact_id: newCommitment.contact_id ? parseInt(newCommitment.contact_id) : null,
          due_date: newCommitment.due_date || null,
        }),
      });
      await loadData();
      setShowNewCommitment(false);
      setNewCommitment({ description: "", contact_id: "", due_date: "" });
    } catch (e) {
      alert("Fehler beim Erstellen der Zusage");
    }
  };

  const markCommitmentDone = async (id: number) => {
    try {
      await apiFetch(`/api/commitments/${id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "done" }),
      });
      await loadData();
    } catch (e) {
      alert("Fehler beim Aktualisieren");
    }
  };

  const deleteCommitment = async (id: number) => {
    if (!confirm("Zusage löschen?")) return;
    try {
      await apiFetch(`/api/commitments/${id}`, { method: "DELETE" });
      await loadData();
    } catch (e) {
      alert("Fehler beim Löschen");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    );
  }

  const overdueContacts = contacts.filter((c) => c.is_overdue);
  const pendingCommitments = commitments.filter((c) => c.status !== "done");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users size={28} className="text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Beziehungen</h1>
            <p className="text-zinc-400 text-sm">
              {overdueContacts.length > 0 && (
                <span className="text-orange-400">{overdueContacts.length} überfällig · </span>
              )}
              {contacts.length} Kontakte · {pendingCommitments.length} offene Zusagen
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-900 rounded-xl p-1 border border-zinc-800">
        <button
          onClick={() => setActiveTab("contacts")}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "contacts"
              ? "bg-indigo-600 text-white"
              : "text-zinc-400 hover:text-white"
          }`}
        >
          Kontakte {contacts.length > 0 && `(${contacts.length})`}
        </button>
        <button
          onClick={() => setActiveTab("commitments")}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "commitments"
              ? "bg-indigo-600 text-white"
              : "text-zinc-400 hover:text-white"
          }`}
        >
          Zusagen {pendingCommitments.length > 0 && `(${pendingCommitments.length})`}
        </button>
      </div>

      {/* Contacts Tab */}
      {activeTab === "contacts" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowNewContact(!showNewContact)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
            >
              <Plus size={16} />
              Neuer Kontakt
            </button>
          </div>

          {/* New Contact Form */}
          {showNewContact && (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 space-y-3">
              <h3 className="text-white font-semibold">Neuen Kontakt hinzufügen</h3>
              <input
                value={newContact.name}
                onChange={(e) => setNewContact((p) => ({ ...p, name: e.target.value }))}
                placeholder="Name *"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              />
              <div className="grid grid-cols-2 gap-3">
                <select
                  value={newContact.relationship_type}
                  onChange={(e) => setNewContact((p) => ({ ...p, relationship_type: e.target.value }))}
                  className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                >
                  {Object.entries(RELATION_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={newContact.contact_frequency_days}
                    onChange={(e) => setNewContact((p) => ({ ...p, contact_frequency_days: parseInt(e.target.value) || 30 }))}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                  />
                  <span className="text-zinc-400 text-xs whitespace-nowrap">Tage</span>
                </div>
              </div>
              <input
                value={newContact.phone}
                onChange={(e) => setNewContact((p) => ({ ...p, phone: e.target.value }))}
                placeholder="Telefon"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              />
              <textarea
                value={newContact.notes}
                onChange={(e) => setNewContact((p) => ({ ...p, notes: e.target.value }))}
                placeholder="Notizen"
                rows={2}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              />
              <div className="flex gap-2">
                <button onClick={createContact} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors">
                  Erstellen
                </button>
                <button onClick={() => setShowNewContact(false)} className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors">
                  Abbrechen
                </button>
              </div>
            </div>
          )}

          {/* Interaction Log Modal */}
          {interactionContactId && (
            <div className="bg-zinc-900 border border-indigo-600/50 rounded-xl p-4 space-y-3">
              <h3 className="text-white font-semibold">Interaktion loggen</h3>
              <select
                value={interactionType}
                onChange={(e) => setInteractionType(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              >
                {INTERACTION_TYPES.map((t) => (
                  <option key={t} value={t}>{INTERACTION_LABELS[t]}</option>
                ))}
              </select>
              <textarea
                value={interactionNotes}
                onChange={(e) => setInteractionNotes(e.target.value)}
                placeholder="Notizen (optional)"
                rows={2}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              />
              <div className="flex gap-2">
                <button onClick={logInteraction} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors">
                  Speichern
                </button>
                <button onClick={() => setInteractionContactId(null)} className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors">
                  Abbrechen
                </button>
              </div>
            </div>
          )}

          {/* Contact Cards */}
          {contacts.length === 0 ? (
            <div className="text-center py-16 text-zinc-500">
              <Users size={48} className="mx-auto mb-4 opacity-30" />
              <p>Noch keine Kontakte. Füge deinen ersten Kontakt hinzu!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {contacts.map((contact) => (
                <div
                  key={contact.id}
                  className={`bg-zinc-900 border rounded-xl p-4 transition-all ${
                    contact.is_overdue ? "border-orange-700/50" : "border-zinc-700"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-white font-medium">{contact.name}</span>
                        {contact.nickname && (
                          <span className="text-zinc-500 text-sm">({contact.nickname})</span>
                        )}
                        <span className="text-xs bg-zinc-700 text-zinc-300 px-2 py-0.5 rounded">
                          {RELATION_LABELS[contact.relationship_type] || contact.relationship_type}
                        </span>
                        {contact.is_overdue && (
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            contact.overdue_days && contact.overdue_days > 14
                              ? "bg-red-900/60 text-red-300"
                              : "bg-orange-900/60 text-orange-300"
                          }`}>
                            ⚠️ {contact.overdue_days ? `${contact.overdue_days}d überfällig` : "nie kontaktiert"}
                          </span>
                        )}
                      </div>
                      <div className="text-zinc-500 text-xs mt-1">
                        Ziel: alle {contact.contact_frequency_days} Tage
                        {contact.last_contacted_at && (
                          <> · Zuletzt: {new Date(contact.last_contacted_at).toLocaleDateString("de-DE")}</>
                        )}
                        {contact.birthday && (
                          <> · 🎂 {new Date(contact.birthday + "T00:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "long" })}</>
                        )}
                      </div>
                      {contact.notes && (
                        <div className="text-zinc-400 text-xs mt-1.5 bg-zinc-800/60 rounded-lg px-2.5 py-1.5 leading-relaxed">
                          📝 {contact.notes}
                        </div>
                      )}
                      {(contact.phone || contact.email) && (
                        <div className="text-zinc-500 text-xs mt-1 flex gap-3">
                          {contact.phone && <span>📞 {contact.phone}</span>}
                          {contact.email && <span>✉️ {contact.email}</span>}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => setInteractionContactId(contact.id)}
                        title="Interaktion loggen"
                        className="p-1.5 text-zinc-400 hover:text-indigo-400 transition-colors"
                      >
                        <PhoneCall size={16} />
                      </button>
                      <button
                        onClick={() => deleteContact(contact.id)}
                        title="Löschen"
                        className="p-1.5 text-zinc-400 hover:text-red-400 transition-colors"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Commitments Tab */}
      {activeTab === "commitments" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowNewCommitment(!showNewCommitment)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm flex items-center gap-2 transition-colors"
            >
              <Plus size={16} />
              Neue Zusage
            </button>
          </div>

          {/* New Commitment Form */}
          {showNewCommitment && (
            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 space-y-3">
              <h3 className="text-white font-semibold">Neue Zusage</h3>
              <input
                value={newCommitment.description}
                onChange={(e) => setNewCommitment((p) => ({ ...p, description: e.target.value }))}
                placeholder="Beschreibung *"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
              />
              <div className="grid grid-cols-2 gap-3">
                <select
                  value={newCommitment.contact_id}
                  onChange={(e) => setNewCommitment((p) => ({ ...p, contact_id: e.target.value }))}
                  className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                >
                  <option value="">Kein Kontakt</option>
                  {contacts.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <input
                  type="date"
                  value={newCommitment.due_date}
                  onChange={(e) => setNewCommitment((p) => ({ ...p, due_date: e.target.value }))}
                  className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex gap-2">
                <button onClick={createCommitment} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm transition-colors">
                  Erstellen
                </button>
                <button onClick={() => setShowNewCommitment(false)} className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors">
                  Abbrechen
                </button>
              </div>
            </div>
          )}

          {/* Commitments List */}
          {commitments.length === 0 ? (
            <div className="text-center py-16 text-zinc-500">
              <CheckSquare size={48} className="mx-auto mb-4 opacity-30" />
              <p>Keine offenen Zusagen.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {commitments.map((cm) => (
                <div
                  key={cm.id}
                  className={`flex items-start gap-3 p-3 rounded-xl border transition-all ${
                    cm.status === "done"
                      ? "bg-zinc-900/50 border-zinc-800 opacity-50"
                      : cm.status === "overdue"
                      ? "bg-red-900/10 border-red-700/40"
                      : "bg-zinc-900 border-zinc-700"
                  }`}
                >
                  <button
                    onClick={() => cm.status !== "done" && markCommitmentDone(cm.id)}
                    className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      cm.status === "done"
                        ? "bg-green-600 border-green-600"
                        : "border-zinc-500 hover:border-indigo-500"
                    }`}
                  >
                    {cm.status === "done" && <span className="text-white text-xs">✓</span>}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm ${cm.status === "done" ? "line-through text-zinc-500" : "text-white"}`}>
                      {cm.description}
                    </div>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {cm.contact_name && (
                        <span className="text-xs text-zinc-400">{cm.contact_name}</span>
                      )}
                      {cm.due_date && (
                        <span className={`text-xs ${cm.status === "overdue" ? "text-red-400" : "text-zinc-400"}`}>
                          <Calendar size={11} className="inline mr-1" />
                          {new Date(cm.due_date).toLocaleDateString("de-DE")}
                          {cm.status === "overdue" && " ⚠️"}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => deleteCommitment(cm.id)}
                    className="p-1 text-zinc-500 hover:text-red-400 transition-colors flex-shrink-0"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
