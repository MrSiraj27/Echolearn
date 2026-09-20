import { getAccessToken, tryRefresh } from "@/lib/api";
import { PastPaperItem, PatternSource, PracticeQuestionType } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const PRACTICE_DISCLAIMER =
  "This is an AI-generated practice paper based on your materials and any patterns you provided. It is a study aid, not a guaranteed prediction of your actual exam.";

export const QUESTION_TYPE_LABELS: Record<PracticeQuestionType, string> = {
  multiple_choice: "Multiple Choice",
  short_answer: "Short Answer",
  long_answer: "Long Answer",
  numerical: "Numerical",
  diagram_based: "Diagram-Based",
};

export const PATTERN_BADGE: Record<PatternSource, string> = {
  standard: "Standard practice format",
  past_papers: "Based on past papers",
  custom: "Custom structure",
};

export function patternBadgeText(source: PatternSource, note: string | null): string {
  return note || PATTERN_BADGE[source];
}

async function authedFetch(path: string, init: RequestInit, retry = true): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (res.status === 401 && retry && (await tryRefresh())) return authedFetch(path, init, false);
  return res;
}

async function errorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    return typeof data.detail === "string" ? data.detail : fallback;
  } catch {
    return fallback;
  }
}

export async function uploadPastPaper(file: File, examName?: string): Promise<PastPaperItem> {
  const form = new FormData();
  form.append("file", file);
  if (examName?.trim()) form.append("exam_name", examName.trim());
  const res = await authedFetch("/past-papers/upload", { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorDetail(res, "Upload failed. Please try again."));
  return res.json();
}

/** Authenticated blob download (same approach as ExportMenu). */
export async function downloadPaperPdf(
  paperId: string,
  title: string,
  variant: "question" | "answer_key"
): Promise<void> {
  const res = await authedFetch(`/practice-papers/${paperId}/export?format=pdf&variant=${variant}`, {
    method: "GET",
  });
  if (!res.ok) throw new Error(await errorDetail(res, "Download failed. Please try again."));
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const safeTitle = (title || "practice_paper").replace(/[^\w-]+/g, "_").slice(0, 60);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${safeTitle}_${variant === "answer_key" ? "answer_key" : "question_paper"}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
