"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2, Lock, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { DocumentItem, SheetLanguage } from "@/lib/types";

interface UsageQuota {
  key: string;
  limit: number | boolean | null;
  current_usage: number;
  resets_in_human: string | null;
}

const LANGUAGES: { value: SheetLanguage; label: string; hint: string }[] = [
  { value: "en", label: "English", hint: "" },
  { value: "ur", label: "اردو", hint: "Urdu" },
  { value: "roman_ur", label: "Roman Urdu", hint: "Urdu in English letters" },
  { value: "bilingual", label: "English + اردو", hint: "English with an Urdu line under each item" },
];

const MAX_TOPICS = 8;

/**
 * Create a revision sheet. Opened from a document, a workspace, a study plan, or the
 * Revision Sheets page; `workspace` makes it cover that whole workspace.
 */
export default function RevisionSheetModal({
  documents,
  preselectedDocumentIds = [],
  workspace,
  defaultTitle,
  onClose,
}: {
  documents: DocumentItem[];
  preselectedDocumentIds?: string[];
  workspace?: { id: string; name: string; label?: string } | null;
  defaultTitle?: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const readyDocs = documents.filter((d) => d.status === "embedded" || d.status === "ready");
  const [selectedIds, setSelectedIds] = useState<string[]>(
    preselectedDocumentIds.filter((id) => readyDocs.some((d) => d.id === id))
  );
  const [topics, setTopics] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState("");
  const [language, setLanguage] = useState<SheetLanguage>("en");
  const [pages, setPages] = useState<1 | 2>(1);
  const [weakSpots, setWeakSpots] = useState(false);
  const [quota, setQuota] = useState<UsageQuota | null>(null);
  const [maxPages, setMaxPages] = useState<number | null>(2);
  const [advanced, setAdvanced] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ quotas: UsageQuota[] }>("/users/me/usage", { auth: true })
      .then((usage) => {
        const find = (key: string) => usage.quotas.find((q) => q.key === key);
        setQuota(find("revision_sheets_per_month") ?? null);
        const pagesLimit = find("revision_sheet_max_pages")?.limit;
        setMaxPages(typeof pagesLimit === "number" ? pagesLimit : null);
        setAdvanced(find("revision_sheet_advanced")?.limit !== false);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  function toggleDoc(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  }

  function addTopic() {
    const value = topicInput.trim().slice(0, 60);
    if (!value || topics.length >= MAX_TOPICS) return;
    if (!topics.some((t) => t.toLowerCase() === value.toLowerCase())) setTopics((prev) => [...prev, value]);
    setTopicInput("");
  }

  const twoPagesLocked = maxPages !== null && maxPages < 2;
  const quotaLimit = typeof quota?.limit === "number" ? quota.limit : null;
  const quotaLeft = quotaLimit !== null && quota ? Math.max(quotaLimit - quota.current_usage, 0) : null;

  async function handleCreate() {
    if (!workspace && selectedIds.length === 0) {
      setError("Select at least one document.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const sheet = await api.post<{ id: string }>(
        "/revision-sheets/",
        {
          ...(workspace ? { workspace_id: workspace.id } : { document_ids: selectedIds }),
          title: defaultTitle || undefined,
          topics: topics.length ? topics : undefined,
          language,
          page_target: pages,
          include_weak_spots: weakSpots,
        },
        { auth: true }
      );
      router.push(`/revision-sheets/${sheet.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't start the revision sheet. Please try again.");
      setLoading(false);
    }
  }

  const pill = (active: boolean, locked = false) =>
    `text-xs px-3 py-1.5 rounded-full border transition-colors inline-flex items-center gap-1 ${
      active
        ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
        : locked
          ? "border-neutral-200 dark:border-neutral-800 text-neutral-400 dark:text-neutral-600 cursor-not-allowed"
          : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
    }`;

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-md bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-neutral-100 dark:border-neutral-800">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Revision sheet</h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            A compact printable cheat sheet of key definitions, formulas and facts from your material.
          </p>
        </div>

        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-2">From</p>
            {workspace ? (
              <p className="text-sm text-neutral-700 dark:text-neutral-300">
                {workspace.label ?? `All documents in “${workspace.name}”`}
              </p>
            ) : (
              <>
                {readyDocs.length === 0 && (
                  <p className="text-xs text-neutral-400 dark:text-neutral-500">No ready documents yet.</p>
                )}
                <div className="space-y-1.5">
                  {readyDocs.map((doc) => (
                    <label
                      key={doc.id}
                      className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(doc.id)}
                        onChange={() => toggleDoc(doc.id)}
                        className="accent-neutral-900 dark:accent-neutral-100"
                      />
                      <span className="truncate">{doc.filename}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>

          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">
              Focus topics <span className="font-normal text-neutral-400">(optional)</span>
            </p>
            <div className="flex flex-wrap gap-1.5 mb-1.5">
              {topics.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 text-xs rounded-full bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 pl-2.5 pr-1.5 py-1"
                >
                  {t}
                  <button
                    onClick={() => setTopics((prev) => prev.filter((x) => x !== t))}
                    aria-label={`Remove ${t}`}
                    className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <input
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addTopic();
                }
              }}
              onBlur={addTopic}
              disabled={topics.length >= MAX_TOPICS}
              placeholder={topics.length >= MAX_TOPICS ? "Topic limit reached" : "Type a topic and press Enter"}
              className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2.5 py-1.5 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100 disabled:opacity-60"
            />
          </div>

          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Language</p>
            <div className="flex flex-wrap gap-1.5">
              {LANGUAGES.map((l) => {
                const locked = l.value !== "en" && !advanced;
                return (
                  <button
                    key={l.value}
                    onClick={() => !locked && setLanguage(l.value)}
                    disabled={locked}
                    title={locked ? "Available on paid plans" : l.hint || undefined}
                    className={pill(language === l.value, locked)}
                  >
                    {locked && <Lock className="h-3 w-3" />}
                    {l.label}
                  </button>
                );
              })}
            </div>
            {!advanced && (
              <p className="text-[11px] text-neutral-400 mt-1.5">
                Urdu, Roman Urdu and bilingual sheets are on paid plans.{" "}
                <Link href="/upgrade" className="underline hover:text-neutral-600 dark:hover:text-neutral-300">
                  See plans
                </Link>
              </p>
            )}
          </div>

          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Length</p>
            <div className="flex gap-1.5">
              <button onClick={() => setPages(1)} className={pill(pages === 1)}>
                1 page
              </button>
              <button
                onClick={() => !twoPagesLocked && setPages(2)}
                disabled={twoPagesLocked}
                title={twoPagesLocked ? "Available on paid plans" : undefined}
                className={pill(pages === 2, twoPagesLocked)}
              >
                {twoPagesLocked && <Lock className="h-3 w-3" />}2 pages
              </button>
            </div>
          </div>

          <label
            className={`flex items-start gap-2 text-sm ${
              advanced ? "text-neutral-700 dark:text-neutral-300 cursor-pointer" : "text-neutral-400 cursor-not-allowed"
            }`}
          >
            <input
              type="checkbox"
              checked={weakSpots && advanced}
              disabled={!advanced}
              onChange={(e) => setWeakSpots(e.target.checked)}
              className="mt-0.5 accent-neutral-900 dark:accent-neutral-100"
            />
            <span>
              Include my weak spots
              <span className="block text-xs text-neutral-500 dark:text-neutral-400">
                Adds a “Watch out” box from quiz answers you got wrong and flashcards you find hard.
                {!advanced && " (Paid plans)"}
              </span>
            </span>
          </label>

          {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
        </div>

        <div className="px-5 py-3 border-t border-neutral-100 dark:border-neutral-800 flex items-center justify-between gap-2">
          <p className="text-[11px] text-neutral-400 min-w-0">
            {quotaLimit !== null && quotaLeft !== null
              ? `${quotaLeft} of ${quotaLimit} left this month${
                  quotaLeft === 0 && quota?.resets_in_human ? ` · resets in ${quota.resets_in_human}` : ""
                }`
              : ""}
          </p>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={onClose}
              className="text-xs font-medium text-neutral-600 dark:text-neutral-400 px-3 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={loading}
              className="text-xs font-medium text-white dark:text-neutral-900 bg-neutral-900 dark:bg-neutral-100 px-3.5 py-1.5 rounded-lg hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {loading ? "Starting..." : "Create sheet"}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
