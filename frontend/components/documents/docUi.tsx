"use client";

import type { DocumentItem, DocumentStatus } from "@/lib/types";

const AV = new Set(["mp3", "wav", "m4a", "mp4", "mov"]);
const VIDEO = new Set(["mp4", "mov"]);

export const READY_STATUSES: DocumentStatus[] = ["embedded", "ready"];
export const isReady = (d: DocumentItem) => READY_STATUSES.includes(d.status);
export const isMedia = (fileType: string) => AV.has(fileType);

/** File-type tile like the design: a dark page with the type label. */
export function DocTypeIcon({ fileType, size = 36 }: { fileType: string; size?: number }) {
  const t = fileType.toLowerCase();
  const label = t === "pdf" ? "PDF" : t === "docx" ? "DOC" : t === "pptx" ? "PPT" : t === "csv" ? "CSV" : t === "txt" ? "TXT" : null;
  const w = Math.round(size * 0.78);
  return (
    <span
      className="relative inline-flex shrink-0 items-end justify-center rounded-[4px] bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
      style={{ width: w, height: size, clipPath: "polygon(0 0, 70% 0, 100% 22%, 100% 100%, 0 100%)" }}
      aria-hidden
    >
      {label ? (
        <span className="mb-[18%] text-[9px] font-bold tracking-wide">{label}</span>
      ) : VIDEO.has(t) ? (
        <svg viewBox="0 0 24 24" className="mb-[22%] h-[42%] w-[42%] fill-current"><path d="M8 5v14l11-7z" /></svg>
      ) : AV.has(t) ? (
        <svg viewBox="0 0 24 24" className="mb-[22%] h-[42%] w-[42%] fill-none stroke-current" strokeWidth="2.5"><path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" /></svg>
      ) : (
        <svg viewBox="0 0 24 24" className="mb-[22%] h-[42%] w-[42%] fill-current"><path d="M4 18l5-6 4 4 3-3 4 5z" /><circle cx="8" cy="8" r="2" /></svg>
      )}
    </span>
  );
}

export function statusLabel(d: Pick<DocumentItem, "status" | "file_type">): string {
  switch (d.status) {
    case "uploaded":
      return "Queued";
    case "parsing":
      return isMedia(d.file_type) ? "Transcribing…" : "Processing…";
    case "embedded":
      return "Finishing…";
    case "ready":
      return "Ready";
    default:
      return "Failed";
  }
}

export function StatusPill({ doc }: { doc: Pick<DocumentItem, "status" | "file_type"> }) {
  const tone =
    doc.status === "failed"
      ? "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900"
      : doc.status === "ready"
        ? "bg-white text-neutral-800 ring-neutral-200 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700"
        : "bg-neutral-100 text-neutral-700 ring-neutral-200 dark:bg-neutral-800 dark:text-neutral-300 dark:ring-neutral-700";
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${tone}`}>
      {statusLabel(doc)}
    </span>
  );
}

export function formatSize(bytes?: number | null): string | null {
  if (bytes == null) return null;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function docMeta(d: DocumentItem): string {
  return [formatDate(d.created_at), formatSize(d.file_size), d.page_count ? `${d.page_count} pages` : null]
    .filter(Boolean)
    .join(" • ");
}
