"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { ArrowLeft, Loader2, Plus, ScrollText, Trash2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import RevisionSheetModal from "@/components/RevisionSheetModal";
import { api, ApiError } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { LANGUAGE_NAMES } from "@/lib/revision";
import { RevisionSheetListItem } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  ready: "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400",
  queued: "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
  generating: "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
  failed: "bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400",
};

export default function RevisionSheetsPage() {
  const router = useRouter();
  const documents = useChatStore((s) => s.documents);
  const loadDocuments = useChatStore((s) => s.loadDocuments);
  const [sheets, setSheets] = useState<RevisionSheetListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    api
      .get<RevisionSheetListItem[]>("/revision-sheets/", { auth: true })
      .then(setSheets)
      .catch(() => setError("Couldn't load your revision sheets."))
      .finally(() => setLoading(false));
    loadDocuments().catch(() => {});
  }, [loadDocuments]);

  async function handleDelete(sheet: RevisionSheetListItem) {
    if (!window.confirm(`Delete "${sheet.title}"? This can't be undone.`)) return;
    setDeletingId(sheet.id);
    setError(null);
    try {
      await api.delete(`/revision-sheets/${sheet.id}`, { auth: true });
      setSheets((prev) => prev.filter((s) => s.id !== sheet.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't delete this sheet.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 pt-16 lg:pt-8">
          <button
            onClick={() => router.push("/chat")}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to chat
          </button>

          <div className="flex items-start justify-between gap-3 mb-1">
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
              Revision sheets
            </h1>
            <button
              onClick={() => setShowModal(true)}
              className="shrink-0 flex items-center gap-1.5 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              New sheet
            </button>
          </div>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
            One-page cheat sheets of the key definitions, formulas and facts from your material. Perfect for the night
            before an exam.
          </p>

          {error && <p className="text-xs text-red-600 dark:text-red-400 mb-3">{error}</p>}

          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin text-neutral-400" />
          ) : sheets.length === 0 ? (
            <div className="rounded-xl border border-dashed border-neutral-300 dark:border-neutral-700 px-6 py-10 text-center">
              <ScrollText className="h-6 w-6 mx-auto text-neutral-300 dark:text-neutral-600 mb-2" />
              <p className="text-sm text-neutral-500 dark:text-neutral-400">No revision sheets yet.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {sheets.map((sheet) => (
                <div
                  key={sheet.id}
                  className="flex items-center gap-3 rounded-xl border border-neutral-200 dark:border-neutral-800 px-4 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-900/60 transition-colors"
                >
                  <Link href={`/revision-sheets/${sheet.id}`} className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">{sheet.title}</p>
                    <p className="text-xs text-neutral-400 dark:text-neutral-500">
                      {LANGUAGE_NAMES[sheet.language]} · {sheet.page_target} page{sheet.page_target > 1 ? "s" : ""} ·{" "}
                      {new Date(sheet.created_at).toLocaleDateString()}
                    </p>
                  </Link>
                  <span
                    className={`text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 ${STATUS_STYLE[sheet.status]}`}
                  >
                    {sheet.status === "queued" || sheet.status === "generating"
                      ? "Generating…"
                      : sheet.status === "ready"
                        ? "Ready"
                        : "Failed"}
                  </span>
                  <button
                    onClick={() => handleDelete(sheet)}
                    disabled={deletingId === sheet.id}
                    aria-label={`Delete ${sheet.title}`}
                    className="text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-1 shrink-0"
                  >
                    {deletingId === sheet.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      <AnimatePresence>
        {showModal && <RevisionSheetModal documents={documents} onClose={() => setShowModal(false)} />}
      </AnimatePresence>
    </>
  );
}
