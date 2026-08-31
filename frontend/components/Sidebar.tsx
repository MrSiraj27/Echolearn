"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  X,
  ChevronRight,
  ChevronDown,
  LogOut,
  Plus,
  Folder as FolderIcon,
  FolderKanban,
  Settings2,
  Menu,
  AudioLines,
  Video,
  FileText as FileTextIcon,
  Link2,
  Loader2,
  BarChart3,
} from "lucide-react";
import { useChatStore } from "@/lib/chat-store";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import {
  AUDIO_VIDEO_EXTENSIONS,
  DocumentItem,
  DocumentStatus,
  Folder,
  QuizListItem,
  VIDEO_EXTENSIONS,
  Workspace,
  WorkspaceDetail,
} from "@/lib/types";
import DocumentSearchModal from "@/components/DocumentSearchModal";
import SettingsMenu from "@/components/SettingsMenu";
import MoveToFolderMenu from "@/components/MoveToFolderMenu";
import SelectChatScopeModal from "@/components/SelectChatScopeModal";
import WorkspaceModal from "@/components/WorkspaceModal";
import UsagePanel from "@/components/UsagePanel";

function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="28" height="28" rx="7" fill="currentColor" />
      <path
        d="M8 10.5C8 9.11929 9.11929 8 10.5 8H17.5C18.8807 8 20 9.11929 20 10.5V15.5C20 16.8807 18.8807 18 17.5 18H12L9 20.5V18H10.5C9.11929 18 8 16.8807 8 15.5V10.5Z"
        fill="white"
        fillOpacity="0.92"
      />
    </svg>
  );
}

const SEARCHABLE_STATUSES: DocumentStatus[] = ["embedded", "ready"];

function StatusBadge({ status, fileType }: { status: DocumentStatus; fileType?: string }) {
  const styles: Record<DocumentStatus, string> = {
    uploaded: "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
    parsing: "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400",
    embedded: "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400",
    ready: "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400",
    failed: "bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400",
  };
  const isMedia = fileType ? AUDIO_VIDEO_EXTENSIONS.has(fileType) : false;
  const labels: Record<DocumentStatus, string> = {
    uploaded: "Uploaded",
    parsing: isMedia ? "Transcribing…" : "Processing",
    embedded: "Finishing up",
    ready: "Ready",
    failed: "Failed",
  };
  return (
    <span
      className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0 ${styles[status]}`}
      title={isMedia && status === "parsing" ? "Transcribing audio — this can take a few minutes." : undefined}
    >
      {labels[status]}
    </span>
  );
}

function DocumentTypeIcon({ fileType }: { fileType: string }) {
  if (VIDEO_EXTENSIONS.has(fileType)) return <Video className="h-3.5 w-3.5 shrink-0 text-neutral-400" />;
  if (AUDIO_VIDEO_EXTENSIONS.has(fileType)) return <AudioLines className="h-3.5 w-3.5 shrink-0 text-neutral-400" />;
  return <FileTextIcon className="h-3.5 w-3.5 shrink-0 text-neutral-400" />;
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function DocumentRow({
  doc,
  folders,
  onSearch,
  onDelete,
  onMove,
  onCreateFolder,
}: {
  doc: DocumentItem;
  folders: Folder[];
  onSearch: () => void;
  onDelete: () => void;
  onMove: (folderId: string | null) => void;
  onCreateFolder: (name: string) => Promise<Folder>;
}) {
  const [expanded, setExpanded] = useState(false);
  const searchable = SEARCHABLE_STATUSES.includes(doc.status);
  const hasSummary = doc.status === "ready" && doc.summary;

  return (
    <div className="rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
      <div
        className="group flex items-center justify-between gap-2 px-2.5 py-2 cursor-pointer"
        onClick={() => hasSummary && setExpanded((v) => !v)}
      >
        <span className="truncate text-sm text-neutral-700 dark:text-neutral-300 flex items-center gap-1">
          {hasSummary && (
            <ChevronRight className={`h-3 w-3 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`} />
          )}
          <DocumentTypeIcon fileType={doc.file_type} />
          {doc.filename}
        </span>
        <div className="flex items-center gap-1 shrink-0">
          <StatusBadge status={doc.status} fileType={doc.file_type} />
          {searchable && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSearch();
              }}
              className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 p-0.5 transition-opacity"
              aria-label={`Search in ${doc.filename}`}
            >
              <Search className="h-3.5 w-3.5" />
            </button>
          )}
          <MoveToFolderMenu
            folders={folders}
            currentFolderId={doc.folder_id}
            onMove={onMove}
            onCreateFolder={onCreateFolder}
          />
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-0.5 transition-opacity"
            aria-label="Delete document"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <AnimatePresence>
        {expanded && hasSummary && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed px-2.5 pb-2.5">
              {doc.summary}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Sidebar({ activeChatId }: { activeChatId?: string }) {
  const router = useRouter();
  const { logout } = useAuth();
  const {
    chats,
    documents,
    folders,
    workspaces,
    loadChats,
    loadDocuments,
    loadFolders,
    createFolder,
    deleteFolder,
    moveDocumentToFolder,
    loadWorkspaces,
    createWorkspace,
    deleteWorkspace,
    addDocumentToWorkspace,
    removeDocumentFromWorkspace,
    createChat,
    createWorkspaceChat,
    deleteChat,
    deleteDocument,
    pollDocumentStatus,
    addDocumentFromUrl,
  } = useChatStore();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadFolderId, setUploadFolderId] = useState<string>("");
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [searchingDoc, setSearchingDoc] = useState<DocumentItem | null>(null);
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());
  const [quizzes, setQuizzes] = useState<QuizListItem[]>([]);
  const [showScopeModal, setShowScopeModal] = useState(false);
  const [showNewWorkspaceModal, setShowNewWorkspaceModal] = useState(false);
  const [managingWorkspace, setManagingWorkspace] = useState<Workspace | null>(null);
  const [managingWorkspaceDocIds, setManagingWorkspaceDocIds] = useState<string[]>([]);
  const [startingWorkspaceId, setStartingWorkspaceId] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get<QuizListItem[]>("/quizzes/", { auth: true })
      .then(setQuizzes)
      .catch(() => setQuizzes([]));
  }, []);

  useEffect(() => {
    loadChats();
    loadDocuments();
    loadFolders();
    loadWorkspaces();
  }, [loadChats, loadDocuments, loadFolders, loadWorkspaces]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    setUploadError(null);
    setUploading(true);

    try {
      const { getAccessToken } = await import("@/lib/api");
      const token = getAccessToken();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const formData = new FormData();
      formData.append("file", file);
      if (uploadFolderId) formData.append("folder_id", uploadFolderId);

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
      await loadFolders();
      pollDocumentStatus(data.document_id);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleAddFromUrl() {
    const url = videoUrl.trim();
    if (!url) return;
    setUrlSubmitting(true);
    setUrlError(null);
    try {
      await addDocumentFromUrl(url, uploadFolderId || null);
      setVideoUrl("");
      setShowUrlInput(false);
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : "Couldn't add that video.");
    } finally {
      setUrlSubmitting(false);
    }
  }

  async function handleStartChat(documentIds: string[]) {
    const id = await createChat(documentIds);
    setShowScopeModal(false);
    router.push(`/chat/${id}`);
  }

  async function handleStartWorkspaceChat(workspaceId: string) {
    setStartingWorkspaceId(workspaceId);
    try {
      const id = await createWorkspaceChat(workspaceId);
      setMobileOpen(false);
      router.push(`/chat/${id}`);
    } finally {
      setStartingWorkspaceId(null);
    }
  }

  async function openManageWorkspace(workspace: Workspace) {
    const detail = await api.get<WorkspaceDetail>(`/workspaces/${workspace.id}`, { auth: true });
    setManagingWorkspaceDocIds(detail.document_ids);
    setManagingWorkspace(workspace);
  }

  function toggleFolderCollapsed(folderId: string) {
    setCollapsedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) next.delete(folderId);
      else next.add(folderId);
      return next;
    });
  }

  const unfiledDocs = documents.filter((d) => !d.folder_id);

  return (
    <>
      {/* Mobile menu trigger — hidden once the drawer is open, and hidden entirely at lg+
          where the sidebar is always visible inline. */}
      {!mobileOpen && (
        <button
          onClick={() => setMobileOpen(true)}
          className="lg:hidden fixed top-3 left-3 z-30 h-9 w-9 flex items-center justify-center rounded-lg bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 shadow-sm"
          aria-label="Open menu"
        >
          <Menu className="h-4 w-4" />
        </button>
      )}

      {/* Backdrop, mobile only, closes the drawer on tap outside it. */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMobileOpen(false)}
            className="lg:hidden fixed inset-0 bg-black/40 z-30"
          />
        )}
      </AnimatePresence>

      <aside
        className={`w-72 shrink-0 h-screen bg-neutral-50 dark:bg-neutral-900 border-r border-neutral-200 dark:border-neutral-800 flex flex-col fixed inset-y-0 left-0 z-40 transform transition-transform duration-200 ease-out lg:relative lg:translate-x-0 lg:z-auto ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="px-4 py-4 flex items-center justify-between text-neutral-900 dark:text-neutral-100">
          <div className="flex items-center gap-2">
            <Mark />
            <span className="text-[15px] font-semibold tracking-tight">EchoLearn</span>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
            aria-label="Close menu"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

      <div className="px-3">
        <button
          onClick={() => {
            setMobileOpen(false);
            setShowScopeModal(true);
          }}
          className="w-full flex items-center justify-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 mt-4 space-y-1">
        <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide px-1 mb-1">
          Chats
        </p>
        {chats.length === 0 && <p className="text-xs text-neutral-400 dark:text-neutral-500 px-1 py-2">No chats yet.</p>}
        <AnimatePresence initial={false}>
          {chats.map((chat) => (
            <motion.div
              key={chat.id}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="group relative"
            >
              <Link
                href={`/chat/${chat.id}`}
                onClick={() => setMobileOpen(false)}
                className={`block rounded-lg px-2.5 py-2 text-sm transition-colors ${
                  activeChatId === chat.id
                    ? "bg-neutral-200/70 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100"
                    : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
                }`}
              >
                <p className="truncate font-medium">{chat.title || "Untitled chat"}</p>
                <p className="truncate text-xs text-neutral-400 dark:text-neutral-500">{timeAgo(chat.created_at)}</p>
              </Link>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  deleteChat(chat.id);
                  if (activeChatId === chat.id) router.push("/chat");
                }}
                className="absolute right-1.5 top-1.5 opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-1 rounded transition-opacity"
                aria-label="Delete chat"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>

        <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide px-1 mb-1 mt-5">
          Documents
        </p>

        {folders.length > 0 && (
          <select
            value={uploadFolderId}
            onChange={(e) => setUploadFolderId(e.target.value)}
            className="w-full text-xs bg-transparent border border-neutral-200 dark:border-neutral-700 rounded-lg px-2 py-1.5 mb-1.5 text-neutral-600 dark:text-neutral-400 focus:outline-none"
          >
            <option value="">Upload to: No folder</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                Upload to: {f.name}
              </option>
            ))}
          </select>
        )}

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
          className={`border border-dashed rounded-lg px-3 py-3 text-center text-xs cursor-pointer transition-colors mb-2 ${
            dragOver
              ? "border-neutral-900 dark:border-neutral-100 bg-neutral-100 dark:bg-neutral-800"
              : "border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
            accept=".pdf,.docx,.pptx,.txt,.csv,.png,.jpg,.jpeg,.mp3,.wav,.m4a,.mp4,.mov"
          />
          {uploading ? "Uploading..." : "Drop a file or click to upload"}
        </div>
        {uploadError && <p className="text-xs text-red-600 dark:text-red-400 px-1 mb-2">{uploadError}</p>}

        {showUrlInput ? (
          <div className="mb-2 space-y-1.5">
            <div className="flex gap-1.5">
              <input
                autoFocus
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddFromUrl()}
                placeholder="Paste a YouTube or video link"
                className="flex-1 min-w-0 text-xs rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1.5 text-neutral-700 dark:text-neutral-300 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
              />
              <button
                onClick={handleAddFromUrl}
                disabled={urlSubmitting || !videoUrl.trim()}
                className="shrink-0 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                {urlSubmitting && <Loader2 className="h-3 w-3 animate-spin" />}
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
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            {urlError && <p className="text-xs text-red-600 dark:text-red-400 px-1">{urlError}</p>}
          </div>
        ) : (
          <button
            onClick={() => setShowUrlInput(true)}
            className="w-full flex items-center justify-center gap-1.5 text-xs text-neutral-400 dark:text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-200 mb-2 py-1 transition-colors"
          >
            <Link2 className="h-3 w-3" />
            Add from video link (YouTube, etc.)
          </button>
        )}

        {documents.length === 0 && <p className="text-xs text-neutral-400 dark:text-neutral-500 px-1 py-2">No documents yet.</p>}

        <div className="space-y-2">
          {folders.map((folder) => {
            const folderDocs = documents.filter((d) => d.folder_id === folder.id);
            const isCollapsed = collapsedFolders.has(folder.id);
            return (
              <div key={folder.id}>
                <div className="group flex items-center justify-between px-1 py-1">
                  <button
                    onClick={() => toggleFolderCollapsed(folder.id)}
                    className="flex items-center gap-1.5 text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors min-w-0"
                  >
                    {isCollapsed ? <ChevronRight className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
                    <FolderIcon className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{folder.name}</span>
                    <span className="text-neutral-400 dark:text-neutral-500 shrink-0">({folderDocs.length})</span>
                  </button>
                  <button
                    onClick={() => deleteFolder(folder.id)}
                    className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-0.5 transition-opacity shrink-0"
                    aria-label={`Delete folder ${folder.name}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
                <AnimatePresence initial={false}>
                  {!isCollapsed && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden space-y-1 pl-2"
                    >
                      {folderDocs.map((doc) => (
                        <DocumentRow
                          key={doc.id}
                          doc={doc}
                          folders={folders}
                          onSearch={() => setSearchingDoc(doc)}
                          onDelete={() => deleteDocument(doc.id)}
                          onMove={(folderId) => moveDocumentToFolder(doc.id, folderId)}
                          onCreateFolder={createFolder}
                        />
                      ))}
                      {folderDocs.length === 0 && (
                        <p className="text-xs text-neutral-400 dark:text-neutral-500 px-2.5 py-1">Empty</p>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}

          {unfiledDocs.length > 0 && (
            <div className="space-y-1">
              {folders.length > 0 && (
                <p className="text-[11px] font-medium text-neutral-400 dark:text-neutral-500 px-1">Unfiled</p>
              )}
              {unfiledDocs.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  folders={folders}
                  onSearch={() => setSearchingDoc(doc)}
                  onDelete={() => deleteDocument(doc.id)}
                  onMove={(folderId) => moveDocumentToFolder(doc.id, folderId)}
                  onCreateFolder={createFolder}
                />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-1 mb-1 mt-5">
          <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide">
            Workspaces
          </p>
          <button
            onClick={() => setShowNewWorkspaceModal(true)}
            className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
            aria-label="New workspace"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
        {workspaces.length === 0 && (
          <p className="text-xs text-neutral-400 dark:text-neutral-500 px-1 py-1">
            Group documents to chat across all of them at once.
          </p>
        )}
        <div className="space-y-1">
          {workspaces.map((workspace) => (
            <div key={workspace.id} className="group flex items-center gap-1 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800/60">
              <button
                onClick={() => handleStartWorkspaceChat(workspace.id)}
                disabled={startingWorkspaceId === workspace.id}
                className="flex-1 min-w-0 flex items-center gap-1.5 text-left px-2.5 py-2 text-sm text-neutral-700 dark:text-neutral-300 disabled:opacity-50"
              >
                <FolderKanban className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
                <span className="truncate">{workspace.name}</span>
                <span className="text-xs text-neutral-400 dark:text-neutral-500 shrink-0">
                  ({workspace.document_count})
                </span>
              </button>
              <button
                onClick={() => openManageWorkspace(workspace)}
                className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 p-0.5 transition-opacity shrink-0"
                aria-label={`Manage ${workspace.name}`}
              >
                <Settings2 className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => deleteWorkspace(workspace.id)}
                className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-0.5 mr-1.5 transition-opacity shrink-0"
                aria-label={`Delete ${workspace.name}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>

        {quizzes.length > 0 && (
          <>
            <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide px-1 mb-1 mt-5">
              My Quizzes
            </p>
            <div className="space-y-1">
              {quizzes.map((quiz) => (
                <Link
                  key={quiz.id}
                  href={`/quiz/${quiz.id}`}
                  onClick={() => setMobileOpen(false)}
                  className="block rounded-lg px-2.5 py-2 text-sm text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800/60 transition-colors"
                >
                  <p className="truncate font-medium">{quiz.title}</p>
                  <p className="text-xs text-neutral-400 dark:text-neutral-500">
                    {quiz.question_count} questions
                    {quiz.best_score != null && ` · Best: ${quiz.best_score}%`}
                  </p>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>

      <UsagePanel />

      <div className="px-3 py-3 border-t border-neutral-200 dark:border-neutral-800 space-y-1">
        <Link
          href="/analytics"
          onClick={() => setMobileOpen(false)}
          className="w-full flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 px-1 py-1 transition-colors"
        >
          <BarChart3 className="h-4 w-4" />
          Analytics
        </Link>
        <SettingsMenu />
        <button
          onClick={() => {
            logout();
            router.push("/login");
          }}
          className="w-full flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 px-1 py-1 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>

      <AnimatePresence>
        {searchingDoc && (
          <DocumentSearchModal
            documentId={searchingDoc.id}
            filename={searchingDoc.filename}
            onClose={() => setSearchingDoc(null)}
          />
        )}
        {showScopeModal && (
          <SelectChatScopeModal
            documents={documents}
            folders={folders}
            onConfirm={handleStartChat}
            onClose={() => setShowScopeModal(false)}
          />
        )}
        {showNewWorkspaceModal && (
          <WorkspaceModal
            documents={documents}
            onCreate={async (name, documentIds) => {
              await createWorkspace(name, documentIds);
            }}
            onClose={() => setShowNewWorkspaceModal(false)}
          />
        )}
        {managingWorkspace && (
          <WorkspaceModal
            documents={documents}
            workspace={managingWorkspace}
            workspaceDocumentIds={managingWorkspaceDocIds}
            onToggleDocument={async (documentId, isMember) => {
              if (isMember) {
                await removeDocumentFromWorkspace(managingWorkspace.id, documentId);
              } else {
                await addDocumentToWorkspace(managingWorkspace.id, documentId);
              }
            }}
            onClose={() => setManagingWorkspace(null)}
          />
        )}
      </AnimatePresence>
    </aside>
    </>
  );
}
