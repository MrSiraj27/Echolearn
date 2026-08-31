"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { X, ArrowLeft, ArrowRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Citation } from "@/lib/types";

interface PageContent {
  page_number: number;
  text: string;
  total_pages: number;
  highlight_start: number | null;
  highlight_end: number | null;
}

export default function SourceViewer({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const [page, setPage] = useState<number>(citation.page_number || 1);
  const [content, setContent] = useState<PageContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!citation.document_id) return;
    setLoading(true);
    setError(null);

    // Only ask the backend to highlight the cited chunk on the page it actually came
    // from — navigating to another page should show plain text, not a stale highlight.
    const isOriginalPage = page === citation.page_number;

    api
      .post<PageContent>(
        `/documents/${citation.document_id}/page/${page}`,
        isOriginalPage ? { chunk_text: citation.chunk_text } : {},
        { auth: true }
      )
      .then(setContent)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load this page."))
      .finally(() => setLoading(false));
  }, [citation.document_id, citation.page_number, citation.chunk_text, page]);

  function renderHighlightedText() {
    if (!content) return null;
    const { text, highlight_start, highlight_end } = content;
    if (highlight_start == null || highlight_end == null) {
      return <span>{text}</span>;
    }
    return (
      <>
        {text.slice(0, highlight_start)}
        <mark className="bg-amber-200/70 dark:bg-amber-400/30 dark:text-amber-100 rounded px-0.5">
          {text.slice(highlight_start, highlight_end)}
        </mark>
        {text.slice(highlight_end)}
      </>
    );
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-xl max-h-[80vh] bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 flex flex-col overflow-hidden"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100 dark:border-neutral-800">
          <div className="min-w-0">
            <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">{citation.filename}</p>
            {content && (
              <p className="text-xs text-neutral-400 dark:text-neutral-500">
                Page {content.page_number} of {content.total_pages}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 shrink-0 ml-2"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          {loading && <p className="text-sm text-neutral-400 dark:text-neutral-500">Loading...</p>}
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          {!loading && !error && content && (
            <p className="text-sm text-neutral-800 dark:text-neutral-200 leading-relaxed whitespace-pre-wrap">
              {renderHighlightedText()}
            </p>
          )}
        </div>

        {content && content.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-neutral-100 dark:border-neutral-800">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="flex items-center gap-1 text-xs font-medium text-neutral-600 dark:text-neutral-400 disabled:opacity-30 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <span className="text-xs text-neutral-400 dark:text-neutral-500">
              Page {page} of {content.total_pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(content.total_pages, p + 1))}
              disabled={page >= content.total_pages}
              className="flex items-center gap-1 text-xs font-medium text-neutral-600 dark:text-neutral-400 disabled:opacity-30 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
            >
              Next
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
