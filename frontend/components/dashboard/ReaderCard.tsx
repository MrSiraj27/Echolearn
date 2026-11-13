"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Download,
  Expand,
  Loader2,
  MessageSquare,
  Search,
  Sparkles,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { api, ApiError, getMediaUrl } from "@/lib/api";
import { buildSegments, findMatches, locateSelection, type HighlightRange } from "@/lib/reader";
import type { DocumentItem, DocumentPagesResponse } from "@/lib/types";

const ZOOMS = [0.85, 1, 1.15, 1.3];

export interface Highlight {
  pageNumber: number;
  text: string;
}

/** The dashboard's middle card: read the selected document, select text to explain it. */
export default function ReaderCard({
  doc,
  pageNumber,
  onPageChange,
  highlight,
  onExplain,
  onChat,
  startingChat,
}: {
  doc: DocumentItem | null;
  pageNumber: number;
  onPageChange: (n: number) => void;
  highlight: Highlight | null;
  onExplain: (text: string, pageNumber: number) => void;
  onChat: () => void;
  startingChat: boolean;
}) {
  const [data, setData] = useState<DocumentPagesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [findOpen, setFindOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState<{ text: string; x: number; y: number } | null>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Reset when a different document is chosen (render-time, no effect needed).
  if ((doc?.id ?? null) !== loadedId) {
    setLoadedId(doc?.id ?? null);
    setData(null);
    setError(null);
    setPending(null);
  }

  useEffect(() => {
    if (!doc) return;
    let alive = true;
    api
      .get<DocumentPagesResponse>(`/documents/${doc.id}/pages`, { auth: true })
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.detail : "Couldn't open this document."));
    return () => {
      alive = false;
    };
  }, [doc]);

  const pages = useMemo(() => data?.pages ?? [], [data]);
  const idx = Math.max(0, pages.findIndex((p) => p.page_number === pageNumber));
  const page = pages[idx];
  const matches = useMemo(() => findMatches(pages, query), [pages, query]);

  const segments = useMemo(() => {
    if (!page) return [];
    const ranges: HighlightRange[] = matches
      .filter((m) => m.pageIndex === idx)
      .map((m) => ({ start: m.start, end: m.end, kind: "match" as const }));
    if (highlight && highlight.pageNumber === page.page_number) {
      const loc = locateSelection(page.text, highlight.text);
      if (loc) ranges.push({ ...loc, kind: "explained" });
    }
    return buildSegments(page.text, ranges);
  }, [page, matches, idx, highlight]);

  const go = useCallback(
    (i: number) => {
      const p = pages[Math.max(0, Math.min(pages.length - 1, i))];
      if (p) {
        onPageChange(p.page_number);
        setPending(null);
        boxRef.current?.scrollTo({ top: 0 });
      }
    },
    [pages, onPageChange]
  );

  function capture() {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? "";
    if (!sel || !text || !sel.rangeCount || !textRef.current?.contains(sel.getRangeAt(0).commonAncestorContainer) || !page) {
      setPending(null);
      return;
    }
    const r = sel.getRangeAt(0).getBoundingClientRect();
    setPending({ text: text.slice(0, 4000), x: Math.min(Math.max(r.left + r.width / 2, 90), window.innerWidth - 90), y: r.top > 70 ? r.top - 8 : r.bottom + 44 });
  }

  const pagesWithMatch = new Set(matches.map((m) => m.pageIndex));
  const firstMatchPage = [...pagesWithMatch].sort((a, b) => a - b).find((i) => i > idx) ?? [...pagesWithMatch].sort((a, b) => a - b)[0];

  return (
    <section className="flex h-[clamp(460px,72vh,780px)] min-w-0 flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white [grid-area:reader] dark:border-neutral-800 dark:bg-neutral-900" aria-label="Document reader">
      <div className="flex items-center gap-1 border-b border-neutral-200 px-3 dark:border-neutral-800">
        <span className="flex items-center gap-2 whitespace-nowrap border-b-2 border-coral px-2.5 py-3 text-[13px] font-medium text-neutral-950 dark:text-neutral-50">
          <BookOpen className="h-4 w-4" /> <span><span className="hidden sm:inline">Document </span>Reader</span>
        </span>
        <button
          onClick={onChat}
          disabled={!doc || startingChat}
          className="flex items-center gap-2 whitespace-nowrap px-2.5 py-3 text-[13px] text-neutral-500 hover:text-neutral-950 disabled:opacity-50 dark:hover:text-neutral-50"
        >
          {startingChat ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquare className="h-4 w-4" />} <span>Chat<span className="hidden sm:inline"> with Document</span></span>
        </button>
        <div className="ml-auto flex items-center gap-0.5">
          <button onClick={() => setFindOpen((v) => !v)} className="rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800" aria-label="Find in document" aria-pressed={findOpen}>
            <Search className="h-4 w-4" />
          </button>
          {doc && (
            <Link href={`/read/${doc.id}?page=${pageNumber}`} className="rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800" aria-label="Open full reader" title="Open full reader">
              <Expand className="h-4 w-4" />
            </Link>
          )}
        </div>
      </div>

      {findOpen && (
        <div className="flex items-center gap-2 border-b border-neutral-200 px-4 py-2 dark:border-neutral-800">
          <Search className="h-3.5 w-3.5 text-neutral-400" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && firstMatchPage !== undefined) go(firstMatchPage);
              if (e.key === "Escape") setFindOpen(false);
            }}
            placeholder="Find in this document"
            aria-label="Find in this document"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
          {query.trim().length >= 2 && (
            <span className="text-[11px] tabular-nums text-neutral-500">
              {matches.length} match{matches.length === 1 ? "" : "es"} on {pagesWithMatch.size} page{pagesWithMatch.size === 1 ? "" : "s"}
            </span>
          )}
          <button onClick={() => { setQuery(""); setFindOpen(false); }} className="p-1 text-neutral-400" aria-label="Close find">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div ref={boxRef} onScroll={() => pending && setPending(null)} className="min-h-0 flex-1 overflow-y-auto bg-neutral-100 p-2.5 sm:p-4 dark:bg-neutral-950/60">
        {!doc ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center text-sm text-neutral-500">
            <BookOpen className="h-8 w-8 text-neutral-300" />
            Upload a document, then open it here to read and highlight.
          </div>
        ) : error ? (
          <p className="p-8 text-center text-sm text-neutral-500">{error}</p>
        ) : !data ? (
          <div className="flex h-full items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-neutral-400" aria-label="Loading" /></div>
        ) : (
          <article
            ref={textRef}
            onMouseUp={capture}
            onTouchEnd={() => setTimeout(capture, 0)}
            className="mx-auto min-h-full max-w-[68ch] rounded-md bg-white px-5 py-6 ring-1 ring-neutral-200 sm:px-8 sm:py-8 dark:bg-neutral-900 dark:ring-neutral-800"
            style={{ fontSize: `${zoom * 0.95}rem` }}
          >
            <p className="mb-4 font-serif text-[0.95em] text-neutral-500">{data.filename.replace(/\.[^.]+$/, "")} · page {page?.page_number}</p>
            {page?.text.trim() ? (
              <p className="whitespace-pre-wrap break-words font-serif leading-[1.7] text-neutral-800 selection:bg-coral-soft dark:text-neutral-200 dark:selection:bg-coral-active/50">
                {segments.map((s, i) =>
                  s.kind ? (
                    <mark key={i} className={s.kind === "explained" ? "rounded-sm bg-amber-100 text-inherit underline decoration-amber-400 decoration-2 underline-offset-2 dark:bg-amber-900/40" : "rounded-sm bg-yellow-200 text-inherit dark:bg-yellow-700/60"}>
                      {s.text}
                    </mark>
                  ) : (
                    <span key={i}>{s.text}</span>
                  )
                )}
              </p>
            ) : (
              <p className="text-sm text-neutral-400">No text on this page.</p>
            )}
          </article>
        )}
      </div>

      {data && (
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-200 px-4 py-2.5 dark:border-neutral-800">
          <div className="flex items-center gap-1 rounded-full border border-neutral-200 px-1 dark:border-neutral-700">
            <button onClick={() => go(idx - 1)} disabled={idx === 0} className="rounded-full p-1.5 disabled:opacity-30" aria-label="Previous page"><ArrowLeft className="h-4 w-4" /></button>
            <span className="px-2 text-[13px] tabular-nums">{idx + 1} / {pages.length}</span>
            <button onClick={() => go(idx + 1)} disabled={idx >= pages.length - 1} className="rounded-full p-1.5 disabled:opacity-30" aria-label="Next page"><ArrowRight className="h-4 w-4" /></button>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setZoom((z) => ZOOMS[Math.max(0, ZOOMS.indexOf(z) - 1)])} disabled={zoom === ZOOMS[0]} className="rounded-lg p-1.5 disabled:opacity-30" aria-label="Zoom out"><ZoomOut className="h-4 w-4" /></button>
            <span className="w-11 text-center text-[13px] tabular-nums">{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom((z) => ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(z) + 1)])} disabled={zoom === ZOOMS[ZOOMS.length - 1]} className="rounded-lg p-1.5 disabled:opacity-30" aria-label="Zoom in"><ZoomIn className="h-4 w-4" /></button>
          </div>
          {doc && (
            <a href={getMediaUrl(doc.id)} target="_blank" rel="noopener noreferrer" className="rounded-lg p-1.5 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800" aria-label="Open the original file" title="Open the original file">
              <Download className="h-4 w-4" />
            </a>
          )}
        </footer>
      )}

      {pending && page && (
        <div className="fixed z-50 -translate-x-1/2 -translate-y-full" style={{ left: pending.x, top: pending.y }}>
          <div className="flex items-center gap-1 rounded-lg bg-neutral-900 p-1 text-xs text-white shadow-lg dark:bg-white dark:text-neutral-900">
            <button
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onExplain(pending.text, page.page_number);
                setPending(null);
                window.getSelection()?.removeAllRanges();
              }}
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-medium hover:bg-white/10 dark:hover:bg-black/10"
            >
              <Sparkles className="h-3.5 w-3.5" /> Explain with AI
            </button>
            <button onMouseDown={(e) => e.preventDefault()} onClick={() => setPending(null)} className="rounded-md p-1.5 hover:bg-white/10" aria-label="Dismiss">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
