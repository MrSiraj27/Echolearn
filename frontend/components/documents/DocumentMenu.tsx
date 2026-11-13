"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  FolderInput,
  GraduationCap,
  Loader2,
  MessageSquare,
  MoreVertical,
  Pencil,
  RotateCcw,
  ScrollText,
  Search,
  Trash2,
} from "lucide-react";
import { useChatStore } from "@/lib/chat-store";
import type { DocumentItem } from "@/lib/types";
import { isReady } from "@/components/documents/docUi";

/** The "⋯" menu on a document: every action in one labelled list. */
export default function DocumentMenu({
  doc,
  onRename,
  onRevise,
  onSearch,
  onMove,
  align = "right",
}: {
  doc: DocumentItem;
  onRename?: () => void;
  onRevise?: () => void;
  onSearch?: () => void;
  onMove?: () => void;
  align?: "left" | "right";
}) {
  const router = useRouter();
  const createChat = useChatStore((s) => s.createChat);
  const deleteDocument = useChatStore((s) => s.deleteDocument);
  const retryDocument = useChatStore((s) => s.retryDocument);
  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const ready = isReady(doc);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setConfirmDelete(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  const item = "flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px] text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 dark:text-neutral-200 dark:hover:bg-neutral-800";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
          setConfirmDelete(false);
        }}
        className="rounded-lg p-1.5 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
        aria-label={`Actions for ${doc.filename}`}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreVertical className="h-4 w-4" />
      </button>
      {open && (
        <div
          role="menu"
          onClick={(e) => e.stopPropagation()}
          className={`absolute top-9 z-40 w-56 overflow-hidden rounded-xl border border-neutral-200 bg-white py-1 shadow-xl dark:border-neutral-700 dark:bg-neutral-900 ${align === "right" ? "right-0" : "left-0"}`}
        >
          {ready && (
            <>
              <button role="menuitem" className={item} onClick={() => router.push(`/read/${doc.id}`)}>
                <BookOpen className="h-4 w-4" /> Read
              </button>
              <button
                role="menuitem"
                className={item}
                disabled={busy !== null}
                onClick={() => run("chat", async () => router.push(`/chat/${await createChat([doc.id], doc.filename)}`))}
              >
                {busy === "chat" ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquare className="h-4 w-4" />} Chat about it
              </button>
              <button role="menuitem" className={item} onClick={() => router.push(`/tutor?doc=${doc.id}`)}>
                <GraduationCap className="h-4 w-4" /> Learn with the tutor
              </button>
              {onRevise && (
                <button role="menuitem" className={item} onClick={() => { setOpen(false); onRevise(); }}>
                  <ScrollText className="h-4 w-4" /> Make a revision sheet
                </button>
              )}
              {onSearch && (
                <button role="menuitem" className={item} onClick={() => { setOpen(false); onSearch(); }}>
                  <Search className="h-4 w-4" /> Search inside
                </button>
              )}
              <div className="my-1 border-t border-neutral-100 dark:border-neutral-800" />
            </>
          )}
          {doc.status === "failed" && (
            <button role="menuitem" className={item} disabled={busy !== null} onClick={() => run("retry", () => retryDocument(doc.id))}>
              {busy === "retry" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />} Try processing again
            </button>
          )}
          {onRename && (
            <button role="menuitem" className={item} onClick={() => { setOpen(false); onRename(); }}>
              <Pencil className="h-4 w-4" /> Rename
            </button>
          )}
          {onMove && (
            <button role="menuitem" className={item} onClick={() => { setOpen(false); onMove(); }}>
              <FolderInput className="h-4 w-4" /> Move to folder
            </button>
          )}
          {confirmDelete ? (
            <div className="px-3.5 py-2">
              <p className="mb-2 text-[12px] text-neutral-600 dark:text-neutral-300">Delete this document and everything made from it? This can&apos;t be undone.</p>
              <div className="flex gap-2">
                <button
                  className="flex-1 rounded-lg bg-red-600 px-2 py-1.5 text-[12px] font-medium text-white hover:bg-red-700 disabled:opacity-60"
                  disabled={busy !== null}
                  onClick={() => run("delete", () => deleteDocument(doc.id))}
                >
                  {busy === "delete" ? "Deleting…" : "Delete"}
                </button>
                <button className="flex-1 rounded-lg border border-neutral-200 px-2 py-1.5 text-[12px] dark:border-neutral-700" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button role="menuitem" className={`${item} text-red-600 dark:text-red-400`} onClick={() => setConfirmDelete(true)}>
              <Trash2 className="h-4 w-4" /> Delete
            </button>
          )}
          {error && <p role="alert" className="px-3.5 pb-2 text-[12px] text-red-600 dark:text-red-400">{error}</p>}
        </div>
      )}
    </div>
  );
}
