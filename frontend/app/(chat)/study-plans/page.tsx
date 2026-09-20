"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Plus, Calendar } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api } from "@/lib/api";
import { StudyPlanResponse } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400",
  completed: "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400",
  abandoned: "bg-neutral-100 dark:bg-neutral-800 text-neutral-400 dark:text-neutral-500",
};

export default function StudyPlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<StudyPlanResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<StudyPlanResponse[]>("/study-plans/", { auth: true })
      .then(setPlans)
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
                Study Plans
              </h1>
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                Exam-aware, day-by-day study schedules built from your documents.
              </p>
            </div>
            <Link
              href="/study-plans/new"
              className="shrink-0 flex items-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3.5 py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
            >
              <Plus className="h-4 w-4" />
              New Plan
            </Link>
          </div>

          {loading && <p className="text-sm text-neutral-400">Loading...</p>}

          {!loading && plans.length === 0 && (
            <div className="rounded-2xl border border-dashed border-neutral-300 dark:border-neutral-700 p-8 text-center">
              <Calendar className="h-6 w-6 text-neutral-400 mx-auto mb-2" />
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                No study plans yet — create one to get an exam-aware study schedule.
              </p>
            </div>
          )}

          <div className="space-y-2">
            {plans.map((plan) => {
              const pct = plan.session_count > 0 ? (plan.completed_count / plan.session_count) * 100 : 0;
              return (
                <Link
                  key={plan.id}
                  href={`/study-plans/${plan.id}`}
                  className="block rounded-xl border border-neutral-200 dark:border-neutral-800 p-4 hover:bg-neutral-50 dark:hover:bg-neutral-900 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">{plan.title}</p>
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${STATUS_STYLE[plan.status]}`}>
                      {plan.status}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-400 mb-2">
                    Exam: {new Date(plan.exam_date + "T00:00:00").toLocaleDateString()}
                  </p>
                  <div className="h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-neutral-900 dark:bg-neutral-100"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-neutral-400 mt-1">
                    {plan.completed_count} / {plan.session_count} sessions
                  </p>
                </Link>
              );
            })}
          </div>
        </div>
      </main>
    </>
  );
}
