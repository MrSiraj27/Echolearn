"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CircleCheckBig, Layers3, Loader2, Plus } from "lucide-react";
import GenerateQuizModal from "@/components/GenerateQuizModal";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { isReady } from "@/components/documents/docUi";
import type { QuizListItem } from "@/lib/types";

interface ReviewToday {
  total_due: number;
}
interface ReviewStats {
  current_streak_days: number;
  total_cards: number;
}

/** Quizzes and flashcard review in one place. */
export default function QuizzesPage() {
  const documents = useChatStore((s) => s.documents);
  const [quizzes, setQuizzes] = useState<QuizListItem[] | null>(null);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [due, setDue] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<QuizListItem[]>("/quizzes/", { auth: true })
      .then(setQuizzes)
      .catch(() => {
        setQuizzes([]);
        setError("Couldn't load your quizzes.");
      });
    api.get<ReviewStats>("/review/stats", { auth: true }).then(setStats).catch(() => setStats(null));
    api.get<ReviewToday>("/review/today", { auth: true }).then((r) => setDue(r.total_due)).catch(() => setDue(null));
  }, []);

  const readyDocs = documents.filter(isReady);

  return (
    <main className="min-w-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight"><CircleCheckBig className="h-7 w-7" /> Quizzes</h1>
            <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">Test yourself on your documents. Questions you miss become flashcards for daily review.</p>
          </div>
          <button
            onClick={() => setCreating(true)}
            disabled={readyDocs.length === 0}
            className="flex items-center gap-2 rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
          >
            <Plus className="h-4 w-4" /> New quiz
          </button>
        </div>

        <Link href="/review" className="flex items-center gap-4 rounded-2xl border border-neutral-200 bg-white p-5 transition-colors hover:border-neutral-400 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-600">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-800"><Layers3 className="h-5 w-5" /></span>
          <span className="min-w-0 flex-1">
            <span className="block font-semibold">Daily review</span>
            <span className="block text-sm text-neutral-500">
              {due === null
                ? "Flashcards from your quizzes, tutor sessions and saved answers"
                : due
                  ? `${due} card${due > 1 ? "s" : ""} due today`
                  : stats?.total_cards
                    ? "No cards due today"
                    : "No flashcards yet"}
              {stats?.current_streak_days ? ` · ${stats.current_streak_days}-day streak` : ""}
            </span>
          </span>
          <span className="text-sm font-medium">{due ? "Start →" : "Open →"}</span>
        </Link>

        <section className="overflow-hidden rounded-2xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900" aria-label="Your quizzes">
          <h2 className="border-b border-neutral-100 px-5 py-3.5 text-[15px] font-semibold dark:border-neutral-800">Your quizzes</h2>
          {quizzes === null ? (
            <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-neutral-400" /></div>
          ) : quizzes.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-neutral-500">{error ?? "No quizzes yet. Create one from any processed document."}</p>
          ) : (
            <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {quizzes.map((q) => (
                <li key={q.id}>
                  <Link href={`/quiz/${q.id}`} className="flex items-center gap-4 px-5 py-3.5 hover:bg-neutral-50 dark:hover:bg-neutral-800/50">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{q.title}</span>
                      <span className="text-[13px] text-neutral-500">
                        {q.question_count} questions · {new Date(q.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                        {q.attempt_count ? ` · ${q.attempt_count} attempt${q.attempt_count > 1 ? "s" : ""}` : " · Not taken yet"}
                      </span>
                    </span>
                    {q.best_score !== null && (
                      <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-[12px] font-medium tabular-nums dark:bg-neutral-800">Best {Math.round(q.best_score)}%</span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {creating && <GenerateQuizModal documents={documents} preselectedDocumentIds={[]} onClose={() => setCreating(false)} />}
    </main>
  );
}
