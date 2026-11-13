"use client";

import { useState } from "react";
import { Check, Copy, Loader2, Send, Sparkles, X } from "lucide-react";
import type { ExplainSelectionResponse, SelectionKind } from "@/lib/types";

export interface FollowUp {
  question: string;
  answer: string | null;
  loading: boolean;
  error: string | null;
}

export interface ExplanationThread {
  selectedText: string;
  pageNumber: number | null;
  loading: boolean;
  error: string | null;
  result: ExplainSelectionResponse | null;
  followUps: FollowUp[];
}

const KIND_LABEL: Record<SelectionKind, string> = {
  term: "Term",
  sentence: "Sentence",
  paragraph: "Passage",
  code: "Code",
  math: "Math",
};

function plainText(r: ExplainSelectionResponse): string {
  const parts = [r.simple_explanation ?? ""];
  if (r.key_points.length) parts.push("Key points:\n" + r.key_points.map((p) => `- ${p}`).join("\n"));
  if (r.example) parts.push(`Example: ${r.example}`);
  if (r.terms.length) parts.push("Terms:\n" + r.terms.map((t) => `- ${t.term}: ${t.meaning}`).join("\n"));
  return parts.filter(Boolean).join("\n\n");
}

export default function ExplanationPanel({
  thread,
  onAsk,
  onRetry,
  onClose,
  onGoToPage,
}: {
  thread: ExplanationThread | null;
  onAsk: (question: string) => void;
  onRetry: () => void;
  onClose: () => void;
  onGoToPage: (pageNumber: number) => void;
}) {
  const [question, setQuestion] = useState("");
  const [copied, setCopied] = useState(false);
  const busy = !!thread && (thread.loading || thread.followUps.some((f) => f.loading));

  function submit(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    onAsk(text);
    setQuestion("");
  }

  async function copy() {
    if (!thread?.result) return;
    try {
      await navigator.clipboard.writeText(plainText(thread.result));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked (permissions / insecure context); nothing useful to show.
    }
  }

  const r = thread?.result;
  const lastQuestions = thread?.followUps.length
    ? []
    : (r?.follow_up_questions ?? []);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-neutral-200 dark:border-neutral-800 px-4 py-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-neutral-900 dark:text-neutral-100">
          <Sparkles className="h-4 w-4 text-neutral-500" />
          AI explanation
        </h2>
        <button
          onClick={onClose}
          className="rounded p-1 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
          aria-label="Close explanation panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 text-sm" aria-live="polite">
        {!thread ? (
          <div className="text-neutral-500 dark:text-neutral-400 space-y-2">
            <p>Select a word, sentence or passage in the document, then choose <strong>Explain with AI</strong>.</p>
            <p className="text-xs">
              Explanations use the text around your selection and related parts of this document. Images and
              diagrams can&apos;t be explained yet: only selectable text is sent.
            </p>
          </div>
        ) : (
          <>
            <figure className="rounded-lg border-l-2 border-amber-400 bg-amber-50/60 dark:bg-amber-950/20 px-3 py-2">
              <blockquote className="max-h-32 overflow-y-auto whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
                {thread.selectedText}
              </blockquote>
              <figcaption className="mt-1 flex items-center gap-2 text-[11px] text-neutral-500">
                {r && <span className="rounded bg-white/70 dark:bg-neutral-800 px-1.5 py-0.5">{KIND_LABEL[r.kind]}</span>}
                {thread.pageNumber && <span>Page {thread.pageNumber}</span>}
              </figcaption>
            </figure>

            {thread.loading && (
              <p className="flex items-center gap-2 text-neutral-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Reading the surrounding text…
              </p>
            )}

            {thread.error && (
              <div role="alert" className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-3 py-2 text-red-700 dark:text-red-300">
                <p>{thread.error}</p>
                <button onClick={onRetry} className="mt-1 text-xs font-medium underline">
                  Try again
                </button>
              </div>
            )}

            {r && (
              <section className="space-y-4">
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400">In simple words</h3>
                    <button
                      onClick={copy}
                      className="flex items-center gap-1 text-[11px] text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
                      aria-label="Copy explanation"
                    >
                      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                      {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <p className="leading-relaxed text-neutral-800 dark:text-neutral-200">{r.simple_explanation}</p>
                </div>

                {r.key_points.length > 0 && (
                  <div>
                    <h3 className="mb-1 text-xs font-semibold text-neutral-500 dark:text-neutral-400">Key points</h3>
                    <ul className="list-disc space-y-1 pl-5 text-neutral-800 dark:text-neutral-200">
                      {r.key_points.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {r.example && (
                  <div>
                    <h3 className="mb-1 text-xs font-semibold text-neutral-500 dark:text-neutral-400">Example</h3>
                    <p className="leading-relaxed text-neutral-800 dark:text-neutral-200">{r.example}</p>
                  </div>
                )}

                {r.terms.length > 0 && (
                  <div>
                    <h3 className="mb-1 text-xs font-semibold text-neutral-500 dark:text-neutral-400">Terms</h3>
                    <dl className="space-y-1.5">
                      {r.terms.map((t) => (
                        <div key={t.term}>
                          <dt className="inline font-medium text-neutral-900 dark:text-neutral-100">{t.term}: </dt>
                          <dd className="inline text-neutral-700 dark:text-neutral-300">{t.meaning}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}

                {r.sources.some((s) => s.page_number) && (
                  <div>
                    <h3 className="mb-1 text-xs font-semibold text-neutral-500 dark:text-neutral-400">Based on</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {[...new Set(r.sources.map((s) => s.page_number).filter((n): n is number => !!n))].map((n) => (
                        <button
                          key={n}
                          onClick={() => onGoToPage(n)}
                          className="rounded-full border border-neutral-200 dark:border-neutral-700 px-2 py-0.5 text-xs text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                        >
                          Page {n}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {thread.followUps.map((f, i) => (
              <section key={i} className="space-y-1.5 border-t border-neutral-200 dark:border-neutral-800 pt-4">
                <p className="font-medium text-neutral-900 dark:text-neutral-100">{f.question}</p>
                {f.loading && (
                  <p className="flex items-center gap-2 text-neutral-500">
                    <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
                  </p>
                )}
                {f.error && <p role="alert" className="text-red-600 dark:text-red-400">{f.error}</p>}
                {f.answer && <p className="whitespace-pre-wrap leading-relaxed text-neutral-800 dark:text-neutral-200">{f.answer}</p>}
              </section>
            ))}

            {r && lastQuestions.length > 0 && (
              <div>
                <h3 className="mb-1.5 text-xs font-semibold text-neutral-500 dark:text-neutral-400">You could ask</h3>
                <div className="flex flex-col gap-1.5">
                  {lastQuestions.map((q) => (
                    <button
                      key={q}
                      onClick={() => submit(q)}
                      disabled={busy}
                      className="rounded-lg border border-neutral-200 dark:border-neutral-700 px-3 py-1.5 text-left text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {r && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(question);
          }}
          className="flex items-center gap-2 border-t border-neutral-200 dark:border-neutral-800 p-3"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={1000}
            placeholder="Ask about this selection…"
            aria-label="Ask a follow-up question"
            className="min-w-0 flex-1 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-sm outline-none focus:border-neutral-400"
          />
          <button
            type="submit"
            disabled={busy || !question.trim()}
            className="rounded-lg bg-neutral-900 dark:bg-neutral-100 p-2 text-white dark:text-neutral-900 disabled:opacity-40"
            aria-label="Send question"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      )}
    </div>
  );
}
