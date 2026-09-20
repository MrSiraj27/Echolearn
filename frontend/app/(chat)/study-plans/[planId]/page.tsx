"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, XCircle, Loader2, AlertTriangle } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { PlanStatusResponse, StudyPlanDetailResponse, StudySessionPublic, StudySessionType } from "@/lib/types";

const SESSION_TYPE_STYLE: Record<StudySessionType, string> = {
  learn: "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-900",
  review:
    "bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-900",
  quiz: "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-900",
  checkpoint:
    "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900",
};

const STATUS_MESSAGE: Record<string, { text: string; tone: string }> = {
  on_track: { text: "You're on track.", tone: "text-emerald-600 dark:text-emerald-400" },
  slightly_behind: { text: "You're a little behind schedule — nothing to worry about yet.", tone: "text-amber-600 dark:text-amber-400" },
  significantly_behind: {
    text: "You're significantly behind schedule. Consider compressing the remaining plan.",
    tone: "text-red-600 dark:text-red-400",
  },
};

function groupByDate(sessions: StudySessionPublic[]) {
  const groups = new Map<string, StudySessionPublic[]>();
  for (const s of sessions) {
    if (!groups.has(s.scheduled_date)) groups.set(s.scheduled_date, []);
    groups.get(s.scheduled_date)!.push(s);
  }
  return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
}

export default function StudyPlanDetailPage({ params }: { params: Promise<{ planId: string }> }) {
  const { planId } = use(params);
  const router = useRouter();
  const [plan, setPlan] = useState<StudyPlanDetailResponse | null>(null);
  const [planStatus, setPlanStatus] = useState<PlanStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busySessionId, setBusySessionId] = useState<string | null>(null);
  const [compressing, setCompressing] = useState(false);

  function load() {
    Promise.all([
      api.get<StudyPlanDetailResponse>(`/study-plans/${planId}`, { auth: true }),
      api.get<PlanStatusResponse>(`/study-plans/${planId}/status`, { auth: true }),
    ])
      .then(([p, s]) => {
        setPlan(p);
        setPlanStatus(s);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't load this plan."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId]);

  async function handleSessionAction(sessionId: string, action: "complete" | "skip") {
    setBusySessionId(sessionId);
    try {
      await api.post(`/study-plans/${planId}/sessions/${sessionId}/${action}`, {}, { auth: true });
      load();
    } finally {
      setBusySessionId(null);
    }
  }

  async function handleCompress() {
    setCompressing(true);
    try {
      await api.post(`/study-plans/${planId}/compress`, {}, { auth: true });
      load();
    } catch {
      setError("Couldn't compress the remaining schedule. Please try again.");
    } finally {
      setCompressing(false);
    }
  }

  if (loading) {
    return (
      <>
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950 px-6 py-10">
          <p className="text-sm text-neutral-400">Loading...</p>
        </main>
      </>
    );
  }

  if (error || !plan) {
    return (
      <>
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950 px-6 py-10">
          <p className="text-sm text-red-600 dark:text-red-400">{error || "Plan not found."}</p>
        </main>
      </>
    );
  }

  const grouped = groupByDate(plan.sessions);
  const pct = plan.session_count > 0 ? (plan.completed_count / plan.session_count) * 100 : 0;
  const statusInfo = planStatus ? STATUS_MESSAGE[planStatus.status] : null;

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => router.push("/study-plans")}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            All plans
          </button>

          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
            {plan.title}
          </h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
            Exam: {new Date(plan.exam_date + "T00:00:00").toLocaleDateString()} · {plan.daily_study_minutes} min/day
          </p>

          <div className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden mb-2">
            <div className="h-full rounded-full bg-neutral-900 dark:bg-neutral-100" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-neutral-400 mb-4">
            {plan.completed_count} of {plan.session_count} sessions completed
          </p>

          {statusInfo && (
            <div className={`flex items-center gap-2 text-sm mb-2 ${statusInfo.tone}`}>
              {planStatus?.status === "significantly_behind" && <AlertTriangle className="h-4 w-4" />}
              {statusInfo.text}
            </div>
          )}
          {planStatus && planStatus.status !== "on_track" && (
            <button
              onClick={handleCompress}
              disabled={compressing}
              className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50 mb-8"
            >
              {compressing && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Compress remaining sessions into what's left
            </button>
          )}

          <div className="space-y-3">
            {grouped.map(([dateStr, sessions]) => (
              <div key={dateStr} className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
                <p className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 mb-2">
                  {new Date(dateStr + "T00:00:00").toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </p>
                <div className="space-y-1.5">
                  {sessions.map((s) => (
                    <div
                      key={s.id}
                      className={`flex items-center justify-between gap-2 text-xs rounded-lg border px-2.5 py-1.5 ${SESSION_TYPE_STYLE[s.session_type]}`}
                    >
                      <button
                        onClick={() => router.push(`/study-plans/${planId}/sessions/${s.id}`)}
                        className="text-left min-w-0 flex-1"
                      >
                        <span className="font-medium capitalize">{s.session_type}</span>
                        {" — "}
                        <span className="truncate">{s.topic_title}</span>
                      </button>
                      {s.status === "pending" ? (
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            onClick={() => handleSessionAction(s.id, "complete")}
                            disabled={busySessionId === s.id}
                            aria-label="Mark complete"
                            className="p-0.5 hover:opacity-70"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleSessionAction(s.id, "skip")}
                            disabled={busySessionId === s.id}
                            aria-label="Skip"
                            className="p-0.5 hover:opacity-70"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <span className="shrink-0 capitalize">{s.status}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
