"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnimatePresence } from "framer-motion";
import { ArrowLeft, BookOpen, Check, Download, Lightbulb, Loader2, Send, SkipForward, Sparkles } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import SourceViewer from "@/components/SourceViewer";
import { TranslationBody } from "@/components/LanguageExplain";
import { api, ApiError, getAccessToken } from "@/lib/api";
import { Citation, TutorSession, TutorSourceRef, TutorSummary, TutorTurn } from "@/lib/types";

const PROSE =
  "prose prose-sm dark:prose-invert prose-neutral max-w-none break-words text-neutral-800 dark:text-neutral-200 leading-relaxed";

// Soft cues only: green for correct, amber for "keep going". No red, no scores.
const VERDICT_STYLE: Record<string, string> = {
  correct: "border-l-4 border-emerald-300 dark:border-emerald-700 bg-emerald-50/60 dark:bg-emerald-950/20",
  partial: "border-l-4 border-amber-300 dark:border-amber-700 bg-amber-50/60 dark:bg-amber-950/20",
  incorrect: "border-l-4 border-amber-300 dark:border-amber-700 bg-amber-50/60 dark:bg-amber-950/20",
  skipped: "border-l-4 border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900/50",
};

function TutorText({ text, language }: { text: string; language: string }) {
  if (language === "ur" || language === "roman_ur") {
    return <TranslationBody text={text} language={language} />;
  }
  return (
    <div className={PROSE}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

function SourceChips({ refs, onOpen }: { refs: TutorSourceRef[] | null; onOpen: (c: Citation) => void }) {
  if (!refs || refs.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {refs.slice(0, 3).map((r, i) => {
        const label = `${r.filename ?? "Source"}${r.page_number != null ? ` · p.${r.page_number}` : ""}`;
        const openable = r.document_id && r.page_number != null;
        return openable ? (
          <button
            key={i}
            onClick={() => onOpen({ filename: r.filename, page_number: r.page_number, document_id: r.document_id })}
            className="inline-flex items-center gap-1 text-[11px] rounded-full border border-neutral-200 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 px-2 py-0.5 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            title="Open the passage this is based on"
          >
            <BookOpen className="h-3 w-3" />
            Source: {label}
          </button>
        ) : (
          <span key={i} className="text-[11px] text-neutral-400 px-1">
            {label}
          </span>
        );
      })}
    </div>
  );
}

function summaryToText(topic: string, s: TutorSummary): string {
  const lines = [`Tutor session: ${topic}`, ""];
  if (s.mastered_count != null) lines.push(`Mastered ${s.mastered_count} of ${s.total_concepts} concepts.`, "");
  if (s.strengths.length) lines.push("What went well:", ...s.strengths.map((x) => `- ${x}`), "");
  if (s.needs_work.length) lines.push("To review:", ...s.needs_work.map((n) => `- ${n.concept}: ${n.why}`), "");
  if (s.next_steps.length) lines.push("Next steps:", ...s.next_steps.map((x) => `- ${x}`));
  return lines.join("\n");
}

export default function TutorSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const [session, setSession] = useState<TutorSession | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [input, setInput] = useState("");
  const [draft, setDraft] = useState<string | null>(null); // tutor reply being streamed
  const [pendingStudent, setPendingStudent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const endRequested = useRef(false);
  const [endingEarly, setEndingEarly] = useState(false);
  const [endFailed, setEndFailed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Citation | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    const data = await api.get<TutorSession>(`/tutor/sessions/${sessionId}`, { auth: true });
    setSession(data);
    return data;
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;
    api
      .get<TutorSession>(`/tutor/sessions/${sessionId}`, { auth: true })
      .then((data) => {
        if (!cancelled) setSession(data); // resumes exactly where the database says we were
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else setError("Couldn't load this session.");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [session?.turns.length, draft, pendingStudent, session?.status]);

  // When the last concept is done (or the turn limit is hit) the session asks to be finished:
  // we call /end once, which writes the summary and adds the flashcards.
  const finishSession = useCallback(() => {
    endRequested.current = true;
    setEndFailed(false);
    setEndingEarly(true);
    api
      .post<{ session: TutorSession }>(`/tutor/sessions/${sessionId}/end`, {}, { auth: true })
      .then((res) => setSession(res.session))
      .catch((err) => {
        endRequested.current = false;
        setEndFailed(true);
        setError(err instanceof ApiError ? err.detail : "Couldn't finish the session. Please try again.");
      })
      .finally(() => setEndingEarly(false));
  }, [sessionId]);

  const needsEnd = !!session && session.finished && session.status === "active";
  useEffect(() => {
    if (needsEnd && !busy && !endRequested.current) finishSession();
  }, [needsEnd, busy, finishSession]);

  async function runAction(path: "hint" | "just-tell-me" | "skip") {
    if (busy || !session || session.status !== "active") return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.post<{ session: TutorSession }>(`/tutor/sessions/${sessionId}/${path}`, {}, { auth: true });
      setSession(res.session);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "The tutor couldn't respond just now. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function sendAnswer() {
    const content = input.trim();
    if (!content || busy || !session || session.status !== "active") return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setInput("");
    setPendingStudent(content);
    setDraft("");

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const token = getAccessToken();
    try {
      const res = await fetch(`${apiUrl}/tutor/sessions/${sessionId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        credentials: "include",
        body: JSON.stringify({ content }),
      });
      if (!res.ok || !res.body) {
        const detail = await res.json().then((d) => d.detail).catch(() => null);
        throw new Error(detail || "The tutor couldn't respond just now.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let text = "";
      let retry = false;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          let event = "message";
          let data = "";
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            if (line.startsWith("data:")) data = line.slice(5).trim();
          }
          if (!data) continue;
          const parsed = JSON.parse(data);
          if (event === "token") {
            text += parsed.content;
            setDraft(text);
          } else if (event === "replace") {
            text = parsed.content;
            setDraft(text);
          } else if (event === "done" && parsed.retry) {
            retry = true;
          }
        }
      }
      if (retry) {
        // Nothing was saved or charged: give the answer back and show the gentle message.
        setInput(content);
        setNotice(text || "Let's try that again. Could you say your answer once more?");
      }
      await refresh();
    } catch (err) {
      setInput(content);
      setError(err instanceof Error ? err.message : "The tutor couldn't respond just now.");
    } finally {
      setDraft(null);
      setPendingStudent(null);
      setBusy(false);
    }
  }

  function downloadSummary() {
    if (!session?.summary) return;
    const blob = new Blob([summaryToText(session.topic, session.summary)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tutor-${session.topic.replace(/[^A-Za-z0-9]+/g, "_").slice(0, 40) || "summary"}.txt`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  if (notFound) {
    return (
      <>
        <Sidebar />
        <main className="flex-1 px-6 py-10 bg-white dark:bg-neutral-950">
          <p className="text-sm text-neutral-500">This session doesn&apos;t exist (or was deleted).</p>
        </main>
      </>
    );
  }
  if (!session) {
    return (
      <>
        <Sidebar />
        <main className="flex-1 px-6 py-10 bg-white dark:bg-neutral-950">
          {error ? <p className="text-sm text-red-600">{error}</p> : <Loader2 className="h-4 w-4 animate-spin text-neutral-400" />}
        </main>
      </>
    );
  }

  const p = session.progress;
  const active = session.status === "active" && !session.finished;
  const showHintLevel = active && p.hint_level > 0 && p.phase !== "check" && p.hint_level < 4;
  const lastTutorTurn = [...session.turns].reverse().find((t) => t.role === "tutor");

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 flex flex-col h-screen bg-white dark:bg-neutral-950">
        <div className="border-b border-neutral-200 dark:border-neutral-800 px-4 sm:px-6 pt-14 lg:pt-4 pb-3">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center justify-between gap-3">
              <button
                onClick={() => router.push("/tutor")}
                className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
              >
                <ArrowLeft className="h-3 w-3" />
                Tutor
              </button>
              <p className="text-xs text-neutral-400 truncate">{session.topic}</p>
            </div>

            {/* progress strip */}
            <div className="mt-3 flex items-center gap-3">
              <p className="text-xs font-medium text-neutral-700 dark:text-neutral-300 shrink-0">
                Concept {Math.min(p.concept_index + 1, p.total_concepts)} of {p.total_concepts}
              </p>
              <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                {p.concepts.map((c) => (
                  <span
                    key={c.index}
                    title={`${c.name}${c.mastered ? " – mastered" : c.revealed ? " – explained" : ""}`}
                    className={`h-2.5 w-7 rounded-full ${
                      c.mastered
                        ? "bg-emerald-400 dark:bg-emerald-600"
                        : c.revealed
                          ? "bg-amber-300 dark:bg-amber-600"
                          : c.index === p.concept_index && session.status === "active"
                            ? "bg-neutral-900 dark:bg-neutral-100"
                            : "bg-neutral-200 dark:bg-neutral-800"
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5">
          <div className="max-w-2xl mx-auto space-y-4">
            {session.turns.map((turn: TutorTurn) =>
              turn.role === "student" ? (
                <div key={turn.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 px-4 py-2.5 text-sm whitespace-pre-wrap">
                    {turn.content}
                  </div>
                </div>
              ) : (
                <div key={turn.id} className="flex justify-start">
                  <div
                    className={`max-w-[92%] rounded-2xl rounded-bl-sm px-4 py-3 ${
                      turn.verdict ? VERDICT_STYLE[turn.verdict] : "bg-neutral-50 dark:bg-neutral-900/60"
                    } ${turn.turn_type === "summary" ? "bg-neutral-100 dark:bg-neutral-800" : ""}`}
                  >
                    <TutorText text={turn.content} language={session.language} />
                    {turn.turn_type !== "summary" && <SourceChips refs={turn.source_refs} onOpen={setViewing} />}
                  </div>
                </div>
              )
            )}

            {pendingStudent && (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 px-4 py-2.5 text-sm whitespace-pre-wrap">
                  {pendingStudent}
                </div>
              </div>
            )}
            {draft !== null && (
              <div className="flex justify-start">
                <div className="max-w-[92%] rounded-2xl rounded-bl-sm bg-neutral-50 dark:bg-neutral-900/60 px-4 py-3">
                  {draft ? (
                    <TutorText text={draft} language={session.language} />
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs text-neutral-400">
                      <Loader2 className="h-3 w-3 animate-spin" /> Thinking…
                    </span>
                  )}
                </div>
              </div>
            )}

            {notice && (
              <p className="text-sm text-neutral-600 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-900/60 rounded-xl px-4 py-3">
                {notice}
              </p>
            )}

            {/* end screen */}
            {needsEnd && !endFailed && (
              <p className="text-sm text-neutral-500 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Preparing your summary…
              </p>
            )}
            {needsEnd && endFailed && (
              <button
                onClick={finishSession}
                className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-2 text-neutral-700 dark:text-neutral-300"
              >
                Try getting the summary again
              </button>
            )}
            {session.status === "completed" && session.summary && (
              <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-5 space-y-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-neutral-500" />
                  <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Session summary</h2>
                </div>
                {session.summary.strengths.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400 mb-1">What went well</p>
                    <ul className="space-y-1">
                      {session.summary.strengths.map((s, i) => (
                        <li key={i} className="text-sm text-neutral-700 dark:text-neutral-300 flex gap-2">
                          <Check className="h-4 w-4 shrink-0 mt-0.5 text-emerald-500" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {session.summary.needs_work.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">Worth another look</p>
                    <ul className="space-y-2">
                      {session.summary.needs_work.map((n, i) => (
                        <li key={i} className="text-sm text-neutral-700 dark:text-neutral-300">
                          <span className="font-medium">{n.concept}</span>: {n.why}
                          <SourceChips refs={n.source_refs} onOpen={setViewing} />
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {session.summary.next_steps.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-neutral-500 mb-1">Next steps</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      {session.summary.next_steps.map((s, i) => (
                        <li key={i} className="text-sm text-neutral-700 dark:text-neutral-300">
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  {session.summary.cards_added
                    ? `${session.summary.cards_added} flashcard${session.summary.cards_added === 1 ? "" : "s"} added to your Daily Review.`
                    : "No new flashcards were needed."}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Link
                    href="/review"
                    className="text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
                  >
                    Start Daily Review
                  </Link>
                  <button
                    onClick={downloadSummary}
                    className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Save summary
                  </button>
                  <Link
                    href="/tutor"
                    className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
                  >
                    New session
                  </Link>
                </div>
              </section>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* answer box + the three always-visible helpers */}
        {session.status === "active" && (
          <div className="border-t border-neutral-200 dark:border-neutral-800 px-4 sm:px-6 py-3">
            <div className="max-w-2xl mx-auto">
              {error && <p className="text-xs text-red-600 dark:text-red-400 mb-2">{error}</p>}
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void sendAnswer();
                    }
                  }}
                  disabled={!active || busy}
                  rows={2}
                  maxLength={2000}
                  dir="auto"
                  placeholder={active ? "Type your answer…" : "Finishing up…"}
                  className="flex-1 resize-none text-sm rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100 disabled:opacity-60"
                />
                <button
                  onClick={() => void sendAnswer()}
                  disabled={!active || busy || !input.trim()}
                  aria-label="Send answer"
                  className="h-10 w-10 shrink-0 flex items-center justify-center rounded-xl bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 disabled:opacity-40 transition-opacity"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </button>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                {/* three equal buttons: "Just tell me" is never hidden, shamed or behind a dialog */}
                {(
                  [
                    { key: "hint", label: "Hint", icon: Lightbulb },
                    { key: "just-tell-me", label: "Just tell me", icon: BookOpen },
                    { key: "skip", label: "Skip", icon: SkipForward },
                  ] as const
                ).map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    onClick={() => void runAction(key)}
                    disabled={!active || busy}
                    className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50"
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </button>
                ))}
                {showHintLevel && (
                  <span className="text-[11px] text-neutral-500 dark:text-neutral-400 ml-1">Hint {p.hint_level} of 4</span>
                )}
                <span className="ml-auto text-[11px] text-neutral-400">
                  {session.turn_count} / {session.max_turns} turns
                </span>
                <button
                  onClick={finishSession}
                  disabled={busy || endingEarly}
                  title="Stop here and see your summary"
                  className="flex items-center gap-1 text-[11px] text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 underline-offset-2 hover:underline disabled:opacity-50"
                >
                  {endingEarly && <Loader2 className="h-3 w-3 animate-spin" />}
                  End session
                </button>
              </div>
              {lastTutorTurn?.turn_type === "explanation" || lastTutorTurn?.turn_type === "answer_reveal" ? (
                <p className="text-[11px] text-neutral-400 mt-1.5">Answer the check question, or tap Skip to move on.</p>
              ) : null}
            </div>
          </div>
        )}
      </main>

      <AnimatePresence>{viewing && <SourceViewer citation={viewing} onClose={() => setViewing(null)} />}</AnimatePresence>
    </>
  );
}
