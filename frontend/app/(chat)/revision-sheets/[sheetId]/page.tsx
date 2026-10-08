"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, Download, Loader2, RefreshCw, Trash2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import RevisionSheetPreview from "@/components/RevisionSheetPreview";
import { api, ApiError } from "@/lib/api";
import { LANGUAGE_NAMES, downloadSheetPdf } from "@/lib/revision";
import { RevisionSheetDetail } from "@/lib/types";

const POLL_MS = 3000;
const GIVE_UP_MS = 12 * 60 * 1000;

interface MonthlyQuota {
  limit: number | null;
  used: number;
  resetsIn: string | null;
}

export default function RevisionSheetPage() {
  const { sheetId } = useParams<{ sheetId: string }>();
  const router = useRouter();
  const [sheet, setSheet] = useState<RevisionSheetDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [quota, setQuota] = useState<MonthlyQuota | null>(null);
  const startedAt = useRef(0); // set when the page loads (not during render: Date.now() is impure)

  const load = useCallback(async () => {
    try {
      setSheet(await api.get<RevisionSheetDetail>(`/revision-sheets/${sheetId}`, { auth: true }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setNotFound(true);
      else setError("Couldn't load this revision sheet.");
    }
  }, [sheetId]);

  const loadQuota = useCallback(() => {
    api
      .get<{ quotas: { key: string; limit: number | boolean | null; current_usage: number; resets_in_human: string | null }[] }>(
        "/users/me/usage",
        { auth: true }
      )
      .then((usage) => {
        const q = usage.quotas.find((x) => x.key === "revision_sheets_per_month");
        if (q) setQuota({ limit: typeof q.limit === "number" ? q.limit : null, used: q.current_usage, resetsIn: q.resets_in_human });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    startedAt.current = Date.now();
    let cancelled = false;
    api
      .get<RevisionSheetDetail>(`/revision-sheets/${sheetId}`, { auth: true })
      .then((detail) => {
        if (!cancelled) setSheet(detail);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else setError("Couldn't load this revision sheet.");
      });
    loadQuota();
    return () => {
      cancelled = true;
    };
  }, [sheetId, loadQuota]);

  // While the sheet is being built, check on it every few seconds. A failed check (the server
  // waking up, a brief network blip) is ignored; polling only stops when the sheet finishes
  // or after a long timeout.
  const inProgress = sheet?.status === "queued" || sheet?.status === "generating";
  useEffect(() => {
    if (!inProgress) return;
    const timer = setInterval(async () => {
      if (Date.now() - startedAt.current > GIVE_UP_MS) {
        clearInterval(timer);
        setError("This is taking much longer than expected. Check back in a few minutes.");
        return;
      }
      try {
        const status = await api.get<{ status: string }>(`/revision-sheets/${sheetId}/status`, { auth: true });
        if (status.status !== "queued" && status.status !== "generating") {
          clearInterval(timer);
          await load();
          loadQuota();
        }
      } catch {
        // ignore and try again on the next tick
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [inProgress, sheetId, load, loadQuota]);

  async function handleDownload() {
    if (!sheet) return;
    setDownloading(true);
    setError(null);
    try {
      await downloadSheetPdf(sheet.id, sheet.title);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't download the PDF.");
    } finally {
      setDownloading(false);
    }
  }

  async function handleRegenerate() {
    if (!sheet) return;
    setRegenerating(true);
    setError(null);
    try {
      const created = await api.post<{ id: string }>(
        "/revision-sheets/",
        {
          title: sheet.title,
          ...(sheet.workspace_id ? { workspace_id: sheet.workspace_id } : { document_ids: sheet.document_ids }),
          topics: sheet.topics ?? undefined,
          language: sheet.language,
          page_target: sheet.page_target,
          include_weak_spots: sheet.include_weak_spots,
          regenerate: true,
        },
        { auth: true }
      );
      router.push(`/revision-sheets/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't regenerate this sheet. Please try again.");
      setRegenerating(false);
    }
  }

  async function handleDelete() {
    if (!sheet || !window.confirm(`Delete "${sheet.title}"? This can't be undone.`)) return;
    setDeleting(true);
    try {
      await api.delete(`/revision-sheets/${sheet.id}`, { auth: true });
      router.push("/revision-sheets");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't delete this sheet.");
      setDeleting(false);
    }
  }

  const content = sheet?.content;
  const quotaLeft = quota && quota.limit !== null ? Math.max(quota.limit - quota.used, 0) : null;

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 pt-16 lg:pt-8">
          <button
            onClick={() => router.push("/revision-sheets")}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            All revision sheets
          </button>

          {notFound ? (
            <p className="text-sm text-neutral-500">This revision sheet doesn&apos;t exist (or was deleted).</p>
          ) : !sheet ? (
            error ? (
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            ) : (
              <Loader2 className="h-4 w-4 animate-spin text-neutral-400" />
            )
          ) : (
            <>
              <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
                {sheet.title}
              </h1>
              <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-5">
                {LANGUAGE_NAMES[sheet.language]} · {sheet.page_target} page{sheet.page_target > 1 ? "s" : ""}
                {sheet.include_weak_spots ? " · with weak spots" : ""}
                {sheet.topics?.length ? ` · focus: ${sheet.topics.join(", ")}` : ""}
              </p>

              {inProgress && (
                <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 px-5 py-8 text-center">
                  <Loader2 className="h-6 w-6 mx-auto animate-spin text-neutral-400 mb-3" />
                  <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">Building your revision sheet…</p>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1.5">
                    Reading your material, checking every formula and number against the source, and laying out the
                    page. This usually takes one to two minutes. You can leave this page; it will keep working.
                  </p>
                </div>
              )}

              {sheet.status === "failed" && (
                <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-4 py-3">
                  <p className="text-sm font-medium text-red-700 dark:text-red-400">Couldn&apos;t build this sheet</p>
                  <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                    {sheet.error_message || "Something went wrong. Please try again."} Nothing was counted against
                    your allowance.
                  </p>
                  <button
                    onClick={handleRegenerate}
                    disabled={regenerating}
                    className="mt-3 flex items-center gap-1.5 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-1.5 disabled:opacity-50"
                  >
                    {regenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    Try again
                  </button>
                </div>
              )}

              {sheet.status === "ready" && content && (
                <>
                  <div className="flex flex-wrap items-center gap-2 mb-4">
                    <button
                      onClick={handleDownload}
                      disabled={downloading}
                      className="flex items-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-4 py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-60"
                    >
                      {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                      Download PDF
                    </button>
                    <button
                      onClick={handleRegenerate}
                      disabled={regenerating}
                      title="Build a fresh version. This uses one of your monthly sheets."
                      className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-60"
                    >
                      {regenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      Regenerate
                    </button>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      aria-label="Delete this sheet"
                      className="ml-auto text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-2"
                    >
                      {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    </button>
                  </div>

                  {quotaLeft !== null && quota && (
                    <p className="text-xs text-neutral-400 mb-4">
                      {quotaLeft} of {quota.limit} revision sheets left this month
                      {quotaLeft === 0 && quota.resetsIn ? ` · resets in ${quota.resetsIn}` : ""}
                    </p>
                  )}

                  {content.warnings.length > 0 && (
                    <div className="rounded-lg border border-amber-300 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/30 px-3 py-2 mb-5 space-y-1">
                      {content.warnings.map((w, i) => (
                        <p key={i} className="text-xs text-amber-800 dark:text-amber-300 flex items-start gap-1.5">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                          {w}
                        </p>
                      ))}
                    </div>
                  )}

                  <RevisionSheetPreview content={content} />

                  {content.sources.length > 0 && (
                    <div className="mt-8 border-t border-neutral-200 dark:border-neutral-800 pt-4">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400 mb-1.5">Sources</p>
                      <ul className="space-y-0.5">
                        {content.sources.map((s) => (
                          <li key={s.document_id} className="text-xs text-neutral-500 dark:text-neutral-400">
                            {s.tag ? `${s.tag} = ` : ""}
                            {s.document}
                          </li>
                        ))}
                      </ul>
                      <p className="text-[11px] text-neutral-400 mt-3">
                        AI-generated revision aid based on your uploaded material. Verify against your source documents.
                      </p>
                    </div>
                  )}
                </>
              )}

              {error && <p className="text-xs text-red-600 dark:text-red-400 mt-4">{error}</p>}
            </>
          )}
        </div>
      </main>
    </>
  );
}
