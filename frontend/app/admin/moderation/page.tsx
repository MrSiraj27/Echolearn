"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { adminApi } from "@/lib/admin-api";

interface ContentReportItem {
  id: string;
  document_id: string;
  document_filename: string;
  document_owner_email: string;
  reporter_email: string | null;
  reason: string;
  details: string | null;
  status: string;
  auto_flagged: boolean;
  created_at: string;
  text_preview: string | null;
}
interface AbuseSignal {
  user_id: string;
  email: string;
  violation_count: number;
  last_violation_at: string;
}

type Tab = "reports" | "abuse";

export default function AdminModerationPage() {
  const [tab, setTab] = useState<Tab>("reports");
  const [reports, setReports] = useState<ContentReportItem[]>([]);
  const [abuse, setAbuse] = useState<AbuseSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  function load() {
    setLoading(true);
    Promise.all([adminApi.get<ContentReportItem[]>("/admin/moderation/reports"), adminApi.get<AbuseSignal[]>("/admin/moderation/abuse-signals")])
      .then(([r, a]) => {
        setReports(r);
        setAbuse(a);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleAction(reportId: string, action: "dismiss" | "remove_document" | "suspend_user") {
    setActingId(reportId);
    try {
      await adminApi.post(`/admin/moderation/reports/${reportId}/action`, {
        action,
        notes: notes[reportId] || "",
      });
      load();
    } finally {
      setActingId(null);
    }
  }

  const pending = reports.filter((r) => r.status === "pending");
  const resolved = reports.filter((r) => r.status !== "pending");

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">Moderation</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        Review flagged documents and monitor repeated rate-limit abuse.
      </p>

      <div className="flex gap-1 border-b border-neutral-200 dark:border-neutral-800 mb-4">
        {(["reports", "abuse"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-sm px-3 py-2 border-b-2 -mb-px capitalize transition-colors ${
              tab === t
                ? "border-neutral-900 dark:border-neutral-100 text-neutral-900 dark:text-neutral-100 font-medium"
                : "border-transparent text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
            }`}
          >
            {t === "reports" ? `Reports (${pending.length} pending)` : "Abuse Signals"}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-neutral-400">Loading...</p>}

      {!loading && tab === "reports" && (
        <div className="space-y-3">
          {[...pending, ...resolved].map((report) => (
            <div key={report.id} className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div>
                  <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 flex items-center gap-1.5">
                    {report.auto_flagged && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                    {report.document_filename}
                  </p>
                  <p className="text-xs text-neutral-400">
                    Owner: {report.document_owner_email} · Reporter: {report.reporter_email || "auto-flagged"} ·{" "}
                    {report.reason}
                  </p>
                </div>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${
                    report.status === "pending"
                      ? "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400"
                      : "bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400"
                  }`}
                >
                  {report.status}
                </span>
              </div>

              {report.details && <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-2">{report.details}</p>}

              {report.text_preview && (
                <p className="text-xs text-neutral-500 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-900 rounded-lg px-3 py-2 mb-2 line-clamp-3">
                  {report.text_preview}
                </p>
              )}

              {report.status === "pending" && (
                <div className="space-y-2">
                  <input
                    value={notes[report.id] || ""}
                    onChange={(e) => setNotes((prev) => ({ ...prev, [report.id]: e.target.value }))}
                    placeholder="Notes (required before acting)"
                    className="w-full text-xs rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2.5 py-1.5 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAction(report.id, "dismiss")}
                      disabled={actingId === report.id || !notes[report.id]?.trim()}
                      className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-2.5 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-40"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => handleAction(report.id, "remove_document")}
                      disabled={actingId === report.id || !notes[report.id]?.trim()}
                      className="text-xs font-medium border border-red-300 dark:border-red-900 text-red-600 dark:text-red-400 rounded-lg px-2.5 py-1.5 hover:bg-red-50 dark:hover:bg-red-950/30 disabled:opacity-40"
                    >
                      Remove Document
                    </button>
                    <button
                      onClick={() => handleAction(report.id, "suspend_user")}
                      disabled={actingId === report.id || !notes[report.id]?.trim()}
                      className="text-xs font-medium border border-amber-300 dark:border-amber-800 text-amber-700 dark:text-amber-400 rounded-lg px-2.5 py-1.5 hover:bg-amber-50 dark:hover:bg-amber-950/30 disabled:opacity-40"
                    >
                      Block User
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {reports.length === 0 && <p className="text-sm text-neutral-400">No reports.</p>}
        </div>
      )}

      {!loading && tab === "abuse" && (
        <div className="space-y-1.5">
          {abuse.map((a) => (
            <div key={a.user_id} className="flex items-center justify-between text-sm px-3 py-2.5 rounded-lg border border-neutral-200 dark:border-neutral-800">
              <div>
                <p className="text-neutral-900 dark:text-neutral-100 font-medium">{a.email}</p>
                <p className="text-xs text-neutral-400">Last: {new Date(a.last_violation_at).toLocaleString()}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-medium text-red-600 dark:text-red-400">{a.violation_count} hits</span>
                <Link
                  href={`/admin/users/${a.user_id}`}
                  className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                >
                  View <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            </div>
          ))}
          {abuse.length === 0 && <p className="text-sm text-neutral-400">No abuse signals detected.</p>}
        </div>
      )}
    </div>
  );
}
