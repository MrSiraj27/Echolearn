"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { FolderInput, Check } from "lucide-react";
import { Folder } from "@/lib/types";

export default function MoveToFolderMenu({
  folders,
  currentFolderId,
  onMove,
  onCreateFolder,
}: {
  folders: Folder[];
  currentFolderId: string | null | undefined;
  onMove: (folderId: string | null) => void;
  onCreateFolder: (name: string) => Promise<Folder>;
}) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setCreating(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  useEffect(() => {
    if (!open) return;
    function reposition() {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPosition({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
    }
    reposition();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [open]);

  async function handleCreateAndMove() {
    const name = newName.trim();
    if (!name) return;
    const folder = await onCreateFolder(name);
    onMove(folder.id);
    setNewName("");
    setCreating(false);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 p-0.5 transition-opacity"
        aria-label="Move to folder"
      >
        <FolderInput className="h-3.5 w-3.5" />
      </button>

      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {open && position && (
              <motion.div
                ref={menuRef}
                initial={{ opacity: 0, y: -4, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.97 }}
                transition={{ duration: 0.12 }}
                onClick={(e) => e.stopPropagation()}
                style={{ position: "fixed", top: position.top, right: position.right }}
                className="w-48 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-lg overflow-hidden z-50"
              >
                <button
                  onClick={() => {
                    onMove(null);
                    setOpen(false);
                  }}
                  className="w-full flex items-center justify-between text-left text-xs text-neutral-700 dark:text-neutral-200 px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
                >
                  No folder
                  {!currentFolderId && <Check className="h-3.5 w-3.5" />}
                </button>
                {folders.length > 0 && <div className="border-t border-neutral-100 dark:border-neutral-700" />}
                <div className="max-h-48 overflow-y-auto">
                  {folders.map((folder) => (
                    <button
                      key={folder.id}
                      onClick={() => {
                        onMove(folder.id);
                        setOpen(false);
                      }}
                      className="w-full flex items-center justify-between text-left text-xs text-neutral-700 dark:text-neutral-200 px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
                    >
                      <span className="truncate">{folder.name}</span>
                      {currentFolderId === folder.id && <Check className="h-3.5 w-3.5 shrink-0" />}
                    </button>
                  ))}
                </div>
                <div className="border-t border-neutral-100 dark:border-neutral-700">
                  {creating ? (
                    <div className="p-2 flex gap-1">
                      <input
                        autoFocus
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleCreateAndMove()}
                        placeholder="Folder name"
                        className="flex-1 min-w-0 text-xs rounded border border-neutral-200 dark:border-neutral-600 bg-transparent px-1.5 py-1 outline-none text-neutral-900 dark:text-neutral-100"
                      />
                      <button
                        onClick={handleCreateAndMove}
                        className="text-xs font-medium text-neutral-900 dark:text-neutral-100 px-1.5"
                      >
                        Add
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setCreating(true)}
                      className="w-full text-left text-xs text-neutral-500 dark:text-neutral-400 px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
                    >
                      + New folder
                    </button>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>,
          document.body
        )}
    </div>
  );
}
