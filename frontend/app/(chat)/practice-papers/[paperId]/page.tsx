"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ChevronDown, ChevronRight, Download, Info, Loader2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import {
  downloadPaperPdf,
  patternBadgeText,
  PRACTICE_DISCLAIMER,
  QUESTION_TYPE_LABELS,
} from "@/lib/practice";
import {
  PaperAttemptResult,
  PaperQuestion,
  PaperQuestionResult,
  PracticePaperDetail,
  PracticePaperStatusResponse,
} from "@/lib/types";

const LETTERS = ["A", "B", "C", "D", "E", "F"];
const fieldCls =
  "w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100";

function marksLabel(m: number) {
  return `${m} mark${m === 1 ? "" : "s"}`;
}

function DisclaimerBanner() {
  return (
    <div
      role="note"
      className="flex gap-3 rounded-xl border-2 border-neutral-900 dark:border-neutral-100 bg-neutral-50 dark:bg-neutral-900 p-4"
    >
      <Info className="h-5 w-5 shrink-0 text-neutral-900 dark:text-neutral-100 mt-0.5" />
      <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">{PRACTICE_DISCLAIMER}</p>
    </div>
  );
}

function WhyThisQuestion({ q }: { q: PaperQuestion }) {
  const [open, setOpen] = useState(false);
  const refs = q.source_references.length ? q.source_references : q.source_reference ? [q.source_reference] : [];
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Why this question?
      </button>
      {open && (
        <div className="mt-1.5 ml-4 text-xs text-neutral-600 dark:text-neutral-400 space-y-1">
          {q.topic_reason && <p>{q.topic_reason}</p>}
          {refs.length > 0 && (
            <p>
              <span className="font-medium">Written from:</span> {refs.map((r) => r.label).join("; ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function QuestionBody({
  q,
  number,
  answer,
  onAnswer,
  attempting,
}: {
  q: PaperQuestion;
  number: number;
  answer: string;
  onAnswer: (v: string) => void;
  attempting: boolean;
}) {
  const long = q.question_type === "long_answer" || q.question_type === "diagram_based";
  return (
    <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 whitespace-pre-wrap">
          {number}. {q.question_text}
        </p>
        <span className="shrink-0 text-xs text-neutral-400">[{marksLabel(q.marks)}]</span>
      </div>

      {q.question_type === "multiple_choice" && (
        <div className="space-y-1.5 mt-3">
          {q.options.map((opt, i) =>
            attempting ? (
              <label
                key={i}
                className="flex items-start gap-2 text-sm text-neutral-700 dark:text-neutral-300 cursor-pointer"
              >
                <input
                  type="radio"
                  name={q.id}
                  checked={answer === LETTERS[i]}
                  onChange={() => onAnswer(LETTERS[i])}
                  className="mt-1 accent-neutral-900 dark:accent-neutral-100"
                />
                <span>
                  <span className="font-medium">{LETTERS[i]}.</span> {opt}
                </span>
              </label>
            ) : (
              <p key={i} className="text-sm text-neutral-700 dark:text-neutral-300">
                <span className="font-medium">{LETTERS[i]}.</span> {opt}
              </p>
            )
          )}
        </div>
      )}

      {attempting && q.question_type !== "multiple_choice" && (
        <div className="mt-3">
          {long ? (
            <textarea
              value={answer}
              onChange={(e) => onAnswer(e.target.value)}
              rows={q.question_type === "long_answer" ? 6 : 4}
              placeholder={q.question_type === "diagram_based" ? "Describe your diagram..." : "Write your answer..."}
              className={fieldCls}
            />
          ) : (
            <input
              value={answer}
              onChange={(e) => onAnswer(e.target.value)}
              placeholder={q.question_type === "numerical" ? "Your answer (with working if you like)..." : "Your answer..."}
              className={fieldCls}
            />
          )}
        </div>
      )}

      {!attempting && <WhyThisQuestion q={q} />}
    </div>
  );
}

const RESULT_STYLE: Record<string, string> = {
  correct: "border-emerald-200 dark:border-emerald-900 bg-emerald-50/40 dark:bg-emerald-950/20",
  incorrect: "border-red-200 dark:border-red-900 bg-red-50/40 dark:bg-red-950/20",
  unanswered: "border-neutral-200 dark:border-neutral-800",
  needs_self_grade: "border-amber-200 dark:border-amber-900 bg-amber-50/40 dark:bg-amber-950/20",
  self_graded: "border-neutral-300 dark:border-neutral-700",
};
const RESULT_LABEL: Record<string, string> = {
  correct: "Correct (auto-marked)",
  incorrect: "Incorrect (auto-marked)",
  unanswered: "Not answered",
  needs_self_grade: "Needs your marking",
  self_graded: "Marked by you",
};

function ResultCard({
  r,
  number,
  selfMark,
  onSelfMark,
}: {
  r: PaperQuestionResult;
  number: number;
  selfMark: string;
  onSelfMark: (v: string) => void;
}) {
  const canSelfGrade = r.status === "needs_self_grade" || r.status === "self_graded";
  return (
    <div className={`rounded-xl border p-4 ${RESULT_STYLE[r.status]}`}>
      <div className="flex items-start justify-between gap-3 mb-1">
        <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 whitespace-pre-wrap">
          {number}. {r.question_text}
        </p>
        <span className="shrink-0 text-xs text-neutral-400">
          {r.marks_awarded != null ? `${r.marks_awarded} / ${r.marks}` : `? / ${r.marks}`}
        </span>
      </div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-neutral-500 mb-2">{RESULT_LABEL[r.status]}</p>
      <p className="text-xs text-neutral-600 dark:text-neutral-400">
        Your answer:{" "}
        <span className="italic whitespace-pre-wrap">
          {r.submitted_answer
            ? r.question_type === "multiple_choice" && /^[A-D]$/.test(r.submitted_answer)
              ? `${r.submitted_answer}. ${r.options["ABCD".indexOf(r.submitted_answer)] ?? ""}`
              : r.submitted_answer
            : "(no answer)"}
        </span>
      </p>
      {r.question_type === "multiple_choice" && r.correct_option && (
        <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5">
          Correct answer:{" "}
          <span className="font-medium">
            {r.correct_option}. {r.correct_answer}
          </span>
        </p>
      )}
      {r.question_type !== "multiple_choice" && r.correct_answer && (
        <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5">
          Expected answer: <span className="font-medium">{r.correct_answer}</span>
        </p>
      )}
      {r.model_answer && (
        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1.5 whitespace-pre-wrap">
          <span className="font-medium">Model answer:</span> {r.model_answer}
        </p>
      )}
      {r.source_reference && (
        <p className="text-xs text-neutral-400 mt-1.5">Source: {r.source_reference.label}</p>
      )}
      {r.note && <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1.5">{r.note}</p>}
      {canSelfGrade && (
        <label className="flex items-center gap-2 mt-3 text-xs text-neutral-600 dark:text-neutral-300">
          Marks you award yourself (0 to {r.marks}):
          <input
            type="number"
            min={0}
            max={r.marks}
            step={0.5}
            value={selfMark}
            onChange={(e) => onSelfMark(e.target.value)}
            className="w-20 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1 text-sm"
          />
        </label>
      )}
    </div>
  );
}

export default function PracticePaperPage({ params }: { params: Promise<{ paperId: string }> }) {
  const { paperId } = use(params);
  const router = useRouter();

  const [statusInfo, setStatusInfo] = useState<PracticePaperStatusResponse | null>(null);
  const [paper, setPaper] = useState<PracticePaperDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"question" | "answer_key" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const [mode, setMode] = useState<"view" | "attempt" | "results">("view");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<PaperAttemptResult | null>(null);
  const [selfMarks, setSelfMarks] = useState<Record<string, string>>({});
  const [savingMarks, setSavingMarks] = useState(false);

  const load = useCallback(async () => {
    try {
      const st = await api.get<PracticePaperStatusResponse>(`/practice-papers/${paperId}/status`, { auth: true });
      setStatusInfo(st);
      if (st.status === "ready") {
        setPaper(await api.get<PracticePaperDetail>(`/practice-papers/${paperId}`, { auth: true }));
      }
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? "Practice paper not found." : "Couldn't load this paper.");
    }
  }, [paperId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while a paper opened from the list/sidebar is still generating.
  useEffect(() => {
    if (statusInfo?.status !== "generating") return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [statusInfo?.status, load]);

  async function handleDownload(variant: "question" | "answer_key") {
    if (!paper) return;
    setDownloading(variant);
    setDownloadError(null);
    try {
      await downloadPaperPdf(paper.id, paper.title, variant);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(null);
    }
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<PaperAttemptResult>(`/practice-papers/${paperId}/submit`, { answers }, { auth: true });
      setResult(res);
      setSelfMarks({});
      setMode("results");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't submit your answers. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSaveSelfMarks() {
    if (!result) return;
    const payload: Record<string, number> = {};
    for (const [id, v] of Object.entries(selfMarks)) {
      const n = parseFloat(v);
      if (!isNaN(n)) payload[id] = n;
    }
    if (Object.keys(payload).length === 0) return;
    setSavingMarks(true);
    setError(null);
    try {
      const res = await api.post<PaperAttemptResult>(
        `/practice-papers/${paperId}/attempts/${result.attempt_id}/self-grade`,
        { self_marks: payload },
        { auth: true }
      );
      setResult(res);
      setSelfMarks({});
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't save your marks.");
    } finally {
      setSavingMarks(false);
    }
  }

  let counter = 0;
  const answeredCount = Object.values(answers).filter((a) => a.trim()).length;

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => (mode !== "view" ? setMode("view") : router.push("/practice-papers"))}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            {mode !== "view" ? "Back to paper" : "All practice papers"}
          </button>

          {error && !paper && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          {!error && !statusInfo && <p className="text-sm text-neutral-400">Loading...</p>}

          {statusInfo?.status === "generating" && (
            <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-8 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-neutral-500 mx-auto mb-3" />
              <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">
                This practice paper is still being written and checked...
              </p>
              <p className="text-xs text-neutral-400 mt-1">This page updates automatically when it&apos;s ready.</p>
            </div>
          )}

          {statusInfo?.status === "failed" && (
            <div className="rounded-2xl border border-red-200 dark:border-red-900 p-6">
              <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">This paper couldn&apos;t be generated</p>
              <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
                {statusInfo.error_message || "Something went wrong."}
              </p>
              <button
                onClick={() => router.push("/practice-papers/new")}
                className="text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-4 py-2"
              >
                Try again
              </button>
            </div>
          )}

          {paper && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
                  {paper.title}
                </h1>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  AI-Generated Practice Exam · {paper.total_questions} questions · {paper.total_marks} marks ·{" "}
                  {paper.time_allowed_minutes} min{paper.time_estimated ? " (estimated)" : ""}
                </p>
                <span className="inline-block mt-2 text-[11px] font-medium rounded-full px-2.5 py-0.5 border border-neutral-300 dark:border-neutral-600 text-neutral-600 dark:text-neutral-300">
                  {patternBadgeText(paper.pattern_source, paper.pattern_note)}
                </span>
              </div>

              <DisclaimerBanner />

              <div className="space-y-2">
                <button
                  onClick={() => handleDownload("question")}
                  disabled={downloading !== null}
                  className="w-full flex items-center justify-center gap-2 text-base font-semibold bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-xl py-4 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-60"
                >
                  {downloading === "question" ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Download className="h-5 w-5" />
                  )}
                  Download Question Paper (PDF)
                </button>
                <div className="flex items-center justify-between gap-3">
                  <button
                    onClick={() => handleDownload("answer_key")}
                    disabled={downloading !== null}
                    className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-60"
                  >
                    {downloading === "answer_key" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Download className="h-3.5 w-3.5" />
                    )}
                    Download Answer Key (PDF)
                  </button>
                  {mode === "view" && (
                    <button
                      onClick={() => {
                        setAnswers({});
                        setMode("attempt");
                      }}
                      className="text-xs text-neutral-500 dark:text-neutral-400 underline underline-offset-2 hover:text-neutral-800 dark:hover:text-neutral-200"
                    >
                      Or attempt it in the app
                    </button>
                  )}
                </div>
                {downloadError && <p className="text-xs text-red-600 dark:text-red-400">{downloadError}</p>}
              </div>

              {paper.topic_coverage.length > 0 && mode === "view" && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
                  <p className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-1.5">Topic focus</p>
                  <ul className="text-xs text-neutral-500 dark:text-neutral-400 space-y-0.5">
                    {paper.topic_coverage.map((t) => (
                      <li key={`${t.origin}-${t.topic}`}>
                        <span className="font-medium text-neutral-700 dark:text-neutral-300">{t.topic}</span>{" "}
                        ({t.origin === "user_important" ? "your request" : "from your past papers"}):{" "}
                        {!t.found_in_materials
                          ? "not found in your material, so no questions could be written on it"
                          : t.questions_covering > 0
                            ? `${t.questions_covering} question${t.questions_covering === 1 ? "" : "s"}`
                            : "found in your material but no question ended up covering it"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {mode === "attempt" && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 p-3 text-xs text-neutral-600 dark:text-neutral-400">
                  <p className="font-medium text-neutral-800 dark:text-neutral-200 mb-1">
                    Attempting in the app · {answeredCount} of {paper.total_questions} answered
                  </p>
                  Multiple-choice answers are marked automatically. Short and numerical answers are marked
                  automatically only when they match exactly. Everything else, including all long answers, can&apos;t be
                  reliably auto-marked, so after submitting you compare with the model answer and mark yourself.
                </div>
              )}

              {mode !== "results" &&
                paper.sections.map((section) => (
                  <section key={section.name}>
                    <div className="flex items-baseline justify-between border-b border-neutral-300 dark:border-neutral-700 pb-1.5 mb-1">
                      <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                        {section.name} · {QUESTION_TYPE_LABELS[section.question_type]}
                      </h2>
                      <span className="text-xs text-neutral-400">
                        {section.count} × {section.marks_each} = {section.count * section.marks_each} marks
                      </span>
                    </div>
                    {section.instructions && (
                      <p className="text-xs italic text-neutral-500 dark:text-neutral-400 mb-3">{section.instructions}</p>
                    )}
                    <div className="space-y-3">
                      {section.questions.map((q) => {
                        counter += 1;
                        return (
                          <QuestionBody
                            key={q.id}
                            q={q}
                            number={counter}
                            answer={answers[q.id] || ""}
                            onAnswer={(v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))}
                            attempting={mode === "attempt"}
                          />
                        );
                      })}
                    </div>
                  </section>
                ))}

              {mode === "attempt" && (
                <>
                  {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
                  <button
                    onClick={handleSubmit}
                    disabled={submitting}
                    className="w-full flex items-center justify-center gap-2 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-xl py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
                  >
                    {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                    Submit for marking
                  </button>
                </>
              )}

              {mode === "results" && result && (
                <div className="space-y-4">
                  <div className="text-center py-2">
                    <p className="text-4xl font-bold text-neutral-900 dark:text-neutral-100">
                      {result.marks_obtained} / {result.total_marks}
                    </p>
                    <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
                      {result.score_percent}% so far
                    </p>
                    {result.pending_self_grade_count > 0 && (
                      <p className="text-xs text-amber-700 dark:text-amber-400 mt-2">
                        {result.pending_self_grade_count} question{result.pending_self_grade_count === 1 ? "" : "s"}{" "}
                        can&apos;t be auto-marked and aren&apos;t counted yet. Read the model answer, enter your own
                        marks below, then save - the total updates.
                      </p>
                    )}
                  </div>
                  {result.results.map((r, i) => (
                    <ResultCard
                      key={r.id}
                      r={r}
                      number={i + 1}
                      selfMark={selfMarks[r.id] ?? (r.status === "self_graded" && r.marks_awarded != null ? String(r.marks_awarded) : "")}
                      onSelfMark={(v) => setSelfMarks((prev) => ({ ...prev, [r.id]: v }))}
                    />
                  ))}
                  {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveSelfMarks}
                      disabled={savingMarks || Object.keys(selfMarks).length === 0}
                      className="flex-1 flex items-center justify-center gap-2 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-xl py-2.5 disabled:opacity-40"
                    >
                      {savingMarks && <Loader2 className="h-4 w-4 animate-spin" />}
                      Save my marks
                    </button>
                    <button
                      onClick={() => {
                        setAnswers({});
                        setResult(null);
                        setMode("attempt");
                      }}
                      className="flex-1 text-sm font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-xl py-2.5 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                    >
                      Retake
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
