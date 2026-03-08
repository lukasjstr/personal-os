"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import Header from "@/components/Header";
import LoadingSpinner, { ErrorState, EmptyState } from "@/components/LoadingSpinner";
import ConfirmDialog from "@/components/ConfirmDialog";
import { ToastContainer, useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CheckCircle, XCircle, Trash2, Zap } from "lucide-react";

type ProposalDraft = {
  id: number;
  source_text: string;
  draft_payload: unknown;
  status: string;
  created_at: string;
  executed_at?: string | null;
};

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-yellow-900/40 text-yellow-400 border-yellow-800/50",
  accepted: "bg-green-900/40 text-green-400 border-green-800/50",
  rejected: "bg-red-900/40 text-red-400 border-red-800/50",
  executed: "bg-blue-900/40 text-blue-400 border-blue-800/50",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Ausstehend",
  accepted: "Akzeptiert",
  rejected: "Abgelehnt",
  executed: "Ausgeführt",
};

async function fetchDrafts(): Promise<ProposalDraft[]> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("api_token") : null;
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
  const res = await fetch(`${apiUrl}/api/objectives/proposal-drafts`, {
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export default function ProposalsPage() {
  const { data: drafts, error, isLoading, mutate } = useSWR<ProposalDraft[]>(
    "proposal-drafts",
    fetchDrafts,
    { refreshInterval: 60_000 }
  );
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<ProposalDraft | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const handleReview = useCallback(
    async (id: number, action: "accept" | "reject") => {
      setActionLoading(id);
      try {
        await api.apiReviewProposal(id, action);
        await mutate();
        addToast(action === "accept" ? "Proposal akzeptiert" : "Proposal abgelehnt", "success");
      } catch {
        addToast("Fehler bei der Aktion", "error");
      } finally {
        setActionLoading(null);
      }
    },
    [mutate, addToast]
  );

  const handleDelete = useCallback(async () => {
    if (!confirmDelete) return;
    setDeletingId(confirmDelete.id);
    try {
      await api.deleteProposalDraft(confirmDelete.id);
      await mutate();
      addToast("Proposal gelöscht", "success");
      setConfirmDelete(null);
    } catch {
      addToast("Fehler beim Löschen", "error");
    } finally {
      setDeletingId(null);
    }
  }, [confirmDelete, mutate, addToast]);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message={error.message} />;

  const list = drafts ?? [];
  const pending = list.filter((d) => d.status === "pending").length;

  return (
    <div>
      <Header
        title="📋 Proposals"
        subtitle={`${list.length} Proposals · ${pending} ausstehend`}
      />

      {list.length === 0 ? (
        <EmptyState emoji="📋" message="Keine Proposals vorhanden" />
      ) : (
        <div className="space-y-4">
          {list.map((d) => (
            <div
              key={d.id}
              className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden"
            >
              {/* Card header */}
              <div className="flex items-start justify-between gap-4 p-5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-semibold text-sm">Draft #{d.id}</span>
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded-full border font-medium",
                        STATUS_STYLE[d.status] ?? "bg-zinc-800 text-zinc-400 border-zinc-700"
                      )}
                    >
                      {STATUS_LABEL[d.status] ?? d.status}
                    </span>
                  </div>
                  <div className="text-zinc-500 text-xs">
                    {new Date(d.created_at).toLocaleString("de-DE")}
                    {d.executed_at && (
                      <span className="ml-2 text-blue-400">
                        · Ausgeführt {new Date(d.executed_at).toLocaleString("de-DE")}
                      </span>
                    )}
                  </div>
                </div>
                {/* Delete button */}
                <button
                  onClick={() => setConfirmDelete(d)}
                  disabled={deletingId === d.id}
                  className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-zinc-800 transition-colors shrink-0"
                  title="Löschen"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              {/* Source text */}
              <div className="px-5 pb-3">
                <div className="text-zinc-500 text-xs uppercase tracking-wide mb-1.5">Source</div>
                <pre className="bg-zinc-800/60 border border-zinc-700/50 rounded-lg p-3 text-zinc-300 text-xs overflow-auto max-h-40 whitespace-pre-wrap break-words">
                  {d.source_text}
                </pre>
              </div>

              {/* Actions */}
              {d.status === "pending" && (
                <div className="px-5 pb-4 flex gap-2">
                  <button
                    onClick={() => handleReview(d.id, "accept")}
                    disabled={actionLoading === d.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded-lg text-sm text-white font-medium transition-colors"
                  >
                    <CheckCircle size={14} />
                    {actionLoading === d.id ? "..." : "Akzeptieren"}
                  </button>
                  <button
                    onClick={() => handleReview(d.id, "reject")}
                    disabled={actionLoading === d.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 rounded-lg text-sm text-white font-medium transition-colors"
                  >
                    <XCircle size={14} />
                    {actionLoading === d.id ? "..." : "Ablehnen"}
                  </button>
                </div>
              )}

              {d.status === "accepted" && (
                <div className="px-5 pb-4">
                  <button
                    onClick={async () => {
                      setActionLoading(d.id);
                      try {
                        await api.executeProposalDraft(d.id);
                        await mutate();
                        addToast("Proposal ausgeführt", "success");
                      } catch {
                        addToast("Fehler beim Ausführen", "error");
                      } finally {
                        setActionLoading(null);
                      }
                    }}
                    disabled={actionLoading === d.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm text-white font-medium transition-colors"
                  >
                    <Zap size={14} />
                    {actionLoading === d.id ? "Ausführen..." : "Ausführen (Execute)"}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!confirmDelete}
        title="Proposal löschen?"
        message={`Draft #${confirmDelete?.id} wird dauerhaft gelöscht.`}
        loading={deletingId !== null}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
