"use client";

import { Suspense, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  BookOpen,
  CloudUpload,
  Folder as FolderIcon,
  FolderPlus,
  Layers,
  Link2,
  Loader2,
  MessageSquare,
  Plus,
  RotateCcw,
  Search,
  Settings2,
  Trash2,
  X,
} from "lucide-react";
import DocumentMenu from "@/components/documents/DocumentMenu";
import { DocTypeIcon, docMeta, isReady, StatusPill } from "@/components/documents/docUi";
import DocumentSearchModal from "@/components/DocumentSearchModal";
import RevisionSheetModal from "@/components/RevisionSheetModal";
import WorkspaceModal from "@/components/WorkspaceModal";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import type { DocumentItem, Workspace, WorkspaceDetail } from "@/lib/types";
import { UPLOAD_ACCEPT, uploadDocument } from "@/lib/upload";

type StatusFilter = "all" | "ready" | "processing" | "failed";

function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl dark:bg-neutral-900"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-neutral-500" aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function DocumentsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const {
    documents,
    folders,
    workspaces,
    createFolder,
    deleteFolder,
    moveDocumentToFolder,
    renameDocument,
    retryDocument,
    addDocumentFromUrl,
    createChat,
    createWorkspace,
    createWorkspaceChat,
    deleteWorkspace,
    addDocumentToWorkspace,
    removeDocumentFromWorkspace,
  } = useChatStore();
  const documentsLoaded = useChatStore((st) => st.documentsLoaded);

  const [query, setQuery] = useState(params.get("q") ?? "");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [folderFilter, setFolderFilter] = useState<string>("all"); // all | unfiled | folder id
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [urlOpen, setUrlOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [newFolder, setNewFolder] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<{ doc: DocumentItem; name: string } | null>(null);
  const [moving, setMoving] = useState<DocumentItem | null>(null);
  const [revising, setRevising] = useState<{ ids: string[]; workspace?: { id: string; name: string } } | null>(null);
  const [searching, setSearching] = useState<DocumentItem | null>(null);
  const [wsCreate, setWsCreate] = useState(false);
  const [wsManage, setWsManage] = useState<{ ws: Workspace; ids: string[] } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const targetFolder = folderFilter !== "all" && folderFilter !== "unfiled" ? folderFilter : null;

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return documents.filter((d) => {
      if (q && !d.filename.toLowerCase().includes(q) && !(d.summary ?? "").toLowerCase().includes(q)) return false;
      if (status === "ready" && !isReady(d)) return false;
      if (status === "failed" && d.status !== "failed") return false;
      if (status === "processing" && (isReady(d) || d.status === "failed")) return false;
      if (folderFilter === "unfiled" && d.folder_id) return false;
      if (targetFolder && d.folder_id !== targetFolder) return false;
      return true;
    });
  }, [documents, query, status, folderFilter, targetFolder]);

  const counts = {
    all: documents.length,
    ready: documents.filter(isReady).length,
    processing: documents.filter((d) => !isReady(d) && d.status !== "failed").length,
    failed: documents.filter((d) => d.status === "failed").length,
  };

  async function act(key: string, fn: () => Promise<unknown>, ok?: string) {
    setBusy(key);
    setNotice(null);
    try {
      await fn();
      if (ok) setNotice({ tone: "ok", text: ok });
    } catch (err) {
      setNotice({ tone: "bad", text: err instanceof Error ? err.message : "That didn't work. Please try again." });
    } finally {
      setBusy(null);
    }
  }

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setNotice(null);
    const list = Array.from(files);
    const failed: string[] = [];
    for (const f of list) {
      try {
        await uploadDocument(f, targetFolder);
      } catch (err) {
        failed.push(`${f.name}: ${err instanceof Error ? err.message : "upload failed"}`);
      }
    }
    setUploading(false);
    if (failed.length) setNotice({ tone: "bad", text: failed.join(" ") });
    else setNotice({ tone: "ok", text: list.length > 1 ? `${list.length} files uploaded. Processing has started.` : "Uploaded. Processing has started." });
  }

  const chip = (active: boolean) =>
    `inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] ring-1 ${
      active
        ? "bg-neutral-900 text-white ring-neutral-900 dark:bg-white dark:text-neutral-900 dark:ring-white"
        : "bg-white text-neutral-700 ring-neutral-200 hover:ring-neutral-400 dark:bg-neutral-900 dark:text-neutral-300 dark:ring-neutral-700"
    }`;

  return (
    <main className="min-w-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">My Documents</h1>
            <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">Everything you&apos;ve uploaded to study from.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setUrlOpen(true)} className="flex items-center gap-2 rounded-xl border border-neutral-300 bg-white px-4 py-2.5 text-sm font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:bg-neutral-800">
              <Link2 className="h-4 w-4" /> Add video link
            </button>
            <button onClick={() => fileRef.current?.click()} disabled={uploading} className="flex items-center gap-2 rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-60 dark:bg-white dark:text-neutral-900">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CloudUpload className="h-4 w-4" />} Upload
            </button>
            <input ref={fileRef} type="file" multiple accept={UPLOAD_ACCEPT} className="hidden" onChange={(e) => { void onFiles(e.target.files); e.target.value = ""; }} />
          </div>
        </div>

        {notice && (
          <div role="status" className={`flex items-start justify-between gap-3 rounded-xl px-4 py-3 text-sm ${notice.tone === "ok" ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300" : "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300"}`}>
            {notice.text}
            <button onClick={() => setNotice(null)} aria-label="Dismiss"><X className="h-4 w-4" /></button>
          </div>
        )}

        {/* filters */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-neutral-200 bg-white px-3.5 py-2.5 sm:max-w-sm dark:border-neutral-800 dark:bg-neutral-900">
              <Search className="h-4 w-4 text-neutral-400" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name or summary" aria-label="Search documents" className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
              {query && <button onClick={() => setQuery("")} aria-label="Clear search"><X className="h-3.5 w-3.5 text-neutral-400" /></button>}
            </label>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
              {(["all", "ready", "processing", "failed"] as StatusFilter[]).map((s) => (
                <button key={s} onClick={() => setStatus(s)} aria-pressed={status === s} className={chip(status === s)}>
                  {s[0].toUpperCase() + s.slice(1)} <span className="opacity-60">{counts[s]}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by folder">
            <button onClick={() => setFolderFilter("all")} aria-pressed={folderFilter === "all"} className={chip(folderFilter === "all")}>All folders</button>
            <button onClick={() => setFolderFilter("unfiled")} aria-pressed={folderFilter === "unfiled"} className={chip(folderFilter === "unfiled")}>Unfiled</button>
            {folders.map((f) => (
              <span key={f.id} className="inline-flex items-center">
                <button onClick={() => setFolderFilter(f.id)} aria-pressed={folderFilter === f.id} className={chip(folderFilter === f.id)}>
                  <FolderIcon className="h-3.5 w-3.5" /> {f.name}
                </button>
                {folderFilter === f.id && (
                  <button
                    onClick={() => act(`folder:${f.id}`, async () => { await deleteFolder(f.id); setFolderFilter("all"); }, `Folder "${f.name}" deleted. Its documents are now unfiled.`)}
                    className="ml-1 rounded-full p-1.5 text-neutral-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
                    aria-label={`Delete folder ${f.name}`}
                    title="Delete folder (documents are kept)"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </span>
            ))}
            {newFolder === null ? (
              <button onClick={() => setNewFolder("")} className={chip(false)}><FolderPlus className="h-3.5 w-3.5" /> New folder</button>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const name = newFolder.trim();
                  if (name) void act("newfolder", async () => { const f = await createFolder(name); setFolderFilter(f.id); setNewFolder(null); });
                }}
                className="inline-flex items-center gap-1"
              >
                <input autoFocus value={newFolder} onChange={(e) => setNewFolder(e.target.value)} onKeyDown={(e) => e.key === "Escape" && setNewFolder(null)} placeholder="Folder name" aria-label="New folder name" className="w-36 rounded-full border border-neutral-300 bg-white px-3 py-1.5 text-[13px] outline-none dark:border-neutral-700 dark:bg-neutral-900" />
                <button type="submit" className="rounded-full bg-neutral-900 px-3 py-1.5 text-[13px] text-white dark:bg-white dark:text-neutral-900">Add</button>
              </form>
            )}
          </div>
        </div>

        {/* list + drop zone */}
        <section
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); void onFiles(e.dataTransfer.files); }}
          className={`overflow-hidden rounded-2xl border bg-white dark:bg-neutral-900 ${dragOver ? "border-neutral-900 ring-2 ring-neutral-900/10 dark:border-white" : "border-neutral-200 dark:border-neutral-800"}`}
          aria-label="Documents"
        >
          {!documentsLoaded ? (
            <div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-neutral-400" aria-label="Loading documents" /></div>
          ) : documents.length === 0 ? (
            <button onClick={() => fileRef.current?.click()} className="flex w-full flex-col items-center gap-3 px-6 py-16 text-center">
              <CloudUpload className="h-10 w-10" strokeWidth={1.5} />
              <span className="text-lg font-semibold">Upload your first document</span>
              <span className="max-w-md text-sm text-neutral-500">Drop a file here or click to choose. PDF, Word, PowerPoint, text, images, audio and video all work.</span>
            </button>
          ) : shown.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-neutral-500">No documents match these filters.</p>
          ) : (
            <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {shown.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5 sm:px-5">
                  <DocTypeIcon fileType={d.file_type} size={40} />
                  <div className="min-w-0 flex-1 basis-48">
                    <p className="truncate text-[15px] font-medium" title={d.filename}>{d.filename}</p>
                    <p className={`text-[12.5px] ${d.status === "failed" ? "text-red-600 dark:text-red-400" : "text-neutral-500"}`}>
                      {d.status === "failed" && d.error_message ? d.error_message : docMeta(d)}
                      {d.folder_id && folderFilter === "all" && <> · <FolderIcon className="inline h-3 w-3" /> {folders.find((f) => f.id === d.folder_id)?.name}</>}
                    </p>
                  </div>
                  <StatusPill doc={d} />
                  <div className="flex items-center gap-1.5">
                    {isReady(d) ? (
                      <>
                        <button onClick={() => router.push(`/read/${d.id}`)} className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-[13px] font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800">
                          <BookOpen className="h-3.5 w-3.5" /> Open
                        </button>
                        <button
                          onClick={() => act(`chat:${d.id}`, async () => router.push(`/chat/${await createChat([d.id], d.filename)}`))}
                          disabled={busy === `chat:${d.id}`}
                          className="hidden items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-[13px] font-medium hover:bg-neutral-50 sm:flex dark:border-neutral-700 dark:hover:bg-neutral-800"
                        >
                          {busy === `chat:${d.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquare className="h-3.5 w-3.5" />} Chat
                        </button>
                      </>
                    ) : d.status === "failed" ? (
                      <button onClick={() => act(`retry:${d.id}`, () => retryDocument(d.id), "Processing again.")} disabled={busy === `retry:${d.id}`} className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-[13px] font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800">
                        {busy === `retry:${d.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />} Retry
                      </button>
                    ) : null}
                    <DocumentMenu
                      doc={d}
                      onRename={() => setRenaming({ doc: d, name: d.filename.replace(/\.[A-Za-z0-9]{1,5}$/, "") })}
                      onRevise={() => setRevising({ ids: [d.id] })}
                      onSearch={() => setSearching(d)}
                      onMove={() => setMoving(d)}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
          {documents.length > 0 && (
            <p className="border-t border-neutral-100 px-5 py-3 text-center text-[12px] text-neutral-500 dark:border-neutral-800">
              Drop files anywhere on this list to upload{targetFolder ? " into this folder" : ""}.
            </p>
          )}
        </section>

        {/* workspaces */}
        <section className="rounded-2xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900" aria-label="Workspaces">
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-lg font-semibold"><Layers className="h-5 w-5" /> Workspaces</h2>
            <button onClick={() => setWsCreate(true)} className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-[13px] font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800">
              <Plus className="h-3.5 w-3.5" /> New workspace
            </button>
          </div>
          <p className="mb-4 text-sm text-neutral-500">Group documents from any folder to chat, study or make revision sheets across all of them.</p>
          {workspaces.length === 0 ? (
            <p className="text-sm text-neutral-500">No workspaces yet.</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {workspaces.map((w) => (
                <li key={w.id} className="flex items-center gap-3 rounded-xl border border-neutral-200 p-3 dark:border-neutral-700">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{w.name}</span>
                    <span className="text-[12px] text-neutral-500">{w.document_count} document{w.document_count === 1 ? "" : "s"}</span>
                  </span>
                  <button
                    onClick={() => act(`ws:${w.id}`, async () => router.push(`/chat/${await createWorkspaceChat(w.id)}`))}
                    disabled={busy === `ws:${w.id}` || w.document_count === 0}
                    className="flex items-center gap-1 rounded-lg bg-neutral-900 px-2.5 py-1.5 text-[12px] font-medium text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900"
                  >
                    {busy === `ws:${w.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquare className="h-3.5 w-3.5" />} Chat
                  </button>
                  <button
                    onClick={() => act(`wsm:${w.id}`, async () => { const det = await api.get<WorkspaceDetail>(`/workspaces/${w.id}`, { auth: true }); setWsManage({ ws: w, ids: det.document_ids }); })}
                    className="rounded-lg p-1.5 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                    aria-label={`Edit documents in ${w.name}`}
                    title="Edit documents"
                  >
                    <Settings2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setRevising({ ids: [], workspace: { id: w.id, name: w.name } })}
                    className="hidden rounded-lg px-2 py-1.5 text-[12px] text-neutral-600 hover:bg-neutral-100 sm:block dark:text-neutral-300 dark:hover:bg-neutral-800"
                  >
                    Revision sheet
                  </button>
                  <button
                    onClick={() => act(`wsd:${w.id}`, () => deleteWorkspace(w.id), `Workspace "${w.name}" deleted. Its documents are kept.`)}
                    className="rounded-lg p-1.5 text-neutral-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
                    aria-label={`Delete workspace ${w.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {urlOpen && (
        <Dialog title="Add a video link" onClose={() => setUrlOpen(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const u = url.trim();
              if (!u) return;
              void act("url", async () => { await addDocumentFromUrl(u, targetFolder); setUrl(""); setUrlOpen(false); }, "Downloading the audio. It will be transcribed automatically.");
            }}
            className="space-y-3"
          >
            <p className="text-sm text-neutral-500">YouTube and most video sites work. The audio is transcribed so you can read and ask about it.</p>
            <input autoFocus value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" aria-label="Video link" className="w-full rounded-xl border border-neutral-300 bg-white px-3 py-2.5 text-sm outline-none dark:border-neutral-700 dark:bg-neutral-950" />
            <button type="submit" disabled={busy === "url" || !url.trim()} className="w-full rounded-xl bg-neutral-900 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900">
              {busy === "url" ? "Adding…" : "Add video"}
            </button>
          </form>
        </Dialog>
      )}

      {renaming && (
        <Dialog title="Rename document" onClose={() => setRenaming(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const n = renaming.name.trim();
              if (!n) return;
              void act("rename", async () => { await renameDocument(renaming.doc.id, n); setRenaming(null); });
            }}
            className="space-y-3"
          >
            <input autoFocus value={renaming.name} maxLength={190} onChange={(e) => setRenaming({ ...renaming, name: e.target.value })} aria-label="Document name" className="w-full rounded-xl border border-neutral-300 bg-white px-3 py-2.5 text-sm outline-none dark:border-neutral-700 dark:bg-neutral-950" />
            <p className="text-xs text-neutral-500">The file type ending is kept automatically.</p>
            <button type="submit" disabled={busy === "rename"} className="w-full rounded-xl bg-neutral-900 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900">Save name</button>
          </form>
        </Dialog>
      )}

      {moving && (
        <Dialog title={`Move “${moving.filename}”`} onClose={() => setMoving(null)}>
          <div className="space-y-1">
            {[{ id: null as string | null, name: "No folder (unfiled)" }, ...folders].map((f) => (
              <button
                key={f.id ?? "none"}
                onClick={() => act("move", async () => { await moveDocumentToFolder(moving.id, f.id); setMoving(null); })}
                disabled={busy === "move" || moving.folder_id === f.id || (!moving.folder_id && f.id === null)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-neutral-100 disabled:opacity-40 dark:hover:bg-neutral-800"
              >
                <FolderIcon className="h-4 w-4" /> {f.name}
              </button>
            ))}
            {folders.length === 0 && <p className="px-3 py-2 text-xs text-neutral-500">Create a folder with “New folder” first.</p>}
          </div>
        </Dialog>
      )}

      {searching && <DocumentSearchModal documentId={searching.id} filename={searching.filename} onClose={() => setSearching(null)} />}
      {revising && (
        <RevisionSheetModal documents={documents} preselectedDocumentIds={revising.ids} workspace={revising.workspace ?? null} onClose={() => setRevising(null)} />
      )}
      {wsCreate && <WorkspaceModal documents={documents} onCreate={async (name, ids) => { await createWorkspace(name, ids); }} onClose={() => setWsCreate(false)} />}
      {wsManage && (
        <WorkspaceModal
          documents={documents}
          workspace={wsManage.ws}
          workspaceDocumentIds={wsManage.ids}
          onToggleDocument={async (documentId, isMember) => {
            if (isMember) await removeDocumentFromWorkspace(wsManage.ws.id, documentId);
            else await addDocumentToWorkspace(wsManage.ws.id, documentId);
          }}
          onClose={() => setWsManage(null)}
        />
      )}
    </main>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<main className="flex-1" />}>
      <DocumentsInner />
    </Suspense>
  );
}
