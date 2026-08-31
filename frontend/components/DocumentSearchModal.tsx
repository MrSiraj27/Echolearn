"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search } from "lucide-react";
import { api, ApiError } from "@/lib/api";

interface SearchResult {
  text: string;
  page_number: number | null;
  score: number;
}

export default function DocumentSearchModal({
  documentId,
  filename,
  onClose,
}: {
  documentId: string;
  filename: string;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<SearchResult[]>(
          `/documents/${documentId}/search?q=${encodeURIComponent(query)}`,
          { auth: true }
        );
        setResults(data);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Search failed.");
      } finally {
        setLoading(false);
        setSearched(true);
      }
    }, 350);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, documentId]);

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24 px-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-lg bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden"
        initial={{ opacity: 0, y: -10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-800 flex items-center gap-2">
          <Search className="h-4 w-4 text-neutral-400 dark:text-neutral-500 shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-xs text-neutral-400 dark:text-neutral-500 mb-1.5 truncate">Searching in {filename}</p>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search this document..."
              className="w-full text-sm outline-none bg-transparent text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 dark:placeholder:text-neutral-500"
            />
          </div>
        </div>

        <div className="max-h-96 overflow-y-auto">
          {loading && <p className="text-sm text-neutral-400 dark:text-neutral-500 px-4 py-6 text-center">Searching...</p>}
          {error && <p className="text-sm text-red-600 dark:text-red-400 px-4 py-6 text-center">{error}</p>}
          {!loading && !error && searched && results.length === 0 && (
            <p className="text-sm text-neutral-400 dark:text-neutral-500 px-4 py-6 text-center">No matches found.</p>
          )}
          <AnimatePresence initial={false}>
            {!loading &&
              results.map((r, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="px-4 py-3 border-b border-neutral-50 dark:border-neutral-800/60 last:border-0"
                >
                  <div className="flex items-center justify-between mb-1">
                    {r.page_number != null && (
                      <span className="text-[11px] font-medium text-neutral-400 dark:text-neutral-500">
                        Page {r.page_number}
                      </span>
                    )}
                    <span className="text-[11px] text-neutral-300 dark:text-neutral-600">
                      {Math.round(r.score * 100)}% match
                    </span>
                  </div>
                  <p className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed line-clamp-3">
                    {r.text}
                  </p>
                </motion.div>
              ))}
          </AnimatePresence>
        </div>

        <div className="px-4 py-2 border-t border-neutral-100 dark:border-neutral-800 text-[11px] text-neutral-400 dark:text-neutral-500">
          Press Esc to close
        </div>
      </motion.div>
    </motion.div>
  );
}
