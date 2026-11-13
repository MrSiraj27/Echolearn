"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUpRight, FileText, Lightbulb, ListChecks, Loader2, Send, Sparkles, Sigma } from "lucide-react";
import MicButton from "@/components/MicButton";
import ExplanationPanel, { type ExplanationThread } from "@/components/reader/ExplanationPanel";
import { useChatStore } from "@/lib/chat-store";
import type { Citation, DocumentItem } from "@/lib/types";

export type AssistantTab = "ask" | "explain" | "sources";

const STARTERS = [
  { icon: Lightbulb, text: "Explain the main concept simply" },
  { icon: ListChecks, text: "Summarize this document" },
  { icon: Sigma, text: "Give me examples" },
];

/** Right-hand AI panel on the dashboard: a chat about the selected document, the
 *  explanation of text selected in the reader, and the sources of the latest answer. */
export default function AssistantPanel({
  doc,
  tab,
  onTab,
  chatId,
  onChatId,
  thread,
  onAskAboutSelection,
  onRetryExplain,
  onGoToPage,
}: {
  doc: DocumentItem | null;
  tab: AssistantTab;
  onTab: (t: AssistantTab) => void;
  chatId: string | null;
  onChatId: (id: string) => void;
  thread: ExplanationThread | null;
  onAskAboutSelection: (q: string) => void;
  onRetryExplain: () => void;
  onGoToPage: (n: number) => void;
}) {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const createChat = useChatStore((s) => s.createChat);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const [input, setInput] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Only show messages that belong to this panel's chat.
  const shown = chatId ? messages : [];
  const lastAnswer = [...shown].reverse().find((m) => m.role === "assistant");
  const sources: Citation[] = (lastAnswer?.citations ?? []).filter((c) => c.page_number || c.chunk_text);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [shown.length, streamingContent]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || !doc || isStreaming || starting) return;
    setError(null);
    setInput("");
    let id = chatId;
    try {
      if (!id) {
        setStarting(true);
        id = await createChat([doc.id], doc.filename);
        useChatStore.setState({ messages: [], activeChatId: id });
        onChatId(id);
        setStarting(false);
      }
      await sendMessage(id, q);
    } catch (err) {
      setStarting(false);
      setError(err instanceof Error ? err.message : "Couldn't send that. Please try again.");
    }
  }

  const tabs: { id: AssistantTab; label: string }[] = [
    { id: "ask", label: "Ask a Question" },
    { id: "explain", label: "Explanation" },
    { id: "sources", label: "Sources" },
  ];

  return (
    <section className="flex h-[clamp(460px,72vh,780px)] min-w-0 flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white [grid-area:assistant] dark:border-neutral-800 dark:bg-neutral-900" aria-label="AI Assistant">
      <div className="flex items-center gap-2 px-5 pt-4">
        <Sparkles className="h-[18px] w-[18px] text-coral" />
        <h2 className="text-[15px] font-medium">AI Assistant</h2>
        {chatId && (
          <Link href={`/chat/${chatId}`} className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-neutral-800 dark:hover:text-white" title="Open as a full chat">
            Full chat <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
      <div role="tablist" aria-label="Assistant views" className="mx-4 mt-3 flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => onTab(t.id)}
            className={`-mb-px whitespace-nowrap border-b-2 px-2 py-2.5 text-[13px] ${
              tab === t.id ? "border-coral font-medium text-neutral-950 dark:text-neutral-50" : "border-transparent text-neutral-500 hover:text-neutral-900 dark:hover:text-white"
            }`}
          >
            {t.label}
            {t.id === "sources" && sources.length > 0 && <span className="ml-1 text-neutral-400">({sources.length})</span>}
          </button>
        ))}
      </div>

      {tab === "explain" ? (
        <div className="min-h-0 flex-1">
          <ExplanationPanel thread={thread} onAsk={onAskAboutSelection} onRetry={onRetryExplain} onClose={() => onTab("ask")} onGoToPage={onGoToPage} />
        </div>
      ) : tab === "sources" ? (
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
          {sources.length === 0 ? (
            <p className="py-10 text-center text-sm text-neutral-500">Ask a question and the passages used for the answer will appear here.</p>
          ) : (
            sources.map((c, i) => (
              <button
                key={i}
                onClick={() => c.page_number && onGoToPage(c.page_number)}
                className="block w-full rounded-xl border border-neutral-200 p-3 text-left hover:border-neutral-400 dark:border-neutral-700 dark:hover:border-neutral-500"
              >
                <span className="flex items-center gap-2 text-xs font-medium text-neutral-700 dark:text-neutral-200">
                  <FileText className="h-3.5 w-3.5" />
                  {c.page_number ? `Page ${c.page_number}` : "Passage"}
                </span>
                {c.chunk_text && <span className="mt-1 line-clamp-3 block text-xs text-neutral-500">{c.chunk_text}</span>}
              </button>
            ))
          )}
        </div>
      ) : (
        <>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4" aria-live="polite">
            {shown.length === 0 && !isStreaming ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 py-6 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-coral-soft text-coral-active dark:bg-neutral-800 dark:text-coral">
                  <Sparkles className="h-6 w-6" />
                </span>
                <p className="text-sm text-neutral-700 dark:text-neutral-300">
                  {doc ? <>Ask anything about <span className="font-medium">{doc.filename}</span></> : "Upload a document to start asking questions."}
                </p>
                {doc && (
                  <div className="flex flex-col items-center gap-2">
                    {STARTERS.map(({ icon: Icon, text }) => (
                      <button
                        key={text}
                        onClick={() => ask(text)}
                        className="flex items-center gap-2 rounded-full border border-neutral-200 px-3.5 py-1.5 text-[13px] text-neutral-800 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-200 dark:hover:bg-neutral-800"
                      >
                        <Icon className="h-3.5 w-3.5" /> {text}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {shown.map((m) =>
                  m.role === "user" ? (
                    <p key={m.id} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-neutral-100 px-3.5 py-2 text-sm text-neutral-950 dark:bg-neutral-800 dark:text-neutral-50">
                      {m.content}
                    </p>
                  ) : (
                    <div key={m.id} className="prose prose-sm max-w-none text-[13.5px] leading-relaxed text-neutral-800 dark:prose-invert dark:text-neutral-200">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                      {(m.citations?.length ?? 0) > 0 && (
                        <button onClick={() => onTab("sources")} className="not-prose mt-1 text-xs text-neutral-500 underline-offset-2 hover:underline">
                          {m.citations!.length} source{m.citations!.length > 1 ? "s" : ""}
                        </button>
                      )}
                    </div>
                  )
                )}
                {isStreaming && (
                  <div className="text-[13.5px] leading-relaxed text-neutral-800 dark:text-neutral-200">
                    {streamingContent ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingContent}</ReactMarkdown>
                    ) : (
                      <span className="flex items-center gap-2 text-neutral-500"><Loader2 className="h-4 w-4 animate-spin" /> Reading your document…</span>
                    )}
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}
            {error && <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void ask(input);
            }}
            className="flex items-center gap-2 border-t border-neutral-200 p-3 dark:border-neutral-800"
          >
            <MicButton disabled={!doc || isStreaming} onInterimResult={setInterim} onFinalResult={(t) => { setInterim(""); setInput((v) => (v ? `${v} ${t}` : t)); }} />
            <input
              value={interim || input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!doc}
              placeholder={doc ? "Type your question..." : "Upload a document first"}
              aria-label="Type your question"
              className="h-10 min-w-0 flex-1 rounded-lg border border-neutral-200 bg-white px-3.5 text-sm outline-none focus:border-coral focus:ring-[3px] focus:ring-coral/15 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-900"
            />
            <button
              type="submit"
              disabled={!doc || !input.trim() || isStreaming || starting}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-coral text-white hover:bg-coral-active disabled:bg-neutral-200 disabled:text-neutral-500 dark:disabled:bg-neutral-800"
              aria-label="Send question"
            >
              {starting || isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
