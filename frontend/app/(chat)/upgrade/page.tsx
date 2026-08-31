"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api } from "@/lib/api";

interface PlanLimits {
  max_documents: number | null;
  max_file_size_mb: number | null;
  max_audio_video_minutes: number | null;
  messages_per_window: number | null;
  message_window_hours: number;
  max_workspaces: number | null;
  quiz_generations_per_month: number | null;
  tts_uses_per_day: number | null;
  diagrams_infographics_per_month: number | null;
  max_storage_mb: number | null;
  priority_processing: boolean;
}

interface Plan {
  id: string;
  name: string;
  slug: string;
  is_default: boolean;
  limits: PlanLimits;
  price_monthly: number | null;
}

function formatLimit(value: number | null, unit: string): string {
  return value === null ? `Unlimited ${unit}` : `${value} ${unit}`;
}

export default function UpgradePage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [contacted, setContacted] = useState(false);

  useEffect(() => {
    api
      .get<Plan[]>("/users/plans", { auth: true })
      .then(setPlans)
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-4xl mx-auto px-6 py-10">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-2">
            Upgrade your plan
          </h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-8">
            Choose the plan that fits how much you use EchoLearn.
          </p>

          {loading && <p className="text-sm text-neutral-400">Loading plans...</p>}

          {!loading && plans.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {plans.map((plan) => (
                <div
                  key={plan.id}
                  className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 flex flex-col"
                >
                  <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{plan.name}</p>
                  <p className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mt-1">
                    {plan.price_monthly == null ? "Custom" : plan.price_monthly === 0 ? "Free" : `$${plan.price_monthly}`}
                    {plan.price_monthly != null && plan.price_monthly > 0 && (
                      <span className="text-sm font-normal text-neutral-400">/mo</span>
                    )}
                  </p>

                  <ul className="mt-5 space-y-2.5 flex-1">
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.max_documents, "documents")}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.max_file_size_mb, "MB max file size")}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.messages_per_window, `messages / ${plan.limits.message_window_hours}h`)}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.max_workspaces, "workspaces")}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.quiz_generations_per_month, "quizzes / month")}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.tts_uses_per_day, "voice reads / day")}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.diagrams_infographics_per_month, "diagrams/infographics / month")}
                    </li>
                    <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                      <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                      {formatLimit(plan.limits.max_storage_mb, "MB storage")}
                    </li>
                    {plan.limits.priority_processing && (
                      <li className="flex items-start gap-2 text-xs text-neutral-600 dark:text-neutral-400">
                        <Check className="h-3.5 w-3.5 text-neutral-400 shrink-0 mt-0.5" />
                        Priority processing
                      </li>
                    )}
                  </ul>

                  <button
                    onClick={() => setContacted(true)}
                    className="mt-6 w-full text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
                  >
                    {plan.slug === "free" ? "Current plan" : "Contact us"}
                  </button>
                </div>
              ))}
            </div>
          )}

          {contacted && (
            <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-6">
              Thanks for your interest — billing isn&apos;t enabled yet. Reach out to support and we&apos;ll help you
              upgrade manually.
            </p>
          )}
        </div>
      </main>
    </>
  );
}
