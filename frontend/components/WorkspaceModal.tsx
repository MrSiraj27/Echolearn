"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { X, Check, Loader2, FolderKanban } from "lucide-react";
import { DocumentItem, Workspace } from "@/lib/types";

const READY_STATUSES = ["embedded", "ready"];

interface Props {
  documents: DocumentItem[];
  /** When set, the modal manages this existing workspace's document membership
   * instead of creating a new one. */
  workspace?: Workspace;
  workspaceDocumentIds?: string[];
  onCreate?: (name: string, documentIds: string[]) => Promise<void>;
  onToggleDocument?: (documentId: string, isMember: boolean) => Promise<void>;
  onClose: () => void;
}

export default function WorkspaceModal({
  documents,
  workspace,
  workspaceDocumentIds,
  onCreate,
  onToggleDocument,
  onClose,
}: Props) {
  const isEditing = Boolean(workspace);
  const [name, setName] = useState(workspace?.name || "");
  const [selected, setSelected] = useState<Set<string>>(new Set(workspaceDocumentIds || []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const readyDocs = documents.filter((d) => READY_STATUSES.includes(d.status));

  function toggle(docId: string) {
    if (isEditing && onToggleDocument) {
      const isMember = selected.has(docId);
      setSelected((prev) => {
        const next = new Set(prev);
        if (isMember) next.delete(docId);
        else next.add(docId);
        return next;
      });
      onToggleDocument(docId, isMember).catch(() =>
        setError("Couldn't update this workspace. Please try again.")
      );
      return;
    }
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }

  async function handleCreate() {
    const trimmed = name.trim();
    if (!trimmed || !onCreate) return;
    setSaving(true);
    setError(null);
    try {
      await onCreate(trimmed, Array.from(selected));
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create this workspace.");
    } finally {
      setSaving(false);
    }
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
        className="w-full max-w-md max-h-[80vh] bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 flex flex-col overflow-hidden"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100 dark:border-neutral-800">
          <div className="flex items-center gap-2 min-w-0">
            <FolderKanban className="h-4 w-4 text-neutral-400 shrink-0" />
            <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
              {isEditing ? `Manage "${workspace?.name}"` : "New workspace"}
            </p>
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
          {!isEditing && (
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Biology 101"
              className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 mb-4 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
            />
          )}

          <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">
            Documents
          </p>

          {readyDocs.length === 0 && (
            <p className="text-xs text-neutral-400 dark:text-neutral-500">
              No ready documents yet — upload one first.
            </p>
          )}

          <div className="space-y-1">
            {readyDocs.map((doc) => {
              const isSelected = selected.has(doc.id);
              return (
                <button
                  key={doc.id}
                  onClick={() => toggle(doc.id)}
                  className={`w-full flex items-center justify-between gap-2 text-left text-sm px-3 py-2 rounded-lg border transition-colors ${
                    isSelected
                      ? "border-neutral-900 dark:border-neutral-100 bg-neutral-50 dark:bg-neutral-800"
                      : "border-neutral-200 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  <span className="truncate text-neutral-700 dark:text-neutral-300">{doc.filename}</span>
                  {isSelected && <Check className="h-3.5 w-3.5 shrink-0 text-neutral-900 dark:text-neutral-100" />}
                </button>
              );
            })}
          </div>

          {error && <p className="text-xs text-red-600 dark:text-red-400 mt-3">{error}</p>}
        </div>

        {!isEditing && (
          <div className="px-4 py-3 border-t border-neutral-100 dark:border-neutral-800">
            <button
              onClick={handleCreate}
              disabled={saving || !name.trim()}
              className="w-full flex items-center justify-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
            >
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create workspace
            </button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
