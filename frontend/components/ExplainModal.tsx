"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

export default function ExplainModal({
  selectedText,
  loading,
  explanation,
  error,
  onClose,
}: {
  selectedText: string;
  loading: boolean;
  explanation: string | null;
  error: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-md bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-neutral-100 dark:border-neutral-800">
          <p className="text-[11px] font-medium text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1">
            You highlighted
          </p>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 italic line-clamp-2">&ldquo;{selectedText}&rdquo;</p>
        </div>

        <div className="px-4 py-4 max-h-80 overflow-y-auto">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-neutral-400 dark:text-neutral-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Explaining...
            </div>
          )}
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          {explanation && (
            <p className="text-sm text-neutral-800 dark:text-neutral-200 leading-relaxed whitespace-pre-wrap">
              {explanation}
            </p>
          )}
        </div>

        <div className="px-4 py-2 border-t border-neutral-100 dark:border-neutral-800 text-[11px] text-neutral-400 dark:text-neutral-500">
          Press Esc to close
        </div>
      </motion.div>
    </motion.div>
  );
}
