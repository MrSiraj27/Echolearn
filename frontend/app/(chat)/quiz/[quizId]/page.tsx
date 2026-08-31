"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Check, X, ExternalLink, Loader2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { QuizDetail, SubmitQuizResponse } from "@/lib/types";
import { useChatStore } from "@/lib/chat-store";
import SourceViewer from "@/components/SourceViewer";

export default function QuizPage({ params }: { params: Promise<{ quizId: string }> }) {
  const { quizId } = use(params);
  const router = useRouter();
  const { documents, loadDocuments } = useChatStore();

  const [quiz, setQuiz] = useState<QuizDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitQuizResponse | null>(null);
  const [viewingSourceFor, setViewingSourceFor] = useState<string | null>(null);

  useEffect(() => {
    loadDocuments();
    api
      .get<QuizDetail>(`/quizzes/${quizId}`, { auth: true })
      .then(setQuiz)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load this quiz."))
      .finally(() => setLoading(false));
  }, [quizId, loadDocuments]);

  async function handleSubmit() {
    if (!quiz) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<SubmitQuizResponse>(`/quizzes/${quizId}/submit`, { answers }, { auth: true });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't submit your answers. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const answeredCount = quiz ? quiz.questions.filter((q) => answers[q.id]?.trim()).length : 0;

  return (
    <>
      <Sidebar />
      <main className="flex-1 flex flex-col h-screen overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto w-full px-6 pt-16 pb-8 lg:pt-8">
          {loading && <p className="text-sm text-neutral-400 dark:text-neutral-500">Loading quiz...</p>}
          {error && !quiz && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

          {quiz && !result && (
            <>
              <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-1">{quiz.title}</h1>
              <p className="text-sm text-neutral-400 dark:text-neutral-500 mb-6">
                {quiz.questions.length} questions · {answeredCount} answered
              </p>

              <div className="space-y-6">
                {quiz.questions.map((q, i) => (
                  <motion.div
                    key={q.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="border border-neutral-200 dark:border-neutral-800 rounded-xl p-4"
                  >
                    <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-3">
                      {i + 1}. {q.question}
                    </p>
                    {q.type === "multiple_choice" ? (
                      <div className="space-y-1.5">
                        {q.options.map((opt) => (
                          <label
                            key={opt}
                            className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 cursor-pointer"
                          >
                            <input
                              type="radio"
                              name={q.id}
                              checked={answers[q.id] === opt}
                              onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                              className="accent-neutral-900 dark:accent-neutral-100"
                            />
                            {opt}
                          </label>
                        ))}
                      </div>
                    ) : (
                      <input
                        type="text"
                        value={answers[q.id] || ""}
                        onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                        placeholder="Your answer..."
                        className="w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 dark:placeholder:text-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                      />
                    )}
                  </motion.div>
                ))}
              </div>

              {error && <p className="text-sm text-red-600 dark:text-red-400 mt-4">{error}</p>}

              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="mt-6 w-full bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-sm font-medium rounded-xl py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {submitting ? "Grading..." : "Submit Quiz"}
              </button>
            </>
          )}

          {result && quiz && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div className="text-center mb-8">
                <p className="text-4xl font-bold text-neutral-900 dark:text-neutral-100">{result.score}%</p>
                <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
                  {result.correct_count} of {result.total} correct
                </p>
              </div>

              <div className="space-y-4">
                {result.results.map((r, i) => (
                  <div
                    key={r.id}
                    className={`border rounded-xl p-4 ${
                      r.is_correct
                        ? "border-emerald-200 dark:border-emerald-900 bg-emerald-50/40 dark:bg-emerald-950/20"
                        : "border-red-200 dark:border-red-900 bg-red-50/40 dark:bg-red-950/20"
                    }`}
                  >
                    <div className="flex items-start gap-2 mb-2">
                      <span
                        className={`shrink-0 mt-0.5 ${
                          r.is_correct ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
                        }`}
                      >
                        {r.is_correct ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
                      </span>
                      <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                        {i + 1}. {r.question}
                      </p>
                    </div>
                    <p className="text-xs text-neutral-600 dark:text-neutral-400 ml-6">
                      Your answer: <span className="italic">{r.submitted_answer || "(no answer)"}</span>
                    </p>
                    {!r.is_correct && (
                      <p className="text-xs text-neutral-600 dark:text-neutral-400 ml-6 mt-0.5">
                        Correct answer: <span className="font-medium">{r.correct_answer}</span>
                      </p>
                    )}
                    {r.explanation && (
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 ml-6 mt-1.5">{r.explanation}</p>
                    )}
                    {r.source_page && (
                      <button
                        onClick={() => setViewingSourceFor(r.id)}
                        className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400 underline underline-offset-2 ml-6 mt-1.5 hover:text-neutral-700 dark:hover:text-neutral-200"
                      >
                        <ExternalLink className="h-3 w-3" />
                        View source (p. {r.source_page})
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex gap-2 mt-6">
                <button
                  onClick={() => {
                    setResult(null);
                    setAnswers({});
                  }}
                  className="flex-1 border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 text-sm font-medium rounded-xl py-2.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
                >
                  Retake Quiz
                </button>
                <button
                  onClick={() => router.push("/chat")}
                  className="flex-1 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-sm font-medium rounded-xl py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
                >
                  Back to Chat
                </button>
              </div>

              <AnimatePresence>
                {viewingSourceFor &&
                  (() => {
                    const r = result.results.find((res) => res.id === viewingSourceFor);
                    if (!r) return null;
                    const doc = documents.find((d) => d.filename === r.source_filename);
                    if (!doc) return null;
                    return (
                      <SourceViewer
                        citation={{
                          filename: r.source_filename,
                          page_number: r.source_page,
                          document_id: doc.id,
                          chunk_text: null,
                        }}
                        onClose={() => setViewingSourceFor(null)}
                      />
                    );
                  })()}
              </AnimatePresence>
            </motion.div>
          )}
        </div>
      </main>
    </>
  );
}
