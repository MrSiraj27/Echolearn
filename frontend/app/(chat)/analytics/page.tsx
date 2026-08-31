"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, HelpCircle, FileWarning } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import {
  AnalyticsOverview,
  DocumentPerformanceItem,
  KnowledgeGapTheme,
  QuizInsightQuestion,
} from "@/lib/types";

type SortKey = "filename" | "times_referenced" | "times_not_found" | "quiz_avg_score";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-4 py-3.5">
      <p className="text-[11px] font-medium text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1">
        {label}
      </p>
      <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{value}</p>
    </div>
  );
}

function QuestionsChart({ points }: { points: { date: string; count: number }[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-neutral-400 dark:text-neutral-500">No questions asked in the last 30 days.</p>;
  }

  const width = 600;
  const height = 140;
  const padding = 8;
  const maxCount = Math.max(...points.map((p) => p.count), 1);
  const stepX = points.length > 1 ? (width - padding * 2) / (points.length - 1) : 0;

  const coords = points.map((p, i) => {
    const x = padding + i * stepX;
    const y = height - padding - (p.count / maxCount) * (height - padding * 2);
    return { x, y, ...p };
  });

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x} ${c.y}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${height - padding} L ${coords[0].x} ${height - padding} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-36" preserveAspectRatio="none">
      <path d={areaPath} fill="currentColor" className="text-neutral-900/5 dark:text-neutral-100/10" />
      <path d={linePath} fill="none" stroke="currentColor" strokeWidth={2} className="text-neutral-900 dark:text-neutral-100" />
      {coords.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={2.5} fill="currentColor" className="text-neutral-900 dark:text-neutral-100">
          <title>{`${c.date}: ${c.count}`}</title>
        </circle>
      ))}
    </svg>
  );
}

export default function AnalyticsPage() {
  const { workspaces, loadWorkspaces } = useChatStore();
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [gaps, setGaps] = useState<KnowledgeGapTheme[]>([]);
  const [docPerformance, setDocPerformance] = useState<DocumentPerformanceItem[]>([]);
  const [quizInsights, setQuizInsights] = useState<QuizInsightQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("times_referenced");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  useEffect(() => {
    const qs = workspaceId ? `?workspace_id=${workspaceId}` : "";
    setLoading(true);
    setError(null);

    Promise.all([
      api.get<AnalyticsOverview>(`/analytics/overview${qs}`, { auth: true }),
      api.get<KnowledgeGapTheme[]>(`/analytics/knowledge-gaps${qs}`, { auth: true }),
      api.get<DocumentPerformanceItem[]>(`/analytics/document-performance${qs}`, { auth: true }),
      api.get<{ questions: QuizInsightQuestion[] }>("/analytics/quiz-insights", { auth: true }),
    ])
      .then(([ov, kg, dp, qi]) => {
        setOverview(ov);
        setGaps(kg);
        setDocPerformance(dp);
        setQuizInsights(qi.questions);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load analytics."))
      .finally(() => setLoading(false));
  }, [workspaceId]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDesc((v) => !v);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  const sortedDocs = [...docPerformance].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "string" || typeof bv === "string") {
      return sortDesc ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
    }
    return sortDesc ? (bv as number) - (av as number) : (av as number) - (bv as number);
  });

  const columns: { key: SortKey; label: string }[] = [
    { key: "filename", label: "Document" },
    { key: "times_referenced", label: "Referenced" },
    { key: "times_not_found", label: "Not found" },
    { key: "quiz_avg_score", label: "Quiz avg" },
  ];

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 h-screen overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-4xl mx-auto px-6 pt-16 pb-12 lg:pt-10">
          <div className="flex items-center justify-between gap-3 mb-6 flex-wrap">
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
                Analytics
              </h1>
              <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
                Read-only insights from your chats, documents, and quizzes.
              </p>
            </div>
            {workspaces.length > 0 && (
              <select
                value={workspaceId}
                onChange={(e) => setWorkspaceId(e.target.value)}
                className="text-sm bg-transparent border border-neutral-200 dark:border-neutral-700 rounded-lg px-3 py-1.5 text-neutral-700 dark:text-neutral-300 focus:outline-none"
              >
                <option value="">All documents</option>
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}
          {loading && <p className="text-sm text-neutral-400 dark:text-neutral-500">Loading analytics...</p>}

          {!loading && overview && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard label="Questions asked" value={overview.total_questions_asked} />
                <StatCard label="Documents" value={overview.total_documents} />
                <StatCard label="Quizzes taken" value={overview.total_quizzes_taken} />
                <StatCard
                  label="Avg quiz score"
                  value={overview.avg_quiz_score != null ? `${overview.avg_quiz_score}%` : "—"}
                />
              </div>

              <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                    Questions over time (last 30 days)
                  </p>
                  {overview.most_active_document && (
                    <p className="text-xs text-neutral-400 dark:text-neutral-500 truncate max-w-[240px]">
                      Most active: {overview.most_active_document}
                    </p>
                  )}
                </div>
                <QuestionsChart points={overview.questions_over_time} />
              </div>

              <div className="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50/50 dark:bg-amber-950/20 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  <p className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">Knowledge Gaps</p>
                </div>
                {gaps.length === 0 ? (
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    No unanswered questions yet — your documents are covering what people ask.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {gaps.map((gap, i) => (
                      <div
                        key={i}
                        className="flex items-start justify-between gap-3 bg-white dark:bg-neutral-900 rounded-lg border border-amber-100 dark:border-amber-900/50 px-3 py-2.5"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">{gap.theme}</p>
                          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5 truncate">
                            e.g. "{gap.example_questions[0]}"
                          </p>
                        </div>
                        <span className="shrink-0 text-xs font-semibold text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-950/50 rounded-full px-2 py-0.5">
                          {gap.count}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
                <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-3">Document performance</p>
                {docPerformance.length === 0 ? (
                  <p className="text-sm text-neutral-400 dark:text-neutral-500">No documents yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-neutral-100 dark:border-neutral-800">
                          {columns.map((col) => (
                            <th
                              key={col.key}
                              onClick={() => toggleSort(col.key)}
                              className="text-left font-medium text-neutral-400 dark:text-neutral-500 px-2 py-2 cursor-pointer select-none hover:text-neutral-700 dark:hover:text-neutral-200 whitespace-nowrap"
                            >
                              {col.label} {sortKey === col.key ? (sortDesc ? "↓" : "↑") : ""}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sortedDocs.map((doc) => (
                          <tr
                            key={doc.document_id}
                            className="border-b border-neutral-50 dark:border-neutral-800/60 last:border-0"
                          >
                            <td className="px-2 py-2 text-neutral-800 dark:text-neutral-200 max-w-[260px] truncate">
                              {doc.filename}
                            </td>
                            <td className="px-2 py-2 text-neutral-600 dark:text-neutral-400">{doc.times_referenced}</td>
                            <td className="px-2 py-2 text-neutral-600 dark:text-neutral-400">{doc.times_not_found}</td>
                            <td className="px-2 py-2 text-neutral-600 dark:text-neutral-400">
                              {doc.quiz_avg_score != null ? `${doc.quiz_avg_score}%` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {quizInsights.length > 0 && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <HelpCircle className="h-4 w-4 text-neutral-400" />
                    <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                      Most commonly missed quiz questions
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    {quizInsights.map((q) => (
                      <div
                        key={q.question_id}
                        className="flex items-center justify-between gap-3 px-2.5 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
                      >
                        <div className="min-w-0">
                          <p className="text-sm text-neutral-800 dark:text-neutral-200 truncate">{q.question}</p>
                          <p className="text-xs text-neutral-400 dark:text-neutral-500 truncate">{q.quiz_title}</p>
                        </div>
                        <span className="shrink-0 flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400">
                          <FileWarning className="h-3 w-3" />
                          {q.wrong_rate}% wrong
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </div>
      </main>
    </>
  );
}
