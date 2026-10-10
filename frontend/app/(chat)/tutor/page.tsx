"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, GraduationCap, Loader2, Lock, Trash2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { TutorLanguage, TutorLevel, TutorSession, TutorSessionListItem } from "@/lib/types";

const LEVELS: { value: TutorLevel; label: string; hint: string }[] = [
  { value: "beginner", label: "Beginner", hint: "Smaller steps, simpler questions" },
  { value: "intermediate", label: "Intermediate", hint: "A balanced mix" },
  { value: "exam_ready", label: "Exam-ready", hint: "Fewer, harder application questions" },
];
const LANGUAGES: { value: TutorLanguage; label: string }[] = [
  { value: "en", label: "English" },
  { value: "ur", label: "اردو" },
  { value: "roman_ur", label: "Roman Urdu" },
];

interface Quota {
  key: string;
  limit: number | boolean | string[] | null;
  current_usage: number;
  resets_in_human: string | null;
}

const STATUS_LABEL: Record<string, string> = { active: "In progress", completed: "Completed", abandoned: "Stopped" };

function TutorStart() {
  const router = useRouter();
  const params = useSearchParams();
  const documents = useChatStore((s) => s.documents);
  const loadDocuments = useChatStore((s) => s.loadDocuments);
  const readyDocs = useMemo(() => documents.filter((d) => d.status === "embedded" || d.status === "ready"), [documents]);

  const [topic, setTopic] = useState(params.get("topic") ?? "");
  const [selectedIds, setSelectedIds] = useState<string[]>(() => {
    const doc = params.get("doc");
    return doc ? [doc] : [];
  });
  const [workspaceId, setWorkspaceId] = useState<string | null>(params.get("workspace"));
  const [level, setLevel] = useState<TutorLevel>("intermediate");
  const [language, setLanguage] = useState<TutorLanguage>("en");
  const [sessions, setSessions] = useState<TutorSessionListItem[]>([]);
  const [quotas, setQuotas] = useState<Quota[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const weekly = quotas.find((q) => q.key === "tutor_sessions_per_week");
  const allowedLevels = (quotas.find((q) => q.key === "tutor_levels_allowed")?.limit as string[] | undefined) ?? null;
  const allowedLanguages = (quotas.find((q) => q.key === "tutor_languages_allowed")?.limit as string[] | undefined) ?? null;
  const weeklyLimit = typeof weekly?.limit === "number" ? weekly.limit : null;
  const weeklyLeft = weeklyLimit !== null && weekly ? Math.max(weeklyLimit - weekly.current_usage, 0) : null;

  useEffect(() => {
    loadDocuments().catch(() => {});
    api.get<TutorSessionListItem[]>("/tutor/sessions", { auth: true }).then(setSessions).catch(() => {});
    api
      .get<{ quotas: Quota[]; preferred_language?: TutorLanguage }>("/users/me/usage", { auth: true })
      .then((usage) => {
        setQuotas(usage.quotas);
        if (usage.preferred_language === "ur" || usage.preferred_language === "roman_ur") {
          setLanguage(usage.preferred_language);
        }
      })
      .catch(() => {});
  }, [loadDocuments]);

  // Pre-select from a link: the chat this came from ("Teach me this"). A `doc` link is read
  // into the initial state above.
  useEffect(() => {
    const chat = params.get("chat");
    if (!chat) return;
    api
      .get<{ document_ids: string[]; workspace_id: string | null }>(`/chats/${chat}`, { auth: true })
      .then((c) => {
        if (c.workspace_id) setWorkspaceId(c.workspace_id);
        else setSelectedIds(c.document_ids);
      })
      .catch(() => {});
  }, [params]);

  function toggleDoc(id: string) {
    setWorkspaceId(null);
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  }

  async function start() {
    if (topic.trim().length < 3) {
      setError("What would you like to learn? Type a topic from your notes.");
      return;
    }
    if (!workspaceId && selectedIds.length === 0) {
      setError("Choose at least one document to learn from.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const session = await api.post<TutorSession>(
        "/tutor/sessions",
        {
          topic: topic.trim(),
          level,
          language,
          ...(workspaceId ? { workspace_id: workspaceId } : { document_ids: selectedIds }),
        },
        { auth: true }
      );
      router.push(`/tutor/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't start the session. Please try again.");
      setLoading(false);
    }
  }

  async function remove(item: TutorSessionListItem) {
    if (!window.confirm(`Delete this session on "${item.topic}"?`)) return;
    setDeletingId(item.id);
    try {
      await api.delete(`/tutor/sessions/${item.id}`, { auth: true });
      setSessions((prev) => prev.filter((s) => s.id !== item.id));
    } catch {
      setError("Couldn't delete that session.");
    } finally {
      setDeletingId(null);
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

  const suggestions = readyDocs
    .filter((d) => selectedIds.includes(d.id))
    .flatMap((d) => d.suggested_questions ?? [])
    .slice(0, 3);

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 pt-16 lg:pt-8">
          <button
            onClick={() => router.push("/chat")}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to chat
          </button>

          <div className="flex items-center gap-2 mb-1">
            <GraduationCap className="h-6 w-6 text-neutral-700 dark:text-neutral-300" />
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">Tutor mode</h1>
          </div>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
            Learn by answering. Your tutor asks questions from your own notes, gives hints step by step, and checks you
            understood. Stuck? Tap <span className="font-medium">Just tell me</span> any time, no questions asked.
          </p>

          <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-5 space-y-5">
            <div>
              <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                What do you want to learn?
              </label>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                maxLength={200}
                placeholder="e.g. how photosynthesis works"
                className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
              />
              {suggestions.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => setTopic(s.slice(0, 200))}
                      className="text-[11px] rounded-full bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 px-2.5 py-1 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-left"
                    >
                      {s.length > 70 ? s.slice(0, 70) + "…" : s}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Learn from</p>
              {workspaceId ? (
                <p className="text-sm text-neutral-700 dark:text-neutral-300">
                  All documents in the chosen workspace.{" "}
                  <button className="underline text-xs" onClick={() => setWorkspaceId(null)}>
                    Choose documents instead
                  </button>
                </p>
              ) : readyDocs.length === 0 ? (
                <p className="text-xs text-neutral-400">No ready documents yet. Upload one first.</p>
              ) : (
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {readyDocs.map((doc) => (
                    <label key={doc.id} className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 cursor-pointer">
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
              )}
            </div>

            <div>
              <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Level</p>
              <div className="flex flex-wrap gap-1.5">
                {LEVELS.map((l) => {
                  const locked = allowedLevels !== null && !allowedLevels.includes(l.value);
                  return (
                    <button
                      key={l.value}
                      onClick={() => !locked && setLevel(l.value)}
                      disabled={locked}
                      title={locked ? "Available on paid plans" : l.hint}
                      className={pill(level === l.value, locked)}
                    >
                      {locked && <Lock className="h-3 w-3" />}
                      {l.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Language</p>
              <div className="flex flex-wrap gap-1.5">
                {LANGUAGES.map((l) => {
                  const locked = allowedLanguages !== null && !allowedLanguages.includes(l.value);
                  return (
                    <button
                      key={l.value}
                      onClick={() => !locked && setLanguage(l.value)}
                      disabled={locked}
                      title={locked ? "Available on paid plans" : undefined}
                      className={pill(language === l.value, locked)}
                    >
                      {locked && <Lock className="h-3 w-3" />}
                      {l.label}
                    </button>
                  );
                })}
              </div>
              {(allowedLevels !== null && allowedLevels.length < 3) || (allowedLanguages !== null && allowedLanguages.length < 3) ? (
                <p className="text-[11px] text-neutral-400 mt-1.5">
                  Locked options are on paid plans.{" "}
                  <Link href="/upgrade" className="underline hover:text-neutral-600 dark:hover:text-neutral-300">
                    See plans
                  </Link>
                </p>
              ) : null}
            </div>

            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}

            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] text-neutral-400">
                {weeklyLeft !== null && weeklyLimit !== null
                  ? `${weeklyLeft} of ${weeklyLimit} sessions left this week${
                      weeklyLeft === 0 && weekly?.resets_in_human ? ` · resets in ${weekly.resets_in_human}` : ""
                    }`
                  : ""}
              </p>
              <button
                onClick={start}
                disabled={loading}
                className="shrink-0 flex items-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-4 py-2 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-60"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                {loading ? "Preparing your lesson…" : "Start session"}
              </button>
            </div>
          </div>

          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mt-10 mb-3">Past sessions</h2>
          {sessions.length === 0 ? (
            <p className="text-xs text-neutral-400">No sessions yet.</p>
          ) : (
            <div className="space-y-2">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-3 rounded-xl border border-neutral-200 dark:border-neutral-800 px-4 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-900/60 transition-colors"
                >
                  <Link href={`/tutor/${s.id}`} className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">{s.topic}</p>
                    <p className="text-xs text-neutral-400">
                      {STATUS_LABEL[s.status]} · {s.mastered_count} of {s.total_concepts} mastered ·{" "}
                      {new Date(s.created_at).toLocaleDateString()}
                    </p>
                  </Link>
                  <button
                    onClick={() => remove(s)}
                    disabled={deletingId === s.id}
                    aria-label="Delete session"
                    className="text-neutral-400 hover:text-red-600 dark:hover:text-red-400 p-1 shrink-0"
                  >
                    {deletingId === s.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}

export default function TutorPage() {
  // useSearchParams needs a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <TutorStart />
    </Suspense>
  );
}
