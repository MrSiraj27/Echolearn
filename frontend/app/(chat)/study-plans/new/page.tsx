"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { PreviewStudyPlanResponse, SessionPreview, StudySessionType } from "@/lib/types";

const MINUTE_PRESETS = [30, 60, 90];

const SESSION_TYPE_STYLE: Record<StudySessionType, string> = {
  learn: "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-900",
  review:
    "bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-900",
  quiz: "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-900",
  checkpoint:
    "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900",
};

function groupByDate(sessions: SessionPreview[]) {
  const groups = new Map<string, SessionPreview[]>();
  for (const s of sessions) {
    if (!groups.has(s.scheduled_date)) groups.set(s.scheduled_date, []);
    groups.get(s.scheduled_date)!.push(s);
  }
  return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
}

export default function NewStudyPlanPage() {
  const router = useRouter();
  const { documents, workspaces, loadDocuments, loadWorkspaces } = useChatStore();

  const [step, setStep] = useState<"form" | "preview">("form");
  const [title, setTitle] = useState("");
  const [examDate, setExamDate] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(60);
  const [customMinutes, setCustomMinutes] = useState("");
  const [scopeType, setScopeType] = useState<"documents" | "workspace">("documents");
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewStudyPlanResponse | null>(null);
  const [selectedTopics, setSelectedTopics] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadDocuments();
    loadWorkspaces();
  }, [loadDocuments, loadWorkspaces]);

  const readyDocuments = useMemo(() => documents.filter((d) => d.status === "ready"), [documents]);

  function toggleDoc(id: string) {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handlePreview() {
    setError(null);
    if (!title.trim() || !examDate) {
      setError("Give the plan a title and an exam date.");
      return;
    }
    if (scopeType === "documents" && selectedDocIds.size === 0) {
      setError("Select at least one document.");
      return;
    }
    if (scopeType === "workspace" && !selectedWorkspaceId) {
      setError("Select a workspace.");
      return;
    }

    setSubmitting(true);
    try {
      const data = await api.post<PreviewStudyPlanResponse>(
        "/study-plans/preview",
        {
          title: title.trim(),
          exam_date: examDate,
          daily_study_minutes: dailyMinutes,
          document_ids: scopeType === "documents" ? Array.from(selectedDocIds) : undefined,
          workspace_id: scopeType === "workspace" ? selectedWorkspaceId : undefined,
        },
        { auth: true }
      );
      setPreview(data);
      setSelectedTopics(
        new Set(data.warning ? data.warning.suggested_reduced_topics : data.topics.map((t) => t.title))
      );
      setStep("preview");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't generate a plan preview. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function toggleTopic(title: string) {
    setSelectedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
  }

  async function handleCreate() {
    if (!preview) return;
    setCreating(true);
    setError(null);
    try {
      const reduced =
        selectedTopics.size < preview.topics.length ? Array.from(selectedTopics) : undefined;
      const plan = await api.post<{ id: string }>(
        "/study-plans/",
        {
          plan_token: preview.plan_token,
          document_ids: scopeType === "documents" ? Array.from(selectedDocIds) : undefined,
          workspace_id: scopeType === "workspace" ? selectedWorkspaceId : undefined,
          reduced_topic_titles: reduced,
        },
        { auth: true }
      );
      router.push(`/study-plans/${plan.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't create the study plan. Please try again.");
    } finally {
      setCreating(false);
    }
  }

  const grouped = preview ? groupByDate(preview.sessions) : [];

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => (step === "preview" ? setStep("form") : router.back())}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            {step === "preview" ? "Back to details" : "Back"}
          </button>

          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-2">
            New Study Plan
          </h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-8">
            {step === "form"
              ? "Tell us what you're studying for and we'll build a day-by-day plan."
              : "Here's the proposed plan — review it, then create it."}
          </p>

          {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}

          {step === "form" && (
            <div className="space-y-6">
              <div>
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Title
                </label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Biology Midterm"
                  className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Exam date
                </label>
                <input
                  type="date"
                  value={examDate}
                  onChange={(e) => setExamDate(e.target.value)}
                  min={new Date(Date.now() + 86400000).toISOString().slice(0, 10)}
                  className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Daily study time
                </label>
                <div className="flex items-center gap-2">
                  {MINUTE_PRESETS.map((m) => (
                    <button
                      key={m}
                      onClick={() => {
                        setDailyMinutes(m);
                        setCustomMinutes("");
                      }}
                      className={`text-sm font-medium rounded-lg px-3.5 py-2 border transition-colors ${
                        dailyMinutes === m && !customMinutes
                          ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                          : "border-neutral-300 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                      }`}
                    >
                      {m} min
                    </button>
                  ))}
                  <input
                    value={customMinutes}
                    onChange={(e) => {
                      setCustomMinutes(e.target.value);
                      const n = parseInt(e.target.value, 10);
                      if (!isNaN(n)) setDailyMinutes(n);
                    }}
                    placeholder="Custom"
                    className="w-20 text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2.5 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Study material
                </label>
                <div className="flex gap-2 mb-3">
                  <button
                    onClick={() => setScopeType("documents")}
                    className={`text-xs font-medium rounded-lg px-3 py-1.5 border transition-colors ${
                      scopeType === "documents"
                        ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                        : "border-neutral-300 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                    }`}
                  >
                    Documents
                  </button>
                  <button
                    onClick={() => setScopeType("workspace")}
                    className={`text-xs font-medium rounded-lg px-3 py-1.5 border transition-colors ${
                      scopeType === "workspace"
                        ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                        : "border-neutral-300 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                    }`}
                  >
                    Workspace
                  </button>
                </div>

                {scopeType === "documents" ? (
                  <div className="space-y-1.5 max-h-56 overflow-y-auto">
                    {readyDocuments.length === 0 && (
                      <p className="text-xs text-neutral-400">No ready documents yet.</p>
                    )}
                    {readyDocuments.map((d) => (
                      <label
                        key={d.id}
                        className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 px-2 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800/60 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedDocIds.has(d.id)}
                          onChange={() => toggleDoc(d.id)}
                          className="accent-neutral-900 dark:accent-neutral-100"
                        />
                        <span className="truncate">{d.filename}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <select
                    value={selectedWorkspaceId}
                    onChange={(e) => setSelectedWorkspaceId(e.target.value)}
                    className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-700 dark:text-neutral-300 focus:outline-none"
                  >
                    <option value="">Select a workspace...</option>
                    {workspaces.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <button
                onClick={handlePreview}
                disabled={submitting}
                className="w-full flex items-center justify-center gap-2 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Generate Plan Preview
              </button>
            </div>
          )}

          {step === "preview" && preview && (
            <div className="space-y-6">
              {preview.warning && (
                <div className="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/30 p-4">
                  <p className="text-sm text-amber-800 dark:text-amber-300 mb-3">{preview.warning.warning}</p>
                  <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-2">
                    Uncheck any topics you want to skip (recommended ones are pre-selected):
                  </p>
                  <div className="space-y-1">
                    {preview.topics.map((t) => (
                      <label
                        key={t.title}
                        className="flex items-center gap-2 text-xs text-amber-800 dark:text-amber-300 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedTopics.has(t.title)}
                          onChange={() => toggleTopic(t.title)}
                          className="accent-amber-600"
                        />
                        {t.title}
                        <span className="text-amber-500">({t.estimated_difficulty})</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                  {preview.topics.length} topics identified
                </h2>
                <div className="flex flex-wrap gap-1.5">
                  {preview.topics.map((t) => (
                    <span
                      key={t.title}
                      className={`text-xs rounded-full px-2.5 py-1 border ${
                        selectedTopics.has(t.title)
                          ? "border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300"
                          : "border-neutral-200 dark:border-neutral-800 text-neutral-300 dark:text-neutral-600 line-through"
                      }`}
                    >
                      {t.title}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                  Day-by-day schedule
                </h2>
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                  {grouped.map(([dateStr, sessions]) => (
                    <div key={dateStr} className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
                      <p className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 mb-2">
                        {new Date(dateStr + "T00:00:00").toLocaleDateString(undefined, {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                      <div className="space-y-1.5">
                        {sessions.map((s, i) => (
                          <div
                            key={i}
                            className={`text-xs rounded-lg border px-2.5 py-1.5 ${SESSION_TYPE_STYLE[s.session_type]}`}
                          >
                            <span className="font-medium capitalize">{s.session_type}</span>
                            {" — "}
                            {s.topic_title}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={handleCreate}
                disabled={creating}
                className="w-full flex items-center justify-center gap-2 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
              >
                {creating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create Plan
              </button>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
