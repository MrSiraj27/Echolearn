"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ClipboardList, Loader2, Plus, Trash2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { patternBadgeText } from "@/lib/practice";
import { PracticePaperListItem } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  ready: "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400",
  generating: "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
  failed: "bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400",
};

export default function PracticePapersPage() {
  const router = useRouter();
  const [papers, setPapers] = useState<PracticePaperListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<PracticePaperListItem[]>("/practice-papers/", { auth: true })
      .then(setPapers)
      .catch(() => setError("Couldn't load your practice papers."))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(paper: PracticePaperListItem) {
    if (!window.confirm(`Delete "${paper.title}"? This can't be undone.`)) return;
    setDeletingId(paper.id);
    setError(null);
    try {
      await api.delete(`/practice-papers/${paper.id}`, { auth: true });
      setPapers((prev) => prev.filter((p) => p.id !== paper.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't delete this paper.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
                Practice Papers
              </h1>
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                AI-generated practice exams built from your study material, ready to print as a PDF.
              </p>
            </div>
            <Link
              href="/practice-papers/new"
              className="shrink-0 flex items-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3.5 py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
            >
              <Plus className="h-4 w-4" />
              New Paper
            </Link>
          </div>

          {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}
          {loading && <p className="text-sm text-neutral-400">Loading...</p>}

          {!loading && papers.length === 0 && !error && (
            <div className="rounded-2xl border border-dashed border-neutral-300 dark:border-neutral-700 p-8 text-center">
              <ClipboardList className="h-6 w-6 text-neutral-400 mx-auto mb-2" />
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                No practice papers yet. Create one to get a printable practice exam and answer key.
              </p>
            </div>
          )}

          <div className="space-y-2">
            {papers.map((paper) => (
              <div
                key={paper.id}
                className="group flex items-start gap-2 rounded-xl border border-neutral-200 dark:border-neutral-800 p-4 hover:bg-neutral-50 dark:hover:bg-neutral-900 transition-colors"
              >
                <Link href={`/practice-papers/${paper.id}`} className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
                      {paper.title}
                    </p>
                    <span
                      className={`shrink-0 flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${STATUS_STYLE[paper.status]}`}
                    >
                      {paper.status === "generating" && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                      {paper.status}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-400">
                    {patternBadgeText(paper.pattern_source, paper.pattern_note)}
                    {paper.total_questions != null && ` · ${paper.total_questions} questions`}
                    {paper.total_marks != null && ` · ${paper.total_marks} marks`}
                    {" · "}
                    {new Date(paper.created_at).toLocaleDateString()}
                  </p>
                  {paper.status === "failed" && paper.error_message && (
                    <p className="text-xs text-red-600 dark:text-red-400 mt-1.5">{paper.error_message}</p>
                  )}
                </Link>
                <button
                  onClick={() => handleDelete(paper)}
                  disabled={deletingId === paper.id}
                  aria-label={`Delete ${paper.title}`}
                  className="shrink-0 p-1.5 text-neutral-400 hover:text-red-600 dark:hover:text-red-400 transition-colors disabled:opacity-50"
                >
                  {deletingId === paper.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
              </div>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
