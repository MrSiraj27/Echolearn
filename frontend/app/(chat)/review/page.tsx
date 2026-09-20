"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Flame, CheckCircle2, ExternalLink } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { ReviewCardWithState, ReviewStatsResponse, TodayReviewResponse } from "@/lib/types";

type Grade = "forgot" | "hard" | "easy";
const QUALITY_BY_GRADE: Record<Grade, number> = { forgot: 1, hard: 3, easy: 5 };

interface GradedCard {
  card: ReviewCardWithState;
  grade: Grade;
}

export default function ReviewPage() {
  const router = useRouter();
  const { createChat } = useChatStore();
  const [loading, setLoading] = useState(true);
  const [cards, setCards] = useState<ReviewCardWithState[]>([]);
  const [totalDue, setTotalDue] = useState(0);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [graded, setGraded] = useState<GradedCard[]>([]);
  const [stats, setStats] = useState<ReviewStatsResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [startingChatFor, setStartingChatFor] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TodayReviewResponse>("/review/today", { auth: true })
      .then((data) => {
        setCards(data.cards);
        setTotalDue(data.total_due);
      })
      .catch(() => setCards([]))
      .finally(() => setLoading(false));
  }, []);

  const current = cards[index];
  const done = cards.length > 0 && index >= cards.length;

  useEffect(() => {
    if (done) {
      api
        .get<ReviewStatsResponse>("/review/stats", { auth: true })
        .then(setStats)
        .catch(() => setStats(null));
    }
  }, [done]);

  async function handleGrade(grade: Grade) {
    if (!current || submitting) return;
    setSubmitting(true);
    try {
      await api.post(`/review/${current.id}/submit`, { quality: QUALITY_BY_GRADE[grade] }, { auth: true });
      setGraded((prev) => [...prev, { card: current, grade }]);
      setRevealed(false);
      setIndex((i) => i + 1);
    } finally {
      setSubmitting(false);
    }
  }

  async function jumpToSource(card: ReviewCardWithState) {
    setStartingChatFor(card.id);
    try {
      const chatId = await createChat([card.document_id]);
      router.push(`/chat/${chatId}`);
    } finally {
      setStartingChatFor(null);
    }
  }

  const forgotCount = graded.filter((g) => g.grade === "forgot").length;
  const hardCount = graded.filter((g) => g.grade === "hard").length;
  const easyCount = graded.filter((g) => g.grade === "easy").length;

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-xl mx-auto px-6 py-10">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-2">
            Daily Review
          </h1>

          {loading && <p className="text-sm text-neutral-400">Loading...</p>}

          {!loading && cards.length === 0 && (
            <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-8 text-center">
              <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-3" />
              <p className="text-sm text-neutral-600 dark:text-neutral-300">
                You&apos;re all caught up — no cards due today.
              </p>
            </div>
          )}

          {!loading && cards.length > 0 && !done && current && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <p className="text-xs text-neutral-400">
                  Card {index + 1} of {cards.length}
                  {totalDue > cards.length && ` (${totalDue - cards.length} more due beyond today's cap)`}
                </p>
              </div>
              <div className="h-1 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden mb-6">
                <div
                  className="h-full rounded-full bg-neutral-900 dark:bg-neutral-100 transition-all"
                  style={{ width: `${(index / cards.length) * 100}%` }}
                />
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={current.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 min-h-[220px] flex flex-col"
                >
                  <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-3">
                    Question
                  </p>
                  <p className="text-base text-neutral-900 dark:text-neutral-100 leading-relaxed flex-1">
                    {current.question}
                  </p>

                  {current.question_type === "multiple_choice" && current.options && (
                    <div className="mt-3 space-y-1.5">
                      {current.options.map((o, i) => (
                        <div
                          key={i}
                          className="text-sm text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-700 rounded-lg px-3 py-1.5"
                        >
                          {o}
                        </div>
                      ))}
                    </div>
                  )}

                  <AnimatePresence>
                    {revealed && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800"
                      >
                        <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">
                          Answer
                        </p>
                        <p className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed">
                          {current.answer}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              </AnimatePresence>

              <div className="mt-6">
                {!revealed ? (
                  <button
                    onClick={() => setRevealed(true)}
                    className="w-full text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
                  >
                    Show Answer
                  </button>
                ) : (
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => handleGrade("forgot")}
                      disabled={submitting}
                      className="text-sm font-medium bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-900 rounded-lg py-2.5 hover:bg-red-100 dark:hover:bg-red-950/50 transition-colors disabled:opacity-50"
                    >
                      Forgot
                    </button>
                    <button
                      onClick={() => handleGrade("hard")}
                      disabled={submitting}
                      className="text-sm font-medium bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900 rounded-lg py-2.5 hover:bg-amber-100 dark:hover:bg-amber-950/50 transition-colors disabled:opacity-50"
                    >
                      Hard
                    </button>
                    <button
                      onClick={() => handleGrade("easy")}
                      disabled={submitting}
                      className="text-sm font-medium bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900 rounded-lg py-2.5 hover:bg-emerald-100 dark:hover:bg-emerald-950/50 transition-colors disabled:opacity-50"
                    >
                      Easy
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {done && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6"
            >
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  Session complete — {graded.length} card{graded.length === 1 ? "" : "s"} reviewed
                </p>
              </div>

              {stats && (
                <p className="flex items-center gap-1.5 text-sm text-amber-600 dark:text-amber-400 mb-4">
                  <Flame className="h-4 w-4" />
                  {stats.current_streak_days} day{stats.current_streak_days === 1 ? "" : "s"} streak
                </p>
              )}

              <div className="grid grid-cols-3 gap-2 mb-5 text-center text-xs">
                <div className="rounded-lg bg-red-50 dark:bg-red-950/30 py-2">
                  <p className="font-semibold text-red-700 dark:text-red-400">{forgotCount}</p>
                  <p className="text-red-500 dark:text-red-500">Forgot</p>
                </div>
                <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 py-2">
                  <p className="font-semibold text-amber-700 dark:text-amber-400">{hardCount}</p>
                  <p className="text-amber-500">Hard</p>
                </div>
                <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 py-2">
                  <p className="font-semibold text-emerald-700 dark:text-emerald-400">{easyCount}</p>
                  <p className="text-emerald-500">Easy</p>
                </div>
              </div>

              {forgotCount > 0 && (
                <div className="mb-5">
                  <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">
                    Review the source for what you forgot
                  </p>
                  <div className="space-y-1.5">
                    {graded
                      .filter((g) => g.grade === "forgot")
                      .map((g) => (
                        <button
                          key={g.card.id}
                          onClick={() => jumpToSource(g.card)}
                          disabled={startingChatFor === g.card.id}
                          className="w-full flex items-center justify-between gap-2 text-left text-xs text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-700 rounded-lg px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50"
                        >
                          <span className="truncate">{g.card.question}</span>
                          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                        </button>
                      ))}
                  </div>
                </div>
              )}

              <button
                onClick={() => router.push("/chat")}
                className="w-full text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
              >
                Done
              </button>
            </motion.div>
          )}
        </div>
      </main>
    </>
  );
}
