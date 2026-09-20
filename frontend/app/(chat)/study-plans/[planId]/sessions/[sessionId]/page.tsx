"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { SessionContentResponse, StudyPlanDetailResponse, StudySessionPublic } from "@/lib/types";

export default function SessionContentPage({
  params,
}: {
  params: Promise<{ planId: string; sessionId: string }>;
}) {
  const { planId, sessionId } = use(params);
  const router = useRouter();
  const [session, setSession] = useState<StudySessionPublic | null>(null);
  const [content, setContent] = useState<SessionContentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<StudyPlanDetailResponse>(`/study-plans/${planId}`, { auth: true })
      .then((plan) => {
        const s = plan.sessions.find((x) => x.id === sessionId);
        if (!s) throw new Error("Session not found.");
        if (cancelled) return;
        setSession(s);

        // A checkpoint quiz already has a real, persisted Quiz — send the user to the
        // normal quiz-taking flow instead of on-demand-generating separate content.
        if (s.session_type === "quiz" && s.quiz_id) {
          router.replace(`/quiz/${s.quiz_id}`);
          return;
        }

        return api.get<SessionContentResponse>(`/study-plans/${planId}/sessions/${sessionId}/content`, { auth: true });
      })
      .then((data) => {
        if (data && !cancelled) setContent(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : "Couldn't load this session.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId, sessionId]);

  async function handleComplete() {
    setCompleting(true);
    try {
      await api.post(`/study-plans/${planId}/sessions/${sessionId}/complete`, {}, { auth: true });
      router.push(`/study-plans/${planId}`);
    } finally {
      setCompleting(false);
    }
  }

  function toggleRevealed(id: string) {
    setRevealed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => router.push(`/study-plans/${planId}`)}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to plan
          </button>

          {loading && <p className="text-sm text-neutral-400">Generating session content...</p>}
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

          {!loading && session && content && (
            <>
              <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1">
                {session.session_type}
              </p>
              <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-2">
                {content.topic_title}
              </h1>
              <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-8">{content.topic_description}</p>

              <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 mb-6">
                <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Explanation</h2>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed whitespace-pre-wrap">
                  {content.explanation}
                </p>
              </section>

              {content.practice_questions.length > 0 && (
                <section className="mb-6">
                  <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                    Practice Questions
                  </h2>
                  <div className="space-y-3">
                    {content.practice_questions.map((q) => (
                      <div key={q.id} className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
                        <p className="text-sm text-neutral-800 dark:text-neutral-200 mb-2">{q.question}</p>
                        {q.type === "multiple_choice" && (
                          <div className="space-y-1 mb-2">
                            {q.options.map((o, i) => (
                              <div
                                key={i}
                                className="text-xs text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-700 rounded-lg px-2.5 py-1"
                              >
                                {o}
                              </div>
                            ))}
                          </div>
                        )}
                        <button
                          onClick={() => toggleRevealed(q.id)}
                          className="text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors"
                        >
                          {revealed.has(q.id) ? "Hide answer" : "Show answer"}
                        </button>
                        {revealed.has(q.id) && (
                          <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-2">
                            <span className="font-medium text-neutral-800 dark:text-neutral-200">
                              {q.correct_answer}
                            </span>
                            {q.explanation && ` — ${q.explanation}`}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-neutral-400 mt-2">
                    These practice questions were also saved to your Daily Review deck.
                  </p>
                </section>
              )}

              {session.status === "pending" ? (
                <button
                  onClick={handleComplete}
                  disabled={completing}
                  className="w-full flex items-center justify-center gap-2 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Mark session complete
                </button>
              ) : (
                <p className="text-xs text-emerald-600 dark:text-emerald-400 text-center">
                  This session is already {session.status}.
                </p>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
