"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Loader2, Plus, Trash2, Upload, X } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { PATTERN_BADGE, PRACTICE_DISCLAIMER, QUESTION_TYPE_LABELS, uploadPastPaper } from "@/lib/practice";
import {
  PaperSectionConfig,
  PastPaperItem,
  PastPaperStatus,
  PracticePaperStatusResponse,
  PreviewPatternResponse,
  PracticeQuestionType,
  WorkspaceDetail,
} from "@/lib/types";

type Step = 1 | 2 | 3 | 4;
const STEP_TITLES: Record<Step, string> = {
  1: "Choose your material",
  2: "Past papers (optional)",
  3: "Important topics (optional)",
  4: "Review the structure",
};
const MAX_SECTIONS = 8;
const MAX_TOPICS = 10;

const inputCls =
  "text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100";
const primaryBtn =
  "flex items-center justify-center gap-2 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-5 py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50";
const secondaryBtn =
  "flex items-center justify-center gap-2 text-sm font-medium border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 rounded-lg px-5 py-2.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50";

function toggled<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

export default function NewPracticePaperPage() {
  const router = useRouter();
  const { documents, workspaces, loadDocuments, loadWorkspaces } = useChatStore();

  const [step, setStep] = useState<Step>(1);
  const [error, setError] = useState<string | null>(null);

  // Step 1
  const [title, setTitle] = useState("");
  const [scopeType, setScopeType] = useState<"documents" | "workspace">("documents");
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [resolvingScope, setResolvingScope] = useState(false);
  const [resolvedDocIds, setResolvedDocIds] = useState<string[]>([]);

  // Step 2
  const [pastPapers, setPastPapers] = useState<PastPaperItem[]>([]);
  const [selectedPastIds, setSelectedPastIds] = useState<Set<string>>(new Set());
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Step 3
  const [topics, setTopics] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState("");

  // Step 4
  const [preview, setPreview] = useState<PreviewPatternResponse | null>(null);
  const [sections, setSections] = useState<PaperSectionConfig[]>([]);
  const [edited, setEdited] = useState(false);
  const [timeInput, setTimeInput] = useState("");
  const [timeEdited, setTimeEdited] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    loadDocuments();
    loadWorkspaces();
    api
      .get<PastPaperItem[]>("/past-papers/", { auth: true })
      .then(setPastPapers)
      .catch(() => setPastPapers([]));
    return () => {
      cancelledRef.current = true;
    };
  }, [loadDocuments, loadWorkspaces]);

  // Past papers are stored as documents too; they only teach the structure, so hide them
  // from the "study material" picker.
  const pastPaperDocIds = useMemo(() => new Set(pastPapers.map((p) => p.document_id)), [pastPapers]);
  const readyDocuments = useMemo(
    () => documents.filter((d) => (d.status === "ready" || d.status === "embedded") && !pastPaperDocIds.has(d.id)),
    [documents, pastPaperDocIds]
  );

  // Live analysis polling while any past paper is still being analysed.
  const anyAnalysing = pastPapers.some((p) => p.analysis_status === "pending" || p.analysis_status === "analyzing");
  useEffect(() => {
    if (!anyAnalysing) return;
    const timer = setInterval(async () => {
      const inFlight = pastPapers.filter((p) => p.analysis_status === "pending" || p.analysis_status === "analyzing");
      const updates = await Promise.all(
        inFlight.map((p) => api.get<PastPaperStatus>(`/past-papers/${p.id}/status`, { auth: true }).catch(() => null))
      );
      setPastPapers((prev) =>
        prev.map((p) => {
          const u = updates.find((x) => x && x.id === p.id);
          return u
            ? {
                ...p,
                analysis_status: u.analysis_status,
                error_message: u.error_message,
                extracted_pattern: u.extracted_pattern,
                pattern_summary: u.pattern_summary,
              }
            : p;
        })
      );
    }, 2500);
    return () => clearInterval(timer);
  }, [anyAnalysing, pastPapers]);

  const readyPastPapers = pastPapers.filter((p) => p.analysis_status === "ready");
  const chosenPast = readyPastPapers.filter((p) => selectedPastIds.has(p.id));

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const created = await uploadPastPaper(file);
        setPastPapers((prev) => [created, ...prev]);
        setSelectedPastIds((prev) => new Set(prev).add(created.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function removePastPaper(id: string) {
    try {
      await api.delete(`/past-papers/${id}`, { auth: true });
      setPastPapers((prev) => prev.filter((p) => p.id !== id));
      setSelectedPastIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't remove that past paper.");
    }
  }

  async function goFromStep1() {
    setError(null);
    if (!title.trim()) return setError("Give the paper a title.");
    if (scopeType === "documents") {
      if (selectedDocIds.size === 0) return setError("Select at least one document.");
      setResolvedDocIds(Array.from(selectedDocIds));
      return setStep(2);
    }
    if (!selectedWorkspaceId) return setError("Select a workspace.");
    setResolvingScope(true);
    try {
      const ws = await api.get<WorkspaceDetail>(`/workspaces/${selectedWorkspaceId}`, { auth: true });
      const ids = ws.document_ids.filter((id) => !pastPaperDocIds.has(id));
      if (ids.length === 0) return setError("That workspace has no documents to build a paper from.");
      setResolvedDocIds(ids);
      setStep(2);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't load that workspace.");
    } finally {
      setResolvingScope(false);
    }
  }

  function addTopic() {
    const parts = topicInput
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length >= 2);
    if (parts.length === 0) return;
    setTopics((prev) => {
      const next = [...prev];
      for (const t of parts) {
        if (next.length < MAX_TOPICS && !next.some((x) => x.toLowerCase() === t.toLowerCase()))
          next.push(t.slice(0, 80));
      }
      return next;
    });
    setTopicInput("");
  }

  const loadPreview = useCallback(async (pastIds: string[]) => {
    setPreviewing(true);
    setError(null);
    try {
      const data = await api.post<PreviewPatternResponse>(
        "/practice-papers/preview-pattern",
        { based_on_past_paper_ids: pastIds.length ? pastIds : undefined },
        { auth: true }
      );
      setPreview(data);
      setSections(data.pattern_config.sections);
      setEdited(false);
      setTimeInput(String(data.estimated_time_minutes));
      setTimeEdited(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't work out the paper structure. Please try again.");
    } finally {
      setPreviewing(false);
    }
  }, []);

  async function goToStep4() {
    setError(null);
    setStep(4);
    await loadPreview(chosenPast.map((p) => p.id));
  }

  function updateSection(i: number, patch: Partial<PaperSectionConfig>) {
    setSections((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
    setEdited(true);
  }

  const totalQuestions = sections.reduce((n, s) => n + (Number(s.count) || 0), 0);
  const totalMarks = sections.reduce((n, s) => n + (Number(s.count) || 0) * (Number(s.marks_each) || 0), 0);

  function validateSections(): string | null {
    if (sections.length === 0) return "Add at least one section.";
    for (const s of sections) {
      if (!s.name.trim()) return "Every section needs a name.";
      if (!Number.isInteger(Number(s.count)) || s.count < 1 || s.count > 40)
        return "Each section needs between 1 and 40 questions.";
      if (!(Number(s.marks_each) > 0) || s.marks_each > 100) return "Marks per question must be above 0 (max 100).";
    }
    if (totalQuestions > 80) return "A paper can have at most 80 questions in total.";
    return null;
  }

  async function handleGenerate() {
    if (!preview) return;
    const problem = validateSections();
    if (problem) return setError(problem);
    const minutes = timeEdited ? parseInt(timeInput, 10) : NaN;
    if (timeEdited && (isNaN(minutes) || minutes < 5 || minutes > 600))
      return setError("Time allowed must be between 5 and 600 minutes.");

    setError(null);
    setGenerating(true);
    try {
      const started = await api.post<{ id: string; status: string }>(
        "/practice-papers/generate",
        {
          title: title.trim(),
          document_ids: resolvedDocIds,
          based_on_past_paper_ids: chosenPast.length ? chosenPast.map((p) => p.id) : undefined,
          important_topics: topics.length ? topics : undefined,
          custom_pattern_override: edited
            ? {
                sections: sections.map((s) => ({
                  ...s,
                  name: s.name.trim(),
                  count: Number(s.count),
                  marks_each: Number(s.marks_each),
                })),
              }
            : undefined,
          time_allowed_minutes: timeEdited ? minutes : undefined,
        },
        { auth: true }
      );

      // Honest, indeterminate wait: we don't know how long it takes, so we don't fake a percentage.
      for (;;) {
        await new Promise((r) => setTimeout(r, 3000));
        if (cancelledRef.current) return;
        const st = await api
          .get<PracticePaperStatusResponse>(`/practice-papers/${started.id}/status`, { auth: true })
          .catch(() => null);
        if (!st) continue;
        if (st.status === "ready") return router.push(`/practice-papers/${started.id}`);
        if (st.status === "failed") {
          setError(st.error_message || "The paper couldn't be generated. Please try again.");
          break;
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't start generating the paper. Please try again.");
    }
    setGenerating(false);
  }

  const badge = edited ? PATTERN_BADGE.custom : preview ? (preview.pattern_source === "past_papers" ? preview.pattern_note : PATTERN_BADGE[preview.pattern_source]) : "";

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => (step > 1 && !generating ? setStep((step - 1) as Step) : router.back())}
            disabled={generating}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6 disabled:opacity-40"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
            New Practice Paper
          </h1>
          <p className="text-xs text-neutral-400 mb-1">
            Step {step} of 4 · {STEP_TITLES[step]}
          </p>
          <div className="flex gap-1 mb-6">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className={`h-1 flex-1 rounded-full ${n <= step ? "bg-neutral-900 dark:bg-neutral-100" : "bg-neutral-200 dark:bg-neutral-800"}`}
              />
            ))}
          </div>

          <p className="text-xs text-neutral-500 dark:text-neutral-400 rounded-lg bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 px-3 py-2 mb-6">
            {PRACTICE_DISCLAIMER}
          </p>

          {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}

          {step === 1 && (
            <div className="space-y-6">
              <div>
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">Title</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Biology Midterm Practice"
                  maxLength={150}
                  className={`w-full ${inputCls}`}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5 block">
                  Study material
                </label>
                <div className="flex gap-2 mb-3">
                  {(["documents", "workspace"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setScopeType(t)}
                      className={`text-xs font-medium rounded-lg px-3 py-1.5 border transition-colors ${
                        scopeType === t
                          ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                          : "border-neutral-300 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                      }`}
                    >
                      {t === "documents" ? "Documents" : "Workspace"}
                    </button>
                  ))}
                </div>
                {scopeType === "documents" ? (
                  <div className="space-y-1.5 max-h-64 overflow-y-auto">
                    {readyDocuments.length === 0 && <p className="text-xs text-neutral-400">No ready documents yet.</p>}
                    {readyDocuments.map((d) => (
                      <label
                        key={d.id}
                        className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 px-2 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800/60 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedDocIds.has(d.id)}
                          onChange={() => setSelectedDocIds((prev) => toggled(prev, d.id))}
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
                    className={`w-full ${inputCls}`}
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
              <div className="flex justify-end">
                <button onClick={goFromStep1} disabled={resolvingScope} className={primaryBtn}>
                  {resolvingScope && <Loader2 className="h-4 w-4 animate-spin" />}
                  Next
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                Upload past papers so we can copy their <em>layout</em> (sections, question types, counts and marks).
                Their questions are never reused. Skip this to use a standard practice format.
              </p>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => handleUpload(e.target.files)}
              />
              <button onClick={() => fileRef.current?.click()} disabled={uploading} className={secondaryBtn}>
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Upload past paper
              </button>

              {pastPapers.length > 0 && (
                <div className="space-y-2">
                  {pastPapers.map((p) => {
                    const busy = p.analysis_status === "pending" || p.analysis_status === "analyzing";
                    const pat = p.extracted_pattern;
                    return (
                      <div key={p.id} className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            disabled={p.analysis_status !== "ready"}
                            checked={selectedPastIds.has(p.id)}
                            onChange={() => setSelectedPastIds((prev) => toggled(prev, p.id))}
                            className="accent-neutral-900 dark:accent-neutral-100"
                            aria-label={`Use ${p.filename}`}
                          />
                          <span className="text-sm text-neutral-800 dark:text-neutral-200 truncate flex-1">
                            {p.filename}
                          </span>
                          {busy && (
                            <span className="flex items-center gap-1 text-xs text-neutral-500">
                              <Loader2 className="h-3 w-3 animate-spin" />
                              {p.analysis_status === "pending" ? "Reading file..." : "Analysing structure..."}
                            </span>
                          )}
                          {p.analysis_status === "ready" && (
                            <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                              <Check className="h-3 w-3" />
                              Analysed
                            </span>
                          )}
                          <button
                            onClick={() => removePastPaper(p.id)}
                            aria-label={`Remove ${p.filename}`}
                            className="text-neutral-400 hover:text-red-600 dark:hover:text-red-400"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        {p.analysis_status === "ready" && pat && (
                          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1.5 ml-6">
                            {pat.sections.length} section{pat.sections.length !== 1 ? "s" : ""}, {pat.total_questions}{" "}
                            questions, {pat.total_marks} marks
                          </p>
                        )}
                        {p.analysis_status === "failed" && (
                          <p className="text-xs text-red-600 dark:text-red-400 mt-1.5 ml-6">
                            {p.error_message || "Analysis failed."}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {chosenPast.length > 0 && (
                <div className="rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 p-3">
                  <p className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 mb-0.5">What we detected</p>
                  <p className="text-sm text-neutral-800 dark:text-neutral-200">
                    {chosenPast.length === 1
                      ? chosenPast[0].pattern_summary
                      : `${chosenPast.length} past papers selected. The merged structure (with how consistent they are) is shown in the last step.`}
                  </p>
                </div>
              )}

              <div className="flex justify-between">
                <button onClick={() => setStep(1)} className={secondaryBtn}>
                  Back
                </button>
                <button onClick={() => setStep(3)} disabled={anyAnalysing || uploading} className={primaryBtn}>
                  {anyAnalysing && <Loader2 className="h-4 w-4 animate-spin" />}
                  {chosenPast.length === 0 && !anyAnalysing ? "Skip" : "Next"}
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-5">
              <p className="text-sm text-neutral-500 dark:text-neutral-400">
                Add topics you want covered more. We give them extra weight where your material mentions them.
                Separate several with commas.
              </p>
              <div className="flex gap-2">
                <input
                  value={topicInput}
                  onChange={(e) => setTopicInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addTopic();
                    }
                  }}
                  placeholder="e.g. photosynthesis, cell division"
                  className={`flex-1 ${inputCls}`}
                />
                <button onClick={addTopic} className={secondaryBtn} aria-label="Add topic">
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              {topics.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {topics.map((t) => (
                    <span
                      key={t}
                      className="flex items-center gap-1 text-xs rounded-full px-2.5 py-1 border border-neutral-300 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300"
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
              )}
              {chosenPast.some((p) => (p.extracted_pattern?.recurring_topics_mentioned.length ?? 0) > 0) && (
                <p className="text-xs text-neutral-400">
                  Topics mentioned in your past papers are also given extra weight automatically.
                </p>
              )}
              <div className="flex justify-between">
                <button onClick={() => setStep(2)} className={secondaryBtn}>
                  Back
                </button>
                <button onClick={goToStep4} className={primaryBtn}>
                  {topics.length === 0 ? "Skip" : "Next"}
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-5">
              {previewing && (
                <p className="flex items-center gap-2 text-sm text-neutral-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Working out the structure...
                </p>
              )}

              {preview && !generating && (
                <>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium rounded-full px-2.5 py-1 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900">
                      {badge}
                    </span>
                    {!edited && preview.past_paper_summary && (
                      <span className="text-xs text-neutral-500 dark:text-neutral-400">
                        {preview.past_paper_summary}
                      </span>
                    )}
                  </div>
                  {!edited && preview.section_confidence && preview.section_confidence.length > 0 && (
                    <ul className="text-xs text-neutral-400 space-y-0.5 list-disc pl-4">
                      {Array.from(new Set(preview.section_confidence)).map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  )}

                  <div className="space-y-2">
                    <div className="hidden sm:grid grid-cols-[1fr_9rem_4rem_4.5rem_2rem] gap-2 text-[11px] font-medium text-neutral-400 px-1">
                      <span>Section</span>
                      <span>Type</span>
                      <span>Count</span>
                      <span>Marks each</span>
                      <span />
                    </div>
                    {sections.map((s, i) => (
                      <div
                        key={i}
                        className="grid grid-cols-2 sm:grid-cols-[1fr_9rem_4rem_4.5rem_2rem] gap-2 items-center"
                      >
                        <input
                          value={s.name}
                          onChange={(e) => updateSection(i, { name: e.target.value })}
                          aria-label="Section name"
                          className={`col-span-2 sm:col-span-1 ${inputCls}`}
                        />
                        <select
                          value={s.question_type}
                          onChange={(e) => updateSection(i, { question_type: e.target.value as PracticeQuestionType })}
                          aria-label="Question type"
                          className={inputCls}
                        >
                          {Object.entries(QUESTION_TYPE_LABELS).map(([v, label]) => (
                            <option key={v} value={v}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <input
                          type="number"
                          min={1}
                          max={40}
                          value={s.count}
                          onChange={(e) => updateSection(i, { count: parseInt(e.target.value, 10) || 0 })}
                          aria-label="Number of questions"
                          className={inputCls}
                        />
                        <input
                          type="number"
                          min={0.5}
                          step={0.5}
                          value={s.marks_each}
                          onChange={(e) => updateSection(i, { marks_each: parseFloat(e.target.value) || 0 })}
                          aria-label="Marks each"
                          className={inputCls}
                        />
                        <button
                          onClick={() => {
                            setSections((prev) => prev.filter((_, idx) => idx !== i));
                            setEdited(true);
                          }}
                          disabled={sections.length <= 1}
                          aria-label="Remove section"
                          className="text-neutral-400 hover:text-red-600 dark:hover:text-red-400 disabled:opacity-30 justify-self-end"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                    {sections.length < MAX_SECTIONS && (
                      <button
                        onClick={() => {
                          setSections((prev) => [
                            ...prev,
                            {
                              name: `Section ${String.fromCharCode(65 + prev.length)}`,
                              question_type: "short_answer",
                              count: 3,
                              marks_each: 3,
                            },
                          ]);
                          setEdited(true);
                        }}
                        className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                      >
                        <Plus className="h-3.5 w-3.5" /> Add section
                      </button>
                    )}
                  </div>

                  <div className="flex items-center justify-between gap-4 flex-wrap rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
                    <p className="text-sm text-neutral-700 dark:text-neutral-300">
                      <span className="font-semibold">{totalQuestions}</span> questions ·{" "}
                      <span className="font-semibold">{Math.round(totalMarks * 100) / 100}</span> marks
                    </p>
                    <label className="flex items-center gap-2 text-xs text-neutral-500">
                      Time allowed
                      <input
                        type="number"
                        min={5}
                        max={600}
                        value={timeInput}
                        onChange={(e) => {
                          setTimeInput(e.target.value);
                          setTimeEdited(true);
                        }}
                        className={`w-20 ${inputCls}`}
                      />
                      min
                    </label>
                  </div>
                  {!timeEdited && (
                    <p className="text-xs text-neutral-400">
                      Suggested time is an estimate from the structure - change it if your exam differs.
                    </p>
                  )}
                  {topics.length > 0 && <p className="text-xs text-neutral-500">Extra focus on: {topics.join(", ")}</p>}

                  <div className="flex justify-between">
                    <button onClick={() => setStep(3)} className={secondaryBtn}>
                      Back
                    </button>
                    <button onClick={handleGenerate} className={primaryBtn}>
                      Generate Practice Paper
                    </button>
                  </div>
                </>
              )}

              {generating && (
                <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-8 text-center">
                  <Loader2 className="h-6 w-6 animate-spin text-neutral-500 mx-auto mb-3" />
                  <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">
                    Writing and checking your practice paper...
                  </p>
                  <p className="text-xs text-neutral-400 mt-1">
                    Every question is checked against your material, so this can take a minute or two. You can leave
                    this page - the paper will appear under Practice Papers when it&apos;s done.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
