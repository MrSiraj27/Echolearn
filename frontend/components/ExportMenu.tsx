"use client";

import { useState, useRef, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Download, Loader2 } from "lucide-react";
import { getAccessToken } from "@/lib/api";

export default function ExportMenu({ chatId, chatTitle }: { chatId: string; chatTitle: string | null }) {
  const [open, setOpen] = useState(false);
  const [loadingFormat, setLoadingFormat] = useState<"markdown" | "pdf" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function handleExport(format: "markdown" | "pdf") {
    setLoadingFormat(format);
    setError(null);
    setOpen(false);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const token = getAccessToken();
      const res = await fetch(`${apiUrl}/chats/${chatId}/export?format=${format}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Export failed. Please try again.");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const safeTitle = (chatTitle || "echolearn_chat").replace(/[^\w\-]+/g, "_");
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safeTitle}.${format === "markdown" ? "md" : "pdf"}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setLoadingFormat(null);
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={loadingFormat !== null}
        className="text-xs font-medium text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50 flex items-center gap-1.5"
      >
        {loadingFormat ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
        <span className="hidden sm:inline">Export</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 mt-1.5 w-40 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-lg overflow-hidden z-20"
          >
            <button
              onClick={() => handleExport("markdown")}
              className="w-full text-left text-xs text-neutral-700 dark:text-neutral-200 px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
            >
              Markdown (.md)
            </button>
            <button
              onClick={() => handleExport("pdf")}
              className="w-full text-left text-xs text-neutral-700 dark:text-neutral-200 px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors border-t border-neutral-100 dark:border-neutral-700"
            >
              PDF (.pdf)
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <p className="absolute right-0 top-full mt-1 text-[11px] text-red-600 dark:text-red-400 whitespace-nowrap">
          {error}
        </p>
      )}
    </div>
  );
}
