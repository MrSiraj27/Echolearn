"use client";

import Link from "next/link";
import { BookOpen, Loader2 } from "lucide-react";
import { DocTypeIcon, docMeta, isReady, StatusPill } from "@/components/documents/docUi";
import { useChatStore } from "@/lib/chat-store";

/** Document Reader: choose what to read. */
export default function ReaderIndexPage() {
  const documents = useChatStore((s) => s.documents);
  const loaded = useChatStore((s) => s.documentsLoaded);
  const ready = documents.filter(isReady);
  const waiting = documents.filter((d) => !isReady(d) && d.status !== "failed");

  return (
    <main className="min-w-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight"><BookOpen className="h-7 w-7" /> Document Reader</h1>
          <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">Open a document to read it page by page. Select any word or passage to get a simple explanation.</p>
        </div>

        {!loaded ? (
          <div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-neutral-400" aria-label="Loading documents" /></div>
        ) : ready.length === 0 ? (
          <div className="rounded-2xl border border-neutral-200 bg-white px-6 py-14 text-center dark:border-neutral-800 dark:bg-neutral-900">
            <p className="font-medium">Nothing to read yet</p>
            <p className="mt-1 text-sm text-neutral-500">
              {waiting.length ? "Your documents are still processing. They'll appear here when ready." : "Upload a document to start reading."}{" "}
              <Link href="/documents" className="font-medium text-neutral-900 underline underline-offset-2 dark:text-white">Go to My Documents</Link>
            </p>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ready.map((d) => (
              <li key={d.id}>
                <Link href={`/read/${d.id}`} className="flex h-full flex-col gap-3 rounded-2xl border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-400 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-600">
                  <span className="flex items-start gap-3">
                    <DocTypeIcon fileType={d.file_type} size={40} />
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 font-medium" title={d.filename}>{d.filename}</span>
                      <span className="block text-[12px] text-neutral-500">{docMeta(d)}</span>
                    </span>
                  </span>
                  {d.summary && <span className="line-clamp-3 text-[13px] text-neutral-600 dark:text-neutral-400">{d.summary}</span>}
                  <span className="mt-auto flex items-center justify-between">
                    <StatusPill doc={d} />
                    <span className="text-[13px] font-medium">Read →</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
