"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Folder as FolderIcon, FileText, Loader2 } from "lucide-react";
import { DocumentItem, Folder } from "@/lib/types";

export default function SelectChatScopeModal({
  documents,
  folders,
  onConfirm,
  onClose,
}: {
  documents: DocumentItem[];
  folders: Folder[];
  onConfirm: (documentIds: string[]) => void | Promise<void>;
  onClose: () => void;
}) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [starting, setStarting] = useState(false);

  const unfiled = documents.filter((d) => !d.folder_id);
  const groups = folders.map((folder) => ({
    folder,
    docs: documents.filter((d) => d.folder_id === folder.id),
  }));

  function toggleDoc(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  }

  function toggleFolder(docIds: string[]) {
    const allSelected = docIds.every((id) => selectedIds.includes(id));
    setSelectedIds((prev) =>
      allSelected ? prev.filter((id) => !docIds.includes(id)) : [...new Set([...prev, ...docIds])]
    );
  }

  async function handleConfirm() {
    setStarting(true);
    await onConfirm(selectedIds);
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
        className="w-full max-w-md bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-neutral-100 dark:border-neutral-800">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            What should this chat cover?
          </h2>
          <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-0.5">
            Pick a folder to chat with everything inside it, or select individual documents.
          </p>
        </div>

        <div className="px-5 py-4 max-h-[55vh] overflow-y-auto space-y-4">
          {groups.map(({ folder, docs }) => {
            const docIds = docs.map((d) => d.id);
            const allSelected = docIds.length > 0 && docIds.every((id) => selectedIds.includes(id));
            return (
              <div key={folder.id}>
                <label className="flex items-center gap-2 text-sm font-medium text-neutral-800 dark:text-neutral-200 cursor-pointer mb-1.5">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() => toggleFolder(docIds)}
                    disabled={docIds.length === 0}
                    className="accent-neutral-900 dark:accent-neutral-100"
                  />
                  <FolderIcon className="h-3.5 w-3.5 text-neutral-400" />
                  {folder.name}
                  <span className="text-xs text-neutral-400 font-normal">({docs.length})</span>
                </label>
                <div className="ml-6 space-y-1">
                  {docs.map((doc) => (
                    <label
                      key={doc.id}
                      className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(doc.id)}
                        onChange={() => toggleDoc(doc.id)}
                        className="accent-neutral-900 dark:accent-neutral-100"
                      />
                      <FileText className="h-3 w-3 shrink-0" />
                      <span className="truncate">{doc.filename}</span>
                    </label>
                  ))}
                </div>
              </div>
            );
          })}

          {unfiled.length > 0 && (
            <div>
              {folders.length > 0 && (
                <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1.5">
                  Unfiled
                </p>
              )}
              <div className="space-y-1">
                {unfiled.map((doc) => (
                  <label
                    key={doc.id}
                    className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(doc.id)}
                      onChange={() => toggleDoc(doc.id)}
                      className="accent-neutral-900 dark:accent-neutral-100"
                    />
                    <FileText className="h-3 w-3 shrink-0" />
                    <span className="truncate">{doc.filename}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {documents.length === 0 && (
            <p className="text-xs text-neutral-400 dark:text-neutral-500">
              No documents yet — upload one from the sidebar first.
            </p>
          )}
        </div>

        <div className="px-5 py-3 border-t border-neutral-100 dark:border-neutral-800 flex items-center justify-between gap-2">
          <p className="text-xs text-neutral-400 dark:text-neutral-500">
            {selectedIds.length === 0 ? "No documents selected" : `${selectedIds.length} selected`}
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="text-xs font-medium text-neutral-600 dark:text-neutral-400 px-3 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={starting}
              className="text-xs font-medium text-white dark:text-neutral-900 bg-neutral-900 dark:bg-neutral-100 px-3.5 py-1.5 rounded-lg hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {starting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Start chat
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
