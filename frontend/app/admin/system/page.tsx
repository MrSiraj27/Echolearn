"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { adminApi } from "@/lib/admin-api";

interface ProviderStat {
  provider: string;
  total_calls: number;
  error_count: number;
  error_rate: number;
  avg_duration_ms: number | null;
}
interface UsageOverview {
  calls_today: number;
  calls_this_week: number;
  calls_this_month: number;
  provider_stats: ProviderStat[];
  purpose_breakdown: { purpose: string; count: number }[];
  top_users: { user_id: string; email: string; call_count: number }[];
}
interface StuckJob {
  document_id: string;
  filename: string;
  user_email: string;
  status: string;
  stuck_for_minutes: number;
}
interface FailedJob {
  document_id: string;
  filename: string;
  user_email: string;
  created_at: string;
}
interface JobHealth {
  stuck_jobs: StuckJob[];
  failed_jobs: FailedJob[];
}
interface StorageItem {
  user_id: string;
  email: string;
  document_count: number;
  bytes_used: number;
}
interface Storage {
  total_bytes: number;
  by_user: StorageItem[];
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function statusColor(errorRate: number): string {
  if (errorRate >= 20) return "bg-red-500";
  if (errorRate >= 5) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function AdminSystemPage() {
  const [usage, setUsage] = useState<UsageOverview | null>(null);
  const [jobHealth, setJobHealth] = useState<JobHealth | null>(null);
  const [storage, setStorage] = useState<Storage | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([
      adminApi.get<UsageOverview>("/admin/system/usage-overview"),
      adminApi.get<JobHealth>("/admin/system/job-health"),
      adminApi.get<Storage>("/admin/system/storage"),
    ])
      .then(([u, j, s]) => {
        setUsage(u);
        setJobHealth(j);
        setStorage(s);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function retryDocument(documentId: string) {
    setRetrying(documentId);
    try {
      await adminApi.post(`/admin/system/documents/${documentId}/retry-processing`);
      load();
    } finally {
      setRetrying(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
        System Health
      </h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        Provider usage, error rates, stuck jobs, and storage — separate from business analytics.
      </p>

      {loading && <p className="text-sm text-neutral-400">Loading...</p>}

      {!loading && usage && (
        <div className="space-y-8">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
              <p className="text-xs text-neutral-400 uppercase tracking-wide mb-1">Calls today</p>
              <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{usage.calls_today}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
              <p className="text-xs text-neutral-400 uppercase tracking-wide mb-1">This week</p>
              <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{usage.calls_this_week}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
              <p className="text-xs text-neutral-400 uppercase tracking-wide mb-1">This month</p>
              <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{usage.calls_this_month}</p>
            </div>
          </div>

          <div>
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">Provider status</p>
            <div className="space-y-2">
              {usage.provider_stats.map((p) => (
                <div
                  key={p.provider}
                  className="flex items-center justify-between text-sm px-3 py-2.5 rounded-lg border border-neutral-200 dark:border-neutral-800"
                >
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${statusColor(p.error_rate)}`} />
                    <span className="font-medium text-neutral-900 dark:text-neutral-100">{p.provider}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-neutral-500 dark:text-neutral-400">
                    <span>{p.total_calls} calls</span>
                    <span>{p.error_rate}% errors</span>
                    {p.avg_duration_ms != null && <span>{Math.round(p.avg_duration_ms)}ms avg</span>}
                  </div>
                </div>
              ))}
              {usage.provider_stats.length === 0 && (
                <p className="text-sm text-neutral-400">No provider calls logged yet.</p>
              )}
            </div>
          </div>

          {jobHealth && jobHealth.stuck_jobs.length > 0 && (
            <div className="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50/50 dark:bg-amber-950/20 p-4">
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-2">Stuck jobs</p>
              <div className="space-y-1.5">
                {jobHealth.stuck_jobs.map((j) => (
                  <div key={j.document_id} className="flex items-center justify-between text-sm bg-white dark:bg-neutral-900 rounded-lg px-3 py-2">
                    <span className="text-neutral-800 dark:text-neutral-200 truncate">
                      {j.filename} <span className="text-neutral-400">({j.user_email})</span>
                    </span>
                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      <span className="text-xs text-amber-700 dark:text-amber-400">
                        {j.status}, {j.stuck_for_minutes}m
                      </span>
                      <button
                        onClick={() => retryDocument(j.document_id)}
                        disabled={retrying === j.document_id}
                        className="flex items-center gap-1 text-xs font-medium text-neutral-600 dark:text-neutral-300 border border-neutral-300 dark:border-neutral-700 rounded-lg px-2 py-1 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Retry
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {jobHealth && jobHealth.failed_jobs.length > 0 && (
            <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50/40 dark:bg-red-950/20 p-4">
              <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-2">Failed jobs</p>
              <div className="space-y-1.5">
                {jobHealth.failed_jobs.map((j) => (
                  <div key={j.document_id} className="flex items-center justify-between text-sm bg-white dark:bg-neutral-900 rounded-lg px-3 py-2">
                    <span className="text-neutral-800 dark:text-neutral-200 truncate">
                      {j.filename} <span className="text-neutral-400">({j.user_email})</span>
                    </span>
                    <button
                      onClick={() => retryDocument(j.document_id)}
                      disabled={retrying === j.document_id}
                      className="flex items-center gap-1 text-xs font-medium text-neutral-600 dark:text-neutral-300 border border-neutral-300 dark:border-neutral-700 rounded-lg px-2 py-1 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                    >
                      <RefreshCw className="h-3 w-3" />
                      Retry
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">Top users by call volume</p>
            <div className="space-y-1">
              {usage.top_users.map((u) => (
                <div key={u.user_id} className="flex items-center justify-between text-sm px-3 py-1.5 rounded-lg bg-neutral-50 dark:bg-neutral-900">
                  <span className="text-neutral-700 dark:text-neutral-300">{u.email}</span>
                  <span className="text-neutral-400 text-xs">{u.call_count} calls</span>
                </div>
              ))}
              {usage.top_users.length === 0 && <p className="text-sm text-neutral-400">No usage data yet.</p>}
            </div>
          </div>

          {storage && (
            <div>
              <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                Storage — {formatBytes(storage.total_bytes)} total
              </p>
              <div className="space-y-1">
                {storage.by_user.slice(0, 10).map((s) => (
                  <div key={s.user_id} className="flex items-center justify-between text-sm px-3 py-1.5 rounded-lg bg-neutral-50 dark:bg-neutral-900">
                    <span className="text-neutral-700 dark:text-neutral-300">{s.email}</span>
                    <span className="text-neutral-400 text-xs">
                      {s.document_count} docs · {formatBytes(s.bytes_used)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
