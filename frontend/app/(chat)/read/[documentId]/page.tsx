"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  MessageSquare,
  PanelLeft,
  Search,
  Sparkles,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import ExplanationPanel, { type ExplanationThread } from "@/components/reader/ExplanationPanel";
import ReadableText from "@/components/reader/ReadableText";
import { api, ApiError, getMediaUrl } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import {
  findMatches,
  formatPages,
  locateSelection,
  type HighlightRange,
  MAX_SEARCH_MATCHES,
} from "@/lib/reader";
import type { DocumentPagesResponse, ExplainSelectionResponse } from "@/lib/types";

const ZOOM_STEPS = [0.85, 1, 1.15, 1.3, 1.5, 1.75];
const MIN_PANEL = 300;
const MAX_PANEL = 640;

interface PendingSelection {
  text: string;
  pageNumber: number;
  x: number;
  y: number;
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

export default function ReaderPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const router = useRouter();
  const createChat = useChatStore((s) => s.createChat);

  const [doc, setDoc] = useState<DocumentPagesResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [zoomStep, setZoomStep] = useState(1);
  const [view, setView] = useState<"text" | "original">("text");

  const [query, setQuery] = useState("");
  const [activeMatch, setActiveMatch] = useState(0);

  const [leftOpen, setLeftOpen] = useState(true); // desktop
  const [mobileLeftOpen, setMobileLeftOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelWidth, setPanelWidth] = useState(380);

  const [pending, setPending] = useState<PendingSelection | null>(null);
  const [thread, setThread] = useState<ExplanationThread | null>(null);
  const [explained, setExplained] = useState<{ pageIndex: number; start: number; end: number } | null>(null);
  const [startingChat, setStartingChat] = useState(false);

  const textRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const requestSeq = useRef(0);

  // ---- load ----
  useEffect(() => {
    let cancelled = false;
    api
      .get<DocumentPagesResponse>(`/documents/${documentId}/pages`, { auth: true })
      .then((data) => {
        if (cancelled) return;
        setDoc(data);
        // ?page=N (e.g. from a chat citation) opens that page.
        const requested = Number(new URLSearchParams(window.location.search).get("page"));
        const idx = data.pages.findIndex((p) => p.page_number === requested);
        if (idx > 0) setPageIndex(idx);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(
          err instanceof ApiError
            ? err.status === 404 && err.detail === "Not Found"
              ? "This document doesn't exist (or was deleted)."
              : err.detail
            : "Couldn't open this document. Check your connection and try again."
        );
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  // Reflow extracted PDF lines into paragraphs, headings and code for comfortable reading.
  const pages = useMemo(() => formatPages(doc?.pages ?? []), [doc]);
  const total = pages.length;
  const page = pages[pageIndex];
  const isPdf = doc?.file_type === "pdf";
  const headings = useMemo(() => {
    const seen = new Set<string>();
    const out: { pageIndex: number; title: string }[] = [];
    pages.forEach((p, pageIndex) =>
      p.blocks.forEach((b) => {
        const title = p.text.slice(b.start, b.end).trim();
        if (b.kind !== "heading" || seen.has(title.toLowerCase()) || out.length >= 200) return;
        seen.add(title.toLowerCase());
        out.push({ pageIndex, title });
      })
    );
    return out;
  }, [pages]);
  const matches = useMemo(() => findMatches(pages, query), [pages, query]);
  const zoom = ZOOM_STEPS[zoomStep];

  const goTo = useCallback(
    (idx: number) => {
      if (!total) return;
      setPageIndex(Math.max(0, Math.min(total - 1, idx)));
      setPending(null);
      scrollRef.current?.scrollTo({ top: 0 });
    },
    [total]
  );
  const goToPageNumber = useCallback(
    (n: number) => {
      const idx = pages.findIndex((p) => p.page_number === n);
      if (idx !== -1) {
        goTo(idx);
        setMobileLeftOpen(false);
      }
    },
    [pages, goTo]
  );

  function jumpToMatch(i: number) {
    if (!matches.length) return;
    const next = ((i % matches.length) + matches.length) % matches.length;
    setActiveMatch(next);
    if (matches[next].pageIndex !== pageIndex) setPageIndex(matches[next].pageIndex);
  }

  // Scroll the active search match into view once its page has rendered.
  useEffect(() => {
    const el = textRef.current?.querySelector("[data-active-match]");
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeMatch, pageIndex, query]);

  // ---- highlights for the current page ----
  const highlightRanges = useMemo(() => {
    const ranges: HighlightRange[] = [];
    matches.forEach((m, i) => {
      if (m.pageIndex === pageIndex) ranges.push({ start: m.start, end: m.end, kind: i === activeMatch ? "active-match" : "match" });
    });
    if (explained && explained.pageIndex === pageIndex) ranges.push({ ...explained, kind: "explained" });
    return ranges;
  }, [matches, activeMatch, pageIndex, explained]);

  // ---- selection -> "Explain with AI" ----
  const captureSelection = useCallback(() => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? "";
    if (!sel || !text || sel.rangeCount === 0 || !textRef.current || !page) {
      setPending(null);
      return;
    }
    const range = sel.getRangeAt(0);
    if (!textRef.current.contains(range.commonAncestorContainer)) {
      setPending(null);
      return;
    }
    const rect = range.getBoundingClientRect();
    setPending({
      text: text.slice(0, 4000),
      pageNumber: page.page_number,
      x: Math.min(Math.max(rect.left + rect.width / 2, 90), window.innerWidth - 90),
      y: rect.top > 60 ? rect.top - 8 : rect.bottom + 44,
    });
  }, [page]);

  const runExplain = useCallback(
    async (selectedText: string, pageNumber: number) => {
      const seq = ++requestSeq.current;
      setPanelOpen(true);
      setThread({ selectedText, pageNumber, loading: true, error: null, result: null, followUps: [] });
      const idx = pages.findIndex((p) => p.page_number === pageNumber);
      const loc = idx !== -1 ? locateSelection(pages[idx].text, selectedText) : null;
      setExplained(loc ? { pageIndex: idx, ...loc } : null);
      try {
        const result = await api.post<ExplainSelectionResponse>(
          `/documents/${documentId}/explain`,
          { text: selectedText, page_number: pageNumber },
          { auth: true }
        );
        if (seq !== requestSeq.current) return; // a newer selection replaced this one
        setThread((t) => (t ? { ...t, loading: false, result } : t));
      } catch (err) {
        if (seq !== requestSeq.current) return;
        const message = err instanceof ApiError ? err.detail : "Couldn't reach the server. Please try again.";
        setThread((t) => (t ? { ...t, loading: false, error: message } : t));
      }
    },
    [documentId, pages]
  );

  function explainPending() {
    if (!pending) return;
    const { text, pageNumber } = pending;
    setPending(null);
    window.getSelection()?.removeAllRanges();
    void runExplain(text, pageNumber);
  }

  async function askFollowUp(question: string) {
    if (!thread?.result) return;
    const seq = requestSeq.current;
    const index = thread.followUps.length;
    const base = thread.result;
    const previous = [base.simple_explanation, ...base.key_points].filter(Boolean).join("\n");
    setThread((t) => (t ? { ...t, followUps: [...t.followUps, { question, answer: null, loading: true, error: null }] } : t));
    const update = (patch: Partial<ExplanationThread["followUps"][number]>) =>
      setThread((t) =>
        t && seq === requestSeq.current
          ? { ...t, followUps: t.followUps.map((f, i) => (i === index ? { ...f, ...patch } : f)) }
          : t
      );
    try {
      const res = await api.post<ExplainSelectionResponse>(
        `/documents/${documentId}/explain`,
        { text: thread.selectedText, page_number: thread.pageNumber, question, previous_explanation: previous },
        { auth: true }
      );
      update({ loading: false, answer: res.answer });
    } catch (err) {
      update({ loading: false, error: err instanceof ApiError ? err.detail : "Couldn't get an answer. Please try again." });
    }
  }

  async function chatAboutDocument() {
    if (!doc || startingChat) return;
    setStartingChat(true);
    try {
      const chatId = await createChat([doc.document_id], doc.filename);
      router.push(`/chat/${chatId}`);
    } catch {
      setStartingChat(false);
    }
  }

  // ---- keyboard shortcuts ----
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f" && view === "text") {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
        return;
      }
      if (isTypingTarget(e.target)) return;
      if (e.key === "ArrowRight" || e.key === "PageDown") goTo(pageIndex + 1);
      else if (e.key === "ArrowLeft" || e.key === "PageUp") goTo(pageIndex - 1);
      else if (e.key === "Escape") {
        if (pending) setPending(null);
        else setPanelOpen(false);
      } else if (e.key.toLowerCase() === "e" && pending) {
        e.preventDefault();
        explainPending();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // ---- resizable explanation panel (desktop) ----
  function startResize(e: React.PointerEvent) {
    e.preventDefault();
    const move = (ev: PointerEvent) =>
      setPanelWidth(Math.max(MIN_PANEL, Math.min(MAX_PANEL, window.innerWidth - ev.clientX)));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  const navList = (
    <nav aria-label="Document navigation" className="flex h-full flex-col">
      {headings.length > 0 && (
        <div className="border-b border-neutral-200 dark:border-neutral-800 px-3 py-3">
          <h2 className="mb-1.5 text-[11px] font-semibold uppercase text-neutral-400">Sections (detected)</h2>
          <ul className="max-h-56 space-y-0.5 overflow-y-auto">
            {headings.map((h, i) => (
              <li key={i}>
                <button
                  onClick={() => goToPageNumber(pages[h.pageIndex].page_number)}
                  className={`w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-neutral-100 dark:hover:bg-neutral-800 ${
                    h.pageIndex === pageIndex ? "text-neutral-900 dark:text-neutral-100 font-medium" : "text-neutral-600 dark:text-neutral-400"
                  }`}
                  title={h.title}
                >
                  {h.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <h2 className="px-3 pt-3 pb-1.5 text-[11px] font-semibold uppercase text-neutral-400">Pages</h2>
      <ul className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {pages.map((p, i) => (
          <li key={p.page_number}>
            <button
              onClick={() => {
                goTo(i);
                setMobileLeftOpen(false);
              }}
              aria-current={i === pageIndex ? "page" : undefined}
              className={`flex w-full gap-2 rounded px-2 py-1.5 text-left text-xs ${
                i === pageIndex
                  ? "bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100"
                  : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
              }`}
            >
              <span className="w-6 shrink-0 tabular-nums text-neutral-400">{p.page_number}</span>
              <span className="line-clamp-2">{p.text.trim().slice(0, 90) || "(no text on this page)"}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );

  return (
    <>
      <main className="flex min-w-0 flex-1 flex-col">
        {/* toolbar */}
        <header className="flex flex-wrap items-center gap-2 border-b border-neutral-200 dark:border-neutral-800 px-3 py-2 py-2">
          <button
            onClick={() => router.back()}
            className="rounded p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Back"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              setLeftOpen((v) => !v);
              setMobileLeftOpen((v) => !v);
            }}
            className="rounded p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Toggle pages and sections"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
          <h1 className="min-w-[8rem] flex-1 truncate text-sm font-medium text-neutral-900 dark:text-neutral-100" title={doc?.filename}>
            {doc?.filename ?? "Document"}
          </h1>

          {doc && (
            <>
              {view === "text" && (
                <div className="order-last flex w-full items-center gap-1 rounded-lg border border-neutral-200 dark:border-neutral-700 px-2 sm:order-none sm:w-auto">
                  <Search className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
                  <input
                    ref={searchRef}
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setActiveMatch(0);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") jumpToMatch(activeMatch + (e.shiftKey ? -1 : 1));
                      if (e.key === "Escape") setQuery("");
                    }}
                    placeholder="Find in document"
                    aria-label="Find in document"
                    className="min-w-0 flex-1 bg-transparent py-1.5 text-sm outline-none sm:w-40"
                  />
                  {query.trim().length >= 2 && (
                    <span className="shrink-0 text-[11px] tabular-nums text-neutral-400" aria-live="polite">
                      {matches.length ? `${activeMatch + 1}/${matches.length}${matches.length >= MAX_SEARCH_MATCHES ? "+" : ""}` : "0"}
                    </span>
                  )}
                  <button onClick={() => jumpToMatch(activeMatch - 1)} disabled={!matches.length} className="p-0.5 text-neutral-400 disabled:opacity-30" aria-label="Previous match">
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={() => jumpToMatch(activeMatch + 1)} disabled={!matches.length} className="p-0.5 text-neutral-400 disabled:opacity-30" aria-label="Next match">
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}

              {view === "text" && (
                <div className="flex items-center">
                  <button onClick={() => setZoomStep((z) => Math.max(0, z - 1))} disabled={zoomStep === 0} className="rounded p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-30" aria-label="Zoom out">
                    <ZoomOut className="h-4 w-4" />
                  </button>
                  <span className="w-10 text-center text-[11px] tabular-nums text-neutral-500">{Math.round(zoom * 100)}%</span>
                  <button onClick={() => setZoomStep((z) => Math.min(ZOOM_STEPS.length - 1, z + 1))} disabled={zoomStep === ZOOM_STEPS.length - 1} className="rounded p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-30" aria-label="Zoom in">
                    <ZoomIn className="h-4 w-4" />
                  </button>
                </div>
              )}

              {isPdf && (
                <div className="flex rounded-lg border border-neutral-200 dark:border-neutral-700 p-0.5 text-xs" role="group" aria-label="View">
                  {(["text", "original"] as const).map((v) => (
                    <button
                      key={v}
                      onClick={() => setView(v)}
                      aria-pressed={view === v}
                      className={`rounded-md px-2 py-1 ${view === v ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900" : "text-neutral-600 dark:text-neutral-300"}`}
                    >
                      {v === "text" ? "Text" : "Original"}
                    </button>
                  ))}
                </div>
              )}

              <button
                onClick={chatAboutDocument}
                disabled={startingChat}
                className="flex items-center gap-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 px-2.5 py-1.5 text-xs text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50"
              >
                {startingChat ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquare className="h-3.5 w-3.5" />}
                <span className="hidden sm:inline">Chat</span>
              </button>
              <button
                onClick={() => setPanelOpen((v) => !v)}
                aria-pressed={panelOpen}
                className="flex items-center gap-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 px-2.5 py-1.5 text-xs text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Explain</span>
              </button>
            </>
          )}
        </header>

        {/* reading progress */}
        {total > 0 && (
          <div className="h-0.5 bg-neutral-100 dark:bg-neutral-900" role="progressbar" aria-label="Reading progress" aria-valuemin={1} aria-valuemax={total} aria-valuenow={pageIndex + 1}>
            <div className="h-full bg-neutral-900 dark:bg-neutral-100 transition-[width] duration-200" style={{ width: `${((pageIndex + 1) / total) * 100}%` }} />
          </div>
        )}

        <div className="relative flex min-h-0 flex-1">
          {/* left: pages + sections */}
          {doc && leftOpen && (
            <aside className="hidden w-60 shrink-0 border-r border-neutral-200 dark:border-neutral-800 lg:block">{navList}</aside>
          )}
          {doc && mobileLeftOpen && (
            <div className="fixed inset-0 z-40 lg:hidden">
              <button className="absolute inset-0 bg-black/30" aria-label="Close navigation" onClick={() => setMobileLeftOpen(false)} />
              <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-white dark:bg-neutral-950 shadow-xl">{navList}</aside>
            </div>
          )}

          {/* center: reader */}
          <section className="flex min-w-0 flex-1 flex-col">
            {!doc ? (
              <div className="flex flex-1 items-center justify-center p-6 text-center">
                {loadError ? (
                  <div className="max-w-sm space-y-3">
                    <FileText className="mx-auto h-8 w-8 text-neutral-300" />
                    <p className="text-sm text-neutral-600 dark:text-neutral-400">{loadError}</p>
                    <button onClick={() => router.push("/documents")} className="text-sm font-medium underline">
                      Back to your documents
                    </button>
                  </div>
                ) : (
                  <Loader2 className="h-5 w-5 animate-spin text-neutral-400" aria-label="Loading document" />
                )}
              </div>
            ) : view === "original" ? (
              <div className="flex min-h-0 flex-1 flex-col">
                {/* Many mobile browsers (e.g. Android Chrome) can't show a PDF inside a page. */}
                <p className="border-b border-neutral-200 dark:border-neutral-800 px-4 py-1.5 text-[11px] text-neutral-500">
                  Showing the original file. Text selection and AI explanations work in Text view.{" "}
                  <a
                    href={`${getMediaUrl(doc.document_id)}#page=${page?.page_number ?? 1}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium underline"
                  >
                    Blank? Open it in a new tab
                  </a>
                </p>
                <iframe
                  key={pageIndex}
                  src={`${getMediaUrl(doc.document_id)}#page=${page?.page_number ?? 1}`}
                  title={`${doc.filename} (original)`}
                  className="h-full w-full flex-1 border-0 bg-neutral-100 dark:bg-neutral-900"
                />
              </div>
            ) : (
              <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 sm:px-6" onScroll={() => pending && setPending(null)}>
                <article
                  ref={textRef}
                  onMouseUp={captureSelection}
                  onKeyUp={(e) => e.shiftKey && captureSelection()}
                  onTouchEnd={() => setTimeout(captureSelection, 0)}
                  className="mx-auto my-4 max-w-[44rem] rounded-xl bg-white px-6 py-9 shadow-sm ring-1 ring-neutral-200 selection:bg-coral-soft sm:my-8 sm:px-12 sm:py-12 dark:bg-neutral-900 dark:ring-neutral-800 dark:selection:bg-coral-active/40"
                  style={{ fontSize: `${zoom * 1.0625}rem` }}
                  aria-label={`Page ${page?.page_number} of ${total}`}
                >
                  {page && page.text.trim() ? (
                    <ReadableText text={page.text} blocks={page.blocks} ranges={highlightRanges} />
                  ) : (
                    <p className="text-sm text-neutral-400">
                      No text was found on this page{isPdf ? " (it may be an image). Switch to Original to see it." : "."}
                    </p>
                  )}
                  <p className="mt-10 text-center font-sans text-[12px] tabular-nums text-neutral-400" aria-hidden>
                    {page?.page_number} / {total}
                  </p>
                </article>
              </div>
            )}

            {/* page navigation */}
            {doc && (
              <footer className="flex items-center justify-center gap-3 border-t border-neutral-200 dark:border-neutral-800 px-3 py-2 text-sm">
                <button onClick={() => goTo(pageIndex - 1)} disabled={pageIndex === 0} className="rounded p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-30" aria-label="Previous page">
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <label className="flex items-center gap-1.5 text-xs text-neutral-500">
                  Page
                  <input
                    key={pageIndex}
                    type="number"
                    min={1}
                    max={total}
                    defaultValue={pageIndex + 1}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") goTo(Number(e.currentTarget.value) - 1);
                    }}
                    onBlur={(e) => goTo(Number(e.currentTarget.value) - 1)}
                    className="w-14 rounded border border-neutral-200 dark:border-neutral-700 bg-transparent px-1.5 py-0.5 text-center tabular-nums"
                    aria-label="Go to page"
                  />
                  of {total}
                </label>
                <button onClick={() => goTo(pageIndex + 1)} disabled={pageIndex >= total - 1} className="rounded p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-30" aria-label="Next page">
                  <ChevronRight className="h-4 w-4" />
                </button>
              </footer>
            )}
          </section>

          {/* right: explanation panel. Wide screens: resizable column beside the text.
              Laptop widths: overlay drawer (a column would squeeze the text to nothing next
              to the app sidebar and page list). Phones: bottom sheet. */}
          {panelOpen && (
            <>
              <aside className="relative hidden shrink-0 border-l border-neutral-200 dark:border-neutral-800 xl:block" style={{ width: panelWidth }}>
                <div
                  onPointerDown={startResize}
                  className="absolute inset-y-0 -left-1 z-10 w-2 cursor-col-resize hover:bg-neutral-200/70 dark:hover:bg-neutral-700/70"
                  role="separator"
                  aria-orientation="vertical"
                  aria-label="Resize explanation panel"
                />
                <ExplanationPanel
                  thread={thread}
                  onAsk={askFollowUp}
                  onRetry={() => thread && runExplain(thread.selectedText, thread.pageNumber ?? page?.page_number ?? 1)}
                  onClose={() => setPanelOpen(false)}
                  onGoToPage={goToPageNumber}
                />
              </aside>
              <div className="fixed inset-x-0 bottom-0 z-40 h-[70vh] rounded-t-2xl border-t border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 shadow-2xl lg:inset-y-0 lg:left-auto lg:right-0 lg:h-full lg:w-[400px] lg:rounded-none lg:border-l lg:border-t-0 xl:hidden">
                <ExplanationPanel
                  thread={thread}
                  onAsk={askFollowUp}
                  onRetry={() => thread && runExplain(thread.selectedText, thread.pageNumber ?? page?.page_number ?? 1)}
                  onClose={() => setPanelOpen(false)}
                  onGoToPage={goToPageNumber}
                />
              </div>
            </>
          )}
        </div>
      </main>

      {/* floating action for a fresh selection */}
      {pending && (
        <div className="fixed z-50 -translate-x-1/2 -translate-y-full" style={{ left: pending.x, top: pending.y }}>
          <div className="flex items-center gap-1 rounded-lg bg-neutral-900 p-1 text-xs text-white shadow-lg dark:bg-neutral-100 dark:text-neutral-900">
            <button onMouseDown={(e) => e.preventDefault()} onClick={explainPending} className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-medium hover:bg-white/10 dark:hover:bg-black/10">
              <Sparkles className="h-3.5 w-3.5" />
              Explain with AI
            </button>
            <button
              onMouseDown={(e) => e.preventDefault()}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(pending.text);
                } catch {
                  // clipboard blocked; the browser's own copy (Ctrl+C) still works on the selection
                }
                setPending(null);
              }}
              className="rounded-md px-2.5 py-1.5 hover:bg-white/10 dark:hover:bg-black/10"
            >
              Copy
            </button>
            <button onMouseDown={(e) => e.preventDefault()} onClick={() => setPending(null)} className="rounded-md p-1.5 hover:bg-white/10 dark:hover:bg-black/10" aria-label="Dismiss">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
