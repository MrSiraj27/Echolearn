"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, BookOpen, CalendarDays, CloudUpload, GraduationCap, Loader2, MessageSquareMore } from "lucide-react";
import AssistantPanel, { type AssistantTab } from "@/components/dashboard/AssistantPanel";
import ReaderCard, { type Highlight } from "@/components/dashboard/ReaderCard";
import DocumentMenu from "@/components/documents/DocumentMenu";
import { DocTypeIcon, docMeta, isReady, StatusPill } from "@/components/documents/docUi";
import type { ExplanationThread } from "@/components/reader/ExplanationPanel";
import SelectChatScopeModal from "@/components/SelectChatScopeModal";
import { api, ApiError } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";
import { firstName, useMe } from "@/lib/me";
import type { ExplainSelectionResponse, StudyPlanResponse, TodaySessionItem } from "@/lib/types";
import { UPLOAD_ACCEPT, uploadDocument } from "@/lib/upload";

function WelcomeArt() {
  // Drop the designer's illustration at public/illustrations/welcome.png to use it here.
  const [failed, setFailed] = useState(false);
  if (failed)
    return (
      <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-coral-soft text-coral-active sm:h-16 sm:w-16 dark:bg-neutral-900 dark:text-coral" aria-hidden>
        <BookOpen className="h-7 w-7 sm:h-8 sm:w-8" strokeWidth={1.5} />
      </span>
    );
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/illustrations/welcome.png" alt="" onError={() => setFailed(true)} className="h-16 w-auto shrink-0 sm:h-20" />;
}

function QuickAction({
  icon: Icon,
  title,
  subtitle,
  onClick,
  href,
  busy,
}: {
  icon: typeof BookOpen;
  title: string;
  subtitle: string;
  onClick?: () => void;
  href?: string;
  busy?: boolean;
}) {
  const body = (
    <>
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-100 text-neutral-900 dark:bg-neutral-800 dark:text-neutral-50">
        <Icon className="h-5 w-5" strokeWidth={1.7} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] font-medium leading-tight text-neutral-950 dark:text-neutral-50">{title}</span>
        <span className="mt-0.5 block text-[12.5px] leading-snug text-neutral-600 dark:text-neutral-400">{subtitle}</span>
      </span>
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-neutral-200 text-neutral-600 transition-colors group-hover:border-coral group-hover:bg-coral group-hover:text-white dark:border-neutral-700 dark:text-neutral-300">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
      </span>
    </>
  );
  const cls =
    "group flex items-center gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 text-left transition-colors hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700";
  return href ? (
    <Link href={href} className={cls}>{body}</Link>
  ) : (
    <button onClick={onClick} disabled={busy} className={cls}>{body}</button>
  );
}

function StudyPlanCard() {
  const [today, setToday] = useState<TodaySessionItem[] | null>(null);
  const [plans, setPlans] = useState<StudyPlanResponse[]>([]);
  useEffect(() => {
    api.get<TodaySessionItem[]>("/study-plans/today", { auth: true }).then(setToday).catch(() => setToday([]));
    api
      .get<StudyPlanResponse[]>("/study-plans/", { auth: true })
      .then((p) => setPlans(p.filter((x) => x.status === "active")))
      .catch(() => setPlans([]));
  }, []);

  const left = today?.length ?? 0;
  const minutes = plans.filter((p) => today?.some((t) => t.plan_id === p.id)).reduce((a, p) => a + p.daily_study_minutes, 0);
  const done = plans.reduce((a, p) => a + p.completed_count, 0);
  const total = plans.reduce((a, p) => a + p.session_count, 0);
  const pct = total ? Math.round((done / total) * 100) : 0;

  return (
    <section className="rounded-xl border border-neutral-200 bg-white p-4 [grid-area:plan] self-start dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-medium">Today&apos;s study plan</h2>
        <Link href="/study-plans" className="flex items-center gap-1 text-[13px] text-neutral-600 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white">
          View plan <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
      {today === null ? (
        <Loader2 className="mt-4 h-4 w-4 animate-spin text-neutral-400" />
      ) : plans.length === 0 ? (
        <div className="mt-3 flex items-center gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-100 dark:bg-neutral-800"><CalendarDays className="h-[18px] w-[18px]" /></span>
          <p className="text-sm text-neutral-600 dark:text-neutral-300">
            No study plan yet. <Link href="/study-plans/new" className="font-medium text-neutral-900 underline underline-offset-2 dark:text-white">Plan your exam prep</Link>
          </p>
        </div>
      ) : (
        <Link href={today[0] ? `/study-plans/${today[0].plan_id}/sessions/${today[0].session.id}` : "/study-plans"} className="mt-3 flex items-center gap-4 rounded-xl p-1 hover:bg-neutral-50 dark:hover:bg-neutral-800/50">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-100 dark:bg-neutral-800"><CalendarDays className="h-[18px] w-[18px]" /></span>
          <span className="min-w-0 flex-1">
            <span className="block text-[15px] font-medium">{left ? `${left} session${left > 1 ? "s" : ""} left` : "All done for today"}</span>
            <span className="block text-[13px] text-neutral-500">{left ? `~ ${minutes} min` : today.length === 0 ? "Nice work. See you tomorrow." : ""}</span>
            <span className="mt-2 block h-1.5 rounded-full bg-neutral-100 dark:bg-neutral-800" role="progressbar" aria-label="Plan progress" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <span className="block h-1.5 rounded-full bg-coral" style={{ width: `${Math.max(pct, 2)}%` }} />
            </span>
          </span>
        </Link>
      )}
    </section>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const me = useMe();
  const documents = useChatStore((s) => s.documents);
  const documentsLoaded = useChatStore((s) => s.documentsLoaded);
  const folders = useChatStore((s) => s.folders);
  const createChat = useChatStore((s) => s.createChat);
  const fileRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [startingChat, setStartingChat] = useState(false);

  const [pickedId, setPickedId] = useState<string | null>(null);
  const selected = useMemo(
    () => documents.find((d) => d.id === pickedId && isReady(d)) ?? documents.find(isReady) ?? null,
    [documents, pickedId]
  );
  const [pageNumber, setPageNumber] = useState(1);
  const [tab, setTab] = useState<AssistantTab>("ask");
  const [chatId, setChatId] = useState<string | null>(null);
  const [thread, setThread] = useState<ExplanationThread | null>(null);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const seq = useRef(0);

  // A different document starts a fresh reader position, chat and explanation.
  const [shownId, setShownId] = useState<string | null>(null);
  if ((selected?.id ?? null) !== shownId) {
    setShownId(selected?.id ?? null);
    setPageNumber(1);
    setChatId(null);
    setThread(null);
    setHighlight(null);
    setTab("ask");
  }

  async function onFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadDocument(file);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function chatAbout(ids: string[], title?: string) {
    setStartingChat(true);
    try {
      router.push(`/chat/${await createChat(ids, title)}`);
    } finally {
      setStartingChat(false);
    }
  }

  const explain = useCallback(
    async (text: string, page: number) => {
      if (!selected) return;
      const mine = ++seq.current;
      setTab("explain");
      setHighlight({ pageNumber: page, text });
      setThread({ selectedText: text, pageNumber: page, loading: true, error: null, result: null, followUps: [] });
      try {
        const result = await api.post<ExplainSelectionResponse>(`/documents/${selected.id}/explain`, { text, page_number: page }, { auth: true });
        if (mine === seq.current) setThread((t) => (t ? { ...t, loading: false, result } : t));
      } catch (err) {
        if (mine === seq.current)
          setThread((t) => (t ? { ...t, loading: false, error: err instanceof ApiError ? err.detail : "Couldn't reach the server. Please try again." } : t));
      }
    },
    [selected]
  );

  async function followUp(question: string) {
    if (!selected || !thread?.result) return;
    const mine = seq.current;
    const i = thread.followUps.length;
    const previous = [thread.result.simple_explanation, ...thread.result.key_points].filter(Boolean).join("\n");
    setThread((t) => (t ? { ...t, followUps: [...t.followUps, { question, answer: null, loading: true, error: null }] } : t));
    const patch = (p: Partial<ExplanationThread["followUps"][number]>) =>
      setThread((t) => (t && mine === seq.current ? { ...t, followUps: t.followUps.map((f, j) => (j === i ? { ...f, ...p } : f)) } : t));
    try {
      const res = await api.post<ExplainSelectionResponse>(
        `/documents/${selected.id}/explain`,
        { text: thread.selectedText, page_number: thread.pageNumber, question, previous_explanation: previous },
        { auth: true }
      );
      patch({ loading: false, answer: res.answer });
    } catch (err) {
      patch({ loading: false, error: err instanceof ApiError ? err.detail : "Couldn't get an answer." });
    }
  }

  const recent = documents.slice(0, 5);

  return (
    <main className="min-w-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[1600px] space-y-5 px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
        {/* Welcome */}
        <section className="flex items-center gap-4 sm:gap-5">
          <WelcomeArt />
          <div className="min-w-0 flex-1">
            <h1 className="font-serif text-[26px] leading-tight tracking-[-0.02em] text-neutral-950 sm:text-[32px] dark:text-neutral-50">Welcome back, {firstName(me?.name)}</h1>
            <p className="mt-1 text-[14px] text-neutral-600 sm:text-[15px] dark:text-neutral-400">Your personal AI study assistant is here to help you learn better.</p>
          </div>
          <p className="ml-auto hidden max-w-[15rem] text-right font-serif text-[16px] italic leading-snug text-neutral-600 2xl:block dark:text-neutral-400">
            “Small steps every day lead to big results.”
          </p>
        </section>

        {/* Quick actions */}
        <section className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4" aria-label="Quick actions">
          <QuickAction icon={CloudUpload} title="Upload Documents" subtitle={uploading ? "Uploading…" : "Add your study material"} busy={uploading} onClick={() => fileRef.current?.click()} />
          <QuickAction icon={MessageSquareMore} title="Start AI Chat" subtitle="Ask questions" busy={startingChat} onClick={() => setScopeOpen(true)} />
          <QuickAction icon={BookOpen} title="Open Reader" subtitle="Read and highlight" href={selected ? `/read/${selected.id}` : "/read"} />
          <QuickAction icon={GraduationCap} title="Start Tutor Mode" subtitle="Learn step by step" href="/tutor" />
        </section>
        <input ref={fileRef} type="file" accept={UPLOAD_ACCEPT} className="hidden" onChange={(e) => { void onFiles(e.target.files); e.target.value = ""; }} />
        {uploadError && <p role="alert" className="-mt-2 text-sm text-red-600 dark:text-red-400">{uploadError}</p>}

        {/* Workspace */}
        {/* Phone: stacked. Tablet: documents | plan, then reader, then assistant.
            Laptop (1280px+): documents | plan, then reader | assistant. Wide: the designer's 3 columns. */}
        <section
          className="grid gap-4 [grid-template-areas:'docs'_'plan'_'reader'_'assistant']
            md:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] md:[grid-template-areas:'docs_plan'_'reader_reader'_'assistant_assistant']
            xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,1fr)] xl:[grid-template-areas:'docs_plan'_'reader_assistant']
            2xl:grid-cols-[minmax(300px,0.9fr)_minmax(0,1.65fr)_minmax(340px,1fr)] 2xl:grid-rows-[auto_1fr] 2xl:[grid-template-areas:'docs_reader_assistant'_'plan_reader_assistant']"
        >
            <section className="min-w-0 rounded-xl border border-neutral-200 bg-white p-4 [grid-area:docs] dark:border-neutral-800 dark:bg-neutral-900">
              <div className="mb-1 flex items-center justify-between">
                <h2 className="text-[15px] font-medium">My documents</h2>
                <Link href="/documents" className="flex items-center gap-1 text-[13px] text-neutral-600 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white">
                  View all <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
              {!documentsLoaded ? (
                <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-neutral-400" aria-label="Loading documents" /></div>
              ) : recent.length === 0 ? (
                <button onClick={() => fileRef.current?.click()} className="mt-2 w-full rounded-xl border border-dashed border-neutral-300 p-6 text-center text-sm text-neutral-600 hover:border-neutral-500 dark:border-neutral-700 dark:text-neutral-300">
                  Upload your first document: PDF, Word, slides, images, audio or video.
                </button>
              ) : (
                <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
                  {recent.map((d) => {
                    const active = selected?.id === d.id;
                    return (
                      <li key={d.id} className="flex items-center gap-2 py-2">
                        <button
                          onClick={() => isReady(d) && setPickedId(d.id)}
                          disabled={!isReady(d)}
                          className={`flex min-w-0 flex-1 items-center gap-3 rounded-lg px-1.5 py-1 text-left ${active ? "bg-neutral-100 dark:bg-neutral-800" : "hover:bg-neutral-50 dark:hover:bg-neutral-800/50"} disabled:cursor-default`}
                          aria-pressed={active}
                          title={isReady(d) ? "Show in the reader" : undefined}
                        >
                          <DocTypeIcon fileType={d.file_type} size={32} />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-[13.5px] font-medium" title={d.filename}>{d.filename}</span>
                            <span className="block truncate text-[12px] text-neutral-500">{d.status === "failed" && d.error_message ? d.error_message : docMeta(d)}</span>
                          </span>
                        </button>
                        <StatusPill doc={d} />
                        <DocumentMenu doc={d} />
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
            <StudyPlanCard />

          <ReaderCard
            doc={selected}
            pageNumber={pageNumber}
            onPageChange={setPageNumber}
            highlight={highlight}
            onExplain={explain}
            onChat={() => selected && chatAbout([selected.id], selected.filename)}
            startingChat={startingChat}
          />

          <AssistantPanel
            doc={selected}
            tab={tab}
            onTab={setTab}
            chatId={chatId}
            onChatId={setChatId}
            thread={thread}
            onAskAboutSelection={followUp}
            onRetryExplain={() => thread && explain(thread.selectedText, thread.pageNumber ?? pageNumber)}
            onGoToPage={setPageNumber}
          />
        </section>
      </div>

      {scopeOpen && (
        <SelectChatScopeModal
          documents={documents}
          folders={folders}
          onConfirm={async (ids) => {
            setScopeOpen(false);
            await chatAbout(ids);
          }}
          onClose={() => setScopeOpen(false)}
        />
      )}
    </main>
  );
}
