"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, Gauge } from "lucide-react";
import { api } from "@/lib/api";

interface QuotaUsageItem {
  key: string;
  label: string;
  limit: number | boolean | null;
  current_usage: number;
  resets_in_seconds: number | null;
  resets_in_human: string | null;
}

interface MyUsageResponse {
  plan_id: string | null;
  plan_name: string | null;
  quotas: QuotaUsageItem[];
}

// Only the rolling-window quotas make sense as "resets in X" progress bars — the
// static ones (documents, workspaces) don't reset on a timer.
const ROLLING_KEYS = new Set([
  "messages_per_window",
  "quiz_generations_per_month",
  "tts_uses_per_day",
  "diagrams_infographics_per_month",
]);

export default function UsagePanel() {
  const [usage, setUsage] = useState<MyUsageResponse | null>(null);
  const [expanded, setExpanded] = useState(false);

  function load() {
    api
      .get<MyUsageResponse>("/users/me/usage", { auth: true })
      .then(setUsage)
      .catch(() => setUsage(null));
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (expanded) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  if (!usage) return null;

  const rollingQuotas = usage.quotas.filter((q) => ROLLING_KEYS.has(q.key));

  return (
    <div className="border-t border-neutral-200 dark:border-neutral-800 px-3 py-2.5">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Gauge className="h-3.5 w-3.5" />
          {usage.plan_name || "Free"} plan
        </span>
        {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {expanded && (
        <div className="mt-2.5 space-y-2.5">
          {rollingQuotas.map((q) => {
            const unlimited = q.limit === null;
            const limitNum = typeof q.limit === "number" ? q.limit : null;
            const pct = unlimited || !limitNum ? 0 : Math.min(100, (q.current_usage / limitNum) * 100);
            const isNear = pct >= 90;
            return (
              <div key={q.key}>
                <div className="flex items-center justify-between text-[11px] text-neutral-500 dark:text-neutral-400 mb-1">
                  <span>{q.label}</span>
                  <span>{unlimited ? "Unlimited" : `${q.current_usage} / ${q.limit}`}</span>
                </div>
                {!unlimited && (
                  <div className="h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        isNear ? "bg-red-500" : "bg-neutral-900 dark:bg-neutral-100"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                )}
                {!unlimited && q.resets_in_human && q.current_usage >= (limitNum || 0) && (
                  <p className="text-[10px] text-red-500 dark:text-red-400 mt-1">Resets in {q.resets_in_human}</p>
                )}
              </div>
            );
          })}
          <Link
            href="/upgrade"
            className="block text-center text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-1.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors mt-1"
          >
            Upgrade Plan
          </Link>
        </div>
      )}
    </div>
  );
}
