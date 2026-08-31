"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { FolderPlus, Folder as FolderIcon, ArrowLeft, ArrowRight, Loader2, Link2, X } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import SelectChatScopeModal from "@/components/SelectChatScopeModal";
import { useChatStore } from "@/lib/chat-store";
import { getAccessToken } from "@/lib/api";
import { AUDIO_VIDEO_EXTENSIONS } from "@/lib/types";

const READY_STATUSES = ["embedded", "ready"];

export default function ChatWelcomePage() {
  const router = useRouter();
  const {
    createChat,
    documents,
    folders,
    loadDocuments,
    loadFolders,
    createFolder,
    pollDocumentStatus,
    addDocumentFromUrl,
  } = useChatStore();

  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [newFolderName, setNewFolderName] = useState("");
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [folderError, setFolderError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [startingChat, setStartingChat] = useState(false);
  const [showAdvancedModal, setShowAdvancedModal] = useState(false);
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDocuments();
    loadFolders();
  }, [loadDocuments, loadFolders]);

  const selectedFolder = folders.find((f) => f.id === selectedFolderId) || null;
  const folderDocs = selectedFolderId ? documents.filter((d) => d.folder_id === selectedFolderId) : [];
  const readyCount = folderDocs.filter((d) => READY_STATUSES.includes(d.status)).length;

  async function handleCreateFolder() {
    const name = newFolderName.trim();
    if (!name) return;
    setCreatingFolder(true);
    setFolderError(null);
    try {
      const folder = await createFolder(name);
      setNewFolderName("");
      setSelectedFolderId(folder.id);
    } catch (err) {
      setFolderError(err instanceof Error ? err.message : "Couldn't create that folder.");
    } finally {
      setCreatingFolder(false);
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0 || !selectedFolderId) return;
    const file = files[0];
    setUploadError(null);
    setUploading(true);

    try {
      const token = getAccessToken();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const formData = new FormData();
      formData.append("file", file);
      formData.append("folder_id", selectedFolderId);

      const res = await fetch(`${apiUrl}/documents/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Upload failed");
      }

      const data = await res.json();
      await loadDocuments();
      pollDocumentStatus(data.document_id);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleAddFromUrl() {
    const url = videoUrl.trim();
    if (!url || !selectedFolderId) return;
    setUrlSubmitting(true);
    setUrlError(null);
    try {
      await addDocumentFromUrl(url, selectedFolderId);
      setVideoUrl("");
      setShowUrlInput(false);
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : "Couldn't add that video.");
    } finally {
      setUrlSubmitting(false);
    }
  }

  async function handleStartChat() {
    if (!selectedFolderId) return;
    setStartingChat(true);
    const readyIds = folderDocs.filter((d) => READY_STATUSES.includes(d.status)).map((d) => d.id);
    const id = await createChat(readyIds);
    router.push(`/chat/${id}`);
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 flex items-center justify-center px-6 pt-16 pb-8 lg:py-6 bg-white dark:bg-neutral-950 overflow-y-auto">
        <div className="max-w-md w-full">
          <AnimatePresence mode="wait">
            {!selectedFolderId ? (
              <motion.div
                key="pick-folder"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
              >
                <div className="text-center mb-6">
                  <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
                    Start with a folder
                  </h1>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1.5">
                    Group related documents into a folder, then chat with everything inside it at once.
                  </p>
                </div>

                {folders.length > 0 && (
                  <div className="space-y-1.5 mb-4">
                    {folders.map((folder) => (
                      <button
                        key={folder.id}
                        onClick={() => setSelectedFolderId(folder.id)}
                        className="w-full flex items-center gap-2.5 text-left text-sm text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700 rounded-lg px-3.5 py-2.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
                      >
                        <FolderIcon className="h-4 w-4 text-neutral-400 shrink-0" />
                        <span className="truncate flex-1">{folder.name}</span>
                        <span className="text-xs text-neutral-400 shrink-0">{folder.document_count} docs</span>
                      </button>
                    ))}
                  </div>
                )}

                <div className="border border-dashed border-neutral-300 dark:border-neutral-700 rounded-lg p-3.5">
                  <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-2 flex items-center gap-1.5">
                    <FolderPlus className="h-3.5 w-3.5" />
                    New folder
                  </p>
                  <div className="flex gap-2">
                    <input
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleCreateFolder()}
                      placeholder="e.g. Q3 Contracts"
                      className="flex-1 min-w-0 text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2.5 py-1.5 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                    />
                    <button
                      onClick={handleCreateFolder}
                      disabled={creatingFolder || !newFolderName.trim()}
                      className="shrink-0 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {creatingFolder && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                      Create
                    </button>
                  </div>
                  {folderError && <p className="text-xs text-red-600 dark:text-red-400 mt-1.5">{folderError}</p>}
                </div>

                {documents.length > 0 && (
                  <button
                    onClick={() => setShowAdvancedModal(true)}
                    className="w-full text-center text-xs text-neutral-400 dark:text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-200 mt-4 transition-colors"
                  >
                    Or select documents manually across folders →
                  </button>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="add-docs"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }}
                transition={{ duration: 0.2 }}
              >
                <button
                  onClick={() => setSelectedFolderId(null)}
                  className="flex items-center gap-1 text-xs text-neutral-400 dark:text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-200 mb-4 transition-colors"
                >
                  <ArrowLeft className="h-3 w-3" />
                  Choose a different folder
                </button>

                <div className="mb-5">
                  <h1 className="text-lg font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
                    <FolderIcon className="h-4 w-4 text-neutral-400" />
                    {selectedFolder?.name}
                  </h1>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
                    Add the documents that belong together in this folder.
                  </p>
                </div>

                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    handleFiles(e.dataTransfer.files);
                  }}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border border-dashed rounded-xl px-4 py-6 text-center text-sm cursor-pointer transition-colors mb-4 ${
                    dragOver
                      ? "border-neutral-900 dark:border-neutral-100 bg-neutral-100 dark:bg-neutral-800"
                      : "border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => handleFiles(e.target.files)}
                    accept=".pdf,.docx,.pptx,.txt,.csv,.png,.jpg,.jpeg,.mp3,.wav,.m4a,.mp4,.mov"
                  />
                  {uploading ? "Uploading..." : "Drop a file here or click to upload"}
                </div>
                {uploadError && <p className="text-xs text-red-600 dark:text-red-400 mb-3">{uploadError}</p>}

                {showUrlInput ? (
                  <div className="mb-4 space-y-1.5">
                    <div className="flex gap-1.5">
                      <input
                        autoFocus
                        value={videoUrl}
                        onChange={(e) => setVideoUrl(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleAddFromUrl()}
                        placeholder="Paste a YouTube or video link"
                        className="flex-1 min-w-0 text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                      />
                      <button
                        onClick={handleAddFromUrl}
                        disabled={urlSubmitting || !videoUrl.trim()}
                        className="shrink-0 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
                      >
                        {urlSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        Add
                      </button>
                      <button
                        onClick={() => {
                          setShowUrlInput(false);
                          setUrlError(null);
                        }}
                        className="shrink-0 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 px-1"
                        aria-label="Cancel"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    {urlError && <p className="text-xs text-red-600 dark:text-red-400">{urlError}</p>}
                  </div>
                ) : (
                  <button
                    onClick={() => setShowUrlInput(true)}
                    className="w-full flex items-center justify-center gap-1.5 text-xs text-neutral-400 dark:text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-200 mb-4 transition-colors"
                  >
                    <Link2 className="h-3 w-3" />
                    Or add from a video link (YouTube, etc.)
                  </button>
                )}

                {folderDocs.length > 0 && (
                  <div className="space-y-1 mb-5">
                    {folderDocs.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between text-xs text-neutral-600 dark:text-neutral-400 px-2.5 py-1.5 rounded-lg bg-neutral-50 dark:bg-neutral-900"
                      >
                        <span className="truncate">{doc.filename}</span>
                        <span
                          className={`shrink-0 ml-2 ${
                            READY_STATUSES.includes(doc.status)
                              ? "text-emerald-600 dark:text-emerald-400"
                              : doc.status === "failed"
                                ? "text-red-600 dark:text-red-400"
                                : "text-amber-600 dark:text-amber-400"
                          }`}
                        >
                          {READY_STATUSES.includes(doc.status)
                            ? "Ready"
                            : doc.status === "failed"
                              ? "Failed"
                              : AUDIO_VIDEO_EXTENSIONS.has(doc.file_type)
                                ? "Transcribing…"
                                : "Processing"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={handleStartChat}
                  disabled={readyCount === 0 || startingChat}
                  className="w-full flex items-center justify-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-40"
                >
                  {startingChat ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      Start chat with this folder
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </button>
                {readyCount === 0 && (
                  <p className="text-xs text-neutral-400 dark:text-neutral-500 text-center mt-2">
                    Add at least one document to start chatting.
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      <AnimatePresence>
        {showAdvancedModal && (
          <SelectChatScopeModal
            documents={documents}
            folders={folders}
            onConfirm={async (documentIds) => {
              const id = await createChat(documentIds);
              setShowAdvancedModal(false);
              router.push(`/chat/${id}`);
            }}
            onClose={() => setShowAdvancedModal(false)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
