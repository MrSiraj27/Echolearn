"use client";

import { useState } from "react";
import { Flag, Loader2, ThumbsDown, ThumbsUp } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { FeedbackRating } from "@/lib/types";

/** Helpful / Not helpful / Report incorrect for one assistant answer. Clicking the active
 *  rating again clears it. Ratings are only used to evaluate answer quality. */
export default function AnswerFeedback({
  chatId,
  messageId,
  initial,
}: {
  chatId: string;
  messageId: string;
  initial?: FeedbackRating | null;
}) {
  const [rating, setRating] = useState<FeedbackRating | null>(initial ?? null);
  const [saving, setSaving] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [thanks, setThanks] = useState(false);

  async function save(next: FeedbackRating | null, note?: string) {
    const previous = rating;
    setRating(next);
    setSaving(true);
    setError(null);
    try {
      const path = `/chats/${chatId}/messages/${messageId}/feedback`;
      if (next) await api.put(path, { rating: next, comment: note || null }, { auth: true });
      else await api.delete(path, { auth: true });
      if (next) {
        setThanks(true);
        setTimeout(() => setThanks(false), 2000);
      }
    } catch (err) {
      setRating(previous);
      setError(err instanceof ApiError ? err.detail : "Couldn't save your feedback.");
    } finally {
      setSaving(false);
    }
  }

  const btn = (active: boolean) =>
    `inline-flex items-center rounded p-0.5 transition-colors disabled:opacity-50 ${
      active ? "text-neutral-900 dark:text-neutral-100" : "hover:text-neutral-700 dark:hover:text-neutral-300"
    }`;

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <button
        onClick={() => save(rating === "helpful" ? null : "helpful")}
        disabled={saving}
        aria-pressed={rating === "helpful"}
        aria-label="Helpful"
        title="Helpful"
        className={btn(rating === "helpful")}
      >
        <ThumbsUp className={`h-3.5 w-3.5 ${rating === "helpful" ? "fill-current" : ""}`} />
      </button>
      <button
        onClick={() => save(rating === "not_helpful" ? null : "not_helpful")}
        disabled={saving}
        aria-pressed={rating === "not_helpful"}
        aria-label="Not helpful"
        title="Not helpful"
        className={btn(rating === "not_helpful")}
      >
        <ThumbsDown className={`h-3.5 w-3.5 ${rating === "not_helpful" ? "fill-current" : ""}`} />
      </button>
      <button
        onClick={() => (rating === "incorrect" ? save(null) : setReporting((v) => !v))}
        disabled={saving}
        aria-pressed={rating === "incorrect"}
        aria-label="Report incorrect answer"
        title="Report incorrect answer"
        className={btn(rating === "incorrect")}
      >
        <Flag className={`h-3.5 w-3.5 ${rating === "incorrect" ? "fill-current" : ""}`} />
      </button>
      {saving && <Loader2 className="h-3 w-3 animate-spin" />}
      {thanks && !saving && <span className="text-[11px]">Thanks for the feedback</span>}
      {error && (
        <span role="alert" className="text-[11px] text-red-600 dark:text-red-400">
          {error}
        </span>
      )}
      {reporting && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setReporting(false);
            void save("incorrect", comment.trim());
            setComment("");
          }}
          className="flex w-full items-center gap-1.5 pt-1"
        >
          <input
            autoFocus
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            placeholder="What's wrong? (optional)"
            aria-label="What is wrong with this answer"
            className="min-w-0 flex-1 rounded border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2 py-1 text-xs text-neutral-800 dark:text-neutral-200 outline-none"
          />
          <button type="submit" className="rounded bg-neutral-900 dark:bg-neutral-100 px-2 py-1 text-xs text-white dark:text-neutral-900">
            Report
          </button>
          <button type="button" onClick={() => setReporting(false)} className="text-xs hover:underline">
            Cancel
          </button>
        </form>
      )}
    </span>
  );
}
