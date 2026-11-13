"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2, MessageSquare, Plus, Sparkles, Trash2 } from "lucide-react";
import SelectChatScopeModal from "@/components/SelectChatScopeModal";
import { useChatStore } from "@/lib/chat-store";
import { isReady } from "@/components/documents/docUi";

function when(iso: string) {
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days < 1) return "Today";
  if (days < 2) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** AI Assistant: start a chat over any documents, or continue an earlier one. */
export default function AssistantPage() {
  const router = useRouter();
  const chats = useChatStore((s) => s.chats);
  const documents = useChatStore((s) => s.documents);
  const folders = useChatStore((s) => s.folders);
  const createChat = useChatStore((s) => s.createChat);
  const deleteChat = useChatStore((s) => s.deleteChat);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const readyCount = documents.filter(isReady).length;

  async function start(ids: string[]) {
    setStarting(true);
    setError(null);
    try {
      router.push(`/chat/${await createChat(ids)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start a chat.");
      setStarting(false);
    }
  }

  async function remove(id: string) {
    setDeleting(id);
    try {
      await deleteChat(id);
      setConfirming(null);
    } catch {
      setError("Couldn't delete that chat. Please try again.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <main className="min-w-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight"><Sparkles className="h-7 w-7" /> AI Assistant</h1>
            <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">Ask questions and get answers from your own documents, with the pages they came from.</p>
          </div>
          <button
            onClick={() => setScopeOpen(true)}
            disabled={starting || readyCount === 0}
            className="flex items-center gap-2 rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} New chat
          </button>
        </div>

        {readyCount === 0 && (
          <p className="rounded-xl bg-white p-4 text-sm text-neutral-600 ring-1 ring-neutral-200 dark:bg-neutral-900 dark:text-neutral-300 dark:ring-neutral-800">
            You need at least one processed document to chat. <Link href="/documents" className="font-medium underline underline-offset-2">Upload one in My Documents</Link>.
          </p>
        )}
        {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <section className="overflow-hidden rounded-2xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900" aria-label="Your chats">
          <h2 className="border-b border-neutral-100 px-5 py-3.5 text-[15px] font-semibold dark:border-neutral-800">Your chats</h2>
          {chats.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
              <MessageSquare className="h-9 w-9" strokeWidth={1.5} />
              <p className="font-medium">No chats yet</p>
              <p className="text-sm text-neutral-500">Start one with “New chat”, then pick the documents to ask about.</p>
            </div>
          ) : (
            <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {chats.map((c) => (
                <li key={c.id} className="flex items-center gap-3 px-5 py-3">
                  <Link href={`/chat/${c.id}`} className="min-w-0 flex-1 rounded-lg py-1 hover:opacity-80">
                    <span className="block truncate text-[15px] font-medium">{c.title || "Untitled chat"}</span>
                    <span className="block truncate text-[13px] text-neutral-500">
                      {when(c.created_at)}
                      {c.preview ? ` · ${c.preview}` : ""}
                    </span>
                  </Link>
                  {confirming === c.id ? (
                    <span className="flex items-center gap-2">
                      <button onClick={() => remove(c.id)} disabled={deleting === c.id} className="rounded-lg bg-red-600 px-2.5 py-1 text-[12px] font-medium text-white disabled:opacity-60">
                        {deleting === c.id ? "Deleting…" : "Delete"}
                      </button>
                      <button onClick={() => setConfirming(null)} className="rounded-lg px-2 py-1 text-[12px] ring-1 ring-neutral-200 dark:ring-neutral-700">Cancel</button>
                    </span>
                  ) : (
                    <button onClick={() => setConfirming(c.id)} className="rounded-lg p-2 text-neutral-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40" aria-label={`Delete chat ${c.title || ""}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {scopeOpen && (
        <SelectChatScopeModal
          documents={documents}
          folders={folders}
          onConfirm={async (ids) => {
            setScopeOpen(false);
            await start(ids);
          }}
          onClose={() => setScopeOpen(false)}
        />
      )}
    </main>
  );
}
