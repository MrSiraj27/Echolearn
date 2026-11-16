"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";
import {
  BookOpen,
  Bot,
  CalendarDays,
  ChartColumnIncreasing,
  CircleCheck,
  CloudUpload,
  EllipsisVertical,
  FileText,
  Files,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  Pause,
  Search,
  SendHorizontal,
  Settings,
  Volume2,
} from "lucide-react";

/*
 * The hero's dashboard picture, playing a silent looping "product video": a cursor uploads a PDF,
 * asks a question, the answer streams in with its page, the answer is read aloud, and a quiz is
 * made. Everything is driven by one clock (t, in ms within LOOP) so the scenes always line up.
 * The clock pauses while the demo is off screen or the tab is hidden; with "reduce motion" the
 * demo shows one still frame.
 */

const LOOP = 19000;
const QUESTION = "Explain photosynthesis simply";
const ANSWER =
  "Photosynthesis is how plants use sunlight to turn water and carbon dioxide into glucose and oxygen.";
const STILL_FRAME = 13000; // shown when the visitor prefers reduced motion

// scene timings (ms)
const T = {
  upload: 1500, // click "Upload Documents"
  uploadStart: 1800,
  uploadDone: 4300,
  ready: 5100,
  typeStart: 6000,
  typeEnd: 7900,
  send: 8150,
  answerStart: 8700,
  answerEnd: 11300,
  listen: 12000, // click "Listen"
  listenEnd: 15400,
  quiz: 16200, // click "Start Quiz"
  quizToastEnd: 18200,
};

type Target = "rest" | "upload" | "input" | "listen" | "quiz";
const MOVES: [number, Target][] = [
  [0, "rest"],
  [700, "upload"],
  [5200, "input"],
  [11500, "listen"],
  [15600, "quiz"],
  [18300, "rest"],
];
const CLICKS = [T.upload, T.send - 150, T.listen, T.quiz];

const prog = (t: number, a: number, b: number) => Math.min(1, Math.max(0, (t - a) / (b - a)));

/** Centre of `el` in `root`'s own (untransformed) layout coordinates, so it works inside the tilt. */
function centreWithin(el: HTMLElement, root: HTMLElement) {
  let x = el.offsetWidth / 2;
  let y = el.offsetHeight / 2;
  let n: HTMLElement | null = el;
  while (n && n !== root) {
    x += n.offsetLeft;
    y += n.offsetTop;
    n = n.offsetParent as HTMLElement | null;
  }
  return { x, y };
}

function useLoopClock(running: boolean) {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!running) return;
    let last = performance.now();
    const id = setInterval(() => {
      const now = performance.now();
      const dt = Math.min(now - last, 100); // no jump after the tab was in the background
      last = now;
      setT((x) => (x + dt) % LOOP);
    }, 40);
    return () => clearInterval(id);
  }, [running]);
  return t;
}

const SIDE = [
  { icon: LayoutDashboard, label: "Dashboard" },
  { icon: Files, label: "My Documents" },
  { icon: Bot, label: "AI Assistant" },
  { icon: GraduationCap, label: "Tutor Mode" },
  { icon: ListChecks, label: "Quizzes" },
  { icon: CalendarDays, label: "Study Plans" },
  { icon: ChartColumnIncreasing, label: "Analytics" },
  { icon: Settings, label: "Settings" },
];
const DOCS = [
  { name: "Mathematics Notes.pdf", meta: "2.4 MB · Apr 12" },
  { name: "Physics Chapter 1.docx", meta: "1.8 MB · Apr 10" },
  { name: "Chemistry Slides.pptx", meta: "3.1 MB · Apr 8" },
];

export function HeroDemo() {
  const reduce = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(true);
  const [pageVisible, setPageVisible] = useState(true);
  const [spots, setSpots] = useState<Partial<Record<Target, { x: number; y: number }>>>({});

  const clock = useLoopClock(inView && pageVisible && !reduce);
  const t = reduce ? STILL_FRAME : clock;

  // pause when scrolled away or the tab is hidden
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { threshold: 0.1 });
    io.observe(root);
    const onVis = () => setPageVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  // where the cursor should point, re-measured whenever the card changes size
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const measure = () => {
      const next: Partial<Record<Target, { x: number; y: number }>> = {
        rest: { x: root.offsetWidth * 0.9, y: root.offsetHeight * 0.92 },
      };
      root.querySelectorAll<HTMLElement>("[data-demo]").forEach((el) => {
        if (el.offsetParent) next[el.dataset.demo as Target] = centreWithin(el, root);
      });
      setSpots((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
    };
    // size changes, plus elements that appear mid-scene (the Listen button)
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    const mo = new MutationObserver(measure);
    mo.observe(root, { childList: true, subtree: true });
    return () => {
      ro.disconnect();
      mo.disconnect();
    };
  }, []);

  // ------------------------------------------------------------ derived scene state
  const target = [...MOVES].reverse().find(([at]) => t >= at)?.[1] ?? "rest";
  const cursor = spots[target] ?? spots.rest;
  const clicking = CLICKS.some((c) => t >= c && t - c < 380);
  const pressed = (c: number) => t >= c && t - c < 350;
  const loopFade = t > 18500 ? 1 - prog(t, 18500, 18950) : t < 250 ? prog(t, 0, 250) : 1;

  const uploadP = prog(t, T.uploadStart, T.uploadDone);
  const showNewDoc = t >= T.uploadStart;
  const newDocStatus = uploadP < 1 ? `Uploading… ${Math.round(uploadP * 100)}%` : t < T.ready ? "Reading pages…" : "Ready · 42 pages";
  const docs = showNewDoc ? [{ name: "Biology Notes.pdf", meta: newDocStatus, fresh: true }, ...DOCS].slice(0, 3) : DOCS;

  const chatMode = t >= T.ready;
  const typed = t < T.send ? QUESTION.slice(0, Math.round(prog(t, T.typeStart, T.typeEnd) * QUESTION.length)) : "";
  const asked = t >= T.send;
  const thinking = t >= T.send && t < T.answerStart;
  const answer = ANSWER.slice(0, Math.round(prog(t, T.answerStart, T.answerEnd) * ANSWER.length));
  const answered = t >= T.answerEnd;
  const playing = t >= T.listen + 150 && t < T.listenEnd;
  const playP = prog(t, T.listen + 150, T.listenEnd);
  const quizToast = t >= T.quiz + 250 && t < T.quizToastEnd;
  const caretOn = t % 900 < 450;

  return (
    <div className="[perspective:1800px]" aria-hidden="true">
      <div
        ref={rootRef}
        className="relative flex overflow-hidden rounded-[22px] border border-neutral-200 bg-neutral-50 shadow-[0_40px_80px_-30px_rgba(24,23,21,0.35)] lg:[transform:rotateY(-14deg)_rotateX(6deg)_rotateZ(1deg)] dark:border-neutral-800 dark:bg-neutral-900"
      >
        {/* sidebar */}
        <div className="hidden w-[150px] shrink-0 bg-neutral-950 px-3 py-4 text-neutral-400 sm:block">
          <div className="mb-4 flex items-center gap-1.5 px-1 text-[12px] font-medium text-neutral-50">
            <BookOpen className="h-4 w-4" /> EchoLearn
          </div>
          {SIDE.map((s) => {
            const active = quizToast ? s.label === "Quizzes" : s.label === "Dashboard";
            return (
              <div
                key={s.label}
                className={`mb-1 flex items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] transition-colors duration-500 ${active ? "bg-neutral-50 text-neutral-950" : ""}`}
              >
                <s.icon className="h-3 w-3" /> {s.label}
              </div>
            );
          })}
        </div>

        {/* main */}
        <div className="relative min-w-0 flex-1 p-4">
          <div className="flex items-center gap-2 rounded-lg border border-neutral-200 px-3 py-1.5 text-[10px] text-neutral-500 dark:border-neutral-800">
            <Search className="h-3 w-3" /> Search documents, ask questions...
            <span className="ml-auto grid h-5 w-5 place-items-center rounded-full bg-neutral-950 text-[9px] font-semibold text-neutral-50 dark:bg-neutral-50 dark:text-neutral-950">
              A
            </span>
          </div>
          <p className="mt-4 text-[15px] font-semibold">Welcome back, Ayesha!</p>
          <p className="text-[10px] text-neutral-500">Continue your learning journey with EchoLearn</p>

          <div className="mt-3 grid grid-cols-3 gap-2">
            {[
              { k: "upload" as const, icon: CloudUpload, t: "Upload Documents", s: "Add your study material", at: T.upload },
              { k: null, icon: Bot, t: "Open AI Assistant", s: "Chat with your docs", at: -1 },
              { k: "quiz" as const, icon: ListChecks, t: "Start Quiz", s: "Test your knowledge", at: T.quiz },
            ].map((c) => (
              <div
                key={c.t}
                data-demo={c.k ?? undefined}
                className={`flex items-start gap-1.5 rounded-lg border p-2 transition duration-200 ${
                  pressed(c.at)
                    ? "scale-95 border-neutral-950 bg-neutral-100 dark:border-neutral-50 dark:bg-neutral-800"
                    : "border-neutral-200 dark:border-neutral-800"
                }`}
              >
                <c.icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div className="min-w-0">
                  <p className="truncate text-[9px] font-semibold">{c.t}</p>
                  <p className="truncate text-[8px] text-neutral-500">{c.s}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 grid grid-cols-[1.15fr_1fr] gap-2">
            {/* documents */}
            <div className="h-[168px] overflow-hidden rounded-lg border border-neutral-200 p-2.5 dark:border-neutral-800">
              <div className="mb-2 flex items-center justify-between text-[10px] font-semibold">
                My Documents <span className="text-[8px] font-medium text-neutral-500">View all →</span>
              </div>
              {docs.map((d) => {
                const fresh = "fresh" in d;
                return (
                  <div
                    key={d.name}
                    className={`py-1.5 ${fresh ? "animate-in fade-in slide-in-from-top-2 duration-500" : ""}`}
                    style={fresh ? { opacity: loopFade } : undefined}
                  >
                    <div className="flex items-center gap-2">
                      {fresh && t >= T.ready ? (
                        <CircleCheck className="h-3.5 w-3.5 shrink-0 fill-neutral-950 text-neutral-50 dark:fill-neutral-50 dark:text-neutral-950" />
                      ) : (
                        <FileText className="h-3.5 w-3.5 shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[9px] font-medium">{d.name}</p>
                        <p className="text-[8px] text-neutral-500">{d.meta}</p>
                      </div>
                      <EllipsisVertical className="h-3 w-3 text-neutral-400" />
                    </div>
                    {fresh && t < T.ready && (
                      <div className="ml-5 mt-1 h-[3px] overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
                        <div
                          className={`h-full rounded-full bg-neutral-950 dark:bg-neutral-50 ${uploadP >= 1 ? "animate-pulse" : ""}`}
                          style={{ width: `${uploadP * 100}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* assistant */}
            <div className="flex h-[168px] flex-col overflow-hidden rounded-lg border border-neutral-200 p-2 dark:border-neutral-800">
              {!chatMode ? (
                <div className="flex flex-1 flex-col items-center text-center" style={{ opacity: loopFade }}>
                  <span className="relative mt-1 grid h-8 w-8 place-items-center rounded-xl bg-neutral-950 text-neutral-50 dark:bg-neutral-50 dark:text-neutral-950">
                    <span className="absolute inset-0 animate-ping rounded-xl bg-neutral-950/30 [animation-duration:2s] dark:bg-neutral-50/30" />
                    <Bot className="relative h-4 w-4" />
                  </span>
                  <p className="mt-2 text-[9px] font-medium">Ask anything about your documents...</p>
                  {["Explain this concept", "Summarize this chapter", "Give me examples"].map((c) => (
                    <span key={c} className="mt-1.5 w-full rounded-full border border-neutral-200 px-2 py-1 text-[8px] dark:border-neutral-800">
                      {c}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col animate-in fade-in duration-500" style={{ opacity: loopFade }}>
                  <div className="flex min-h-0 flex-1 flex-col justify-end gap-1.5 overflow-hidden">
                    {!asked && (
                      <div className="m-auto flex flex-col items-center gap-1 text-center text-[8px] text-neutral-500">
                        <Bot className="h-4 w-4 text-neutral-950 dark:text-neutral-50" />
                        Ask anything about
                        <span className="font-medium text-neutral-950 dark:text-neutral-50">Biology Notes.pdf</span>
                      </div>
                    )}
                    {asked && (
                      <p className="ml-auto max-w-[90%] rounded-xl rounded-br-sm bg-neutral-950 px-2 py-1 text-[8px] text-neutral-50 animate-in fade-in slide-in-from-bottom-1 dark:bg-neutral-50 dark:text-neutral-950">
                        {QUESTION}
                      </p>
                    )}
                    {thinking && (
                      <span className="flex w-fit gap-0.5 rounded-xl bg-neutral-100 px-2 py-1.5 dark:bg-neutral-800">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="h-1 w-1 animate-bounce rounded-full bg-neutral-500" style={{ animationDelay: `${i * 120}ms` }} />
                        ))}
                      </span>
                    )}
                    {t >= T.answerStart && (
                      <div className="max-w-[96%] rounded-xl rounded-bl-sm bg-neutral-100 px-2 py-1.5 text-[8px] leading-snug dark:bg-neutral-800">
                        {answer}
                        {!answered && <span className="ml-px inline-block h-2 w-px translate-y-px bg-current" />}
                        {answered && (
                          <div className="mt-1 flex items-center gap-1 animate-in fade-in">
                            <span className="truncate whitespace-nowrap rounded-full border border-neutral-300 px-1.5 py-px text-[7px] dark:border-neutral-700">
                              Biology Notes · p. 12
                            </span>
                            <span
                              data-demo="listen"
                              className={`ml-auto flex items-center gap-1 rounded-full px-1.5 py-px text-[7px] font-medium transition ${
                                playing || pressed(T.listen)
                                  ? "bg-neutral-950 text-neutral-50 dark:bg-neutral-50 dark:text-neutral-950"
                                  : "border border-neutral-300 dark:border-neutral-700"
                              }`}
                            >
                              {playing ? <Pause className="h-2 w-2" /> : <Volume2 className="h-2 w-2" />}
                              {playing ? "Playing" : "Listen"}
                            </span>
                          </div>
                        )}
                        {playing && (
                          <div className="mt-1 flex items-center gap-1.5">
                            <span className="flex h-3 items-end gap-[2px]">
                              {Array.from({ length: 14 }, (_, i) => (
                                <span
                                  key={i}
                                  className="w-[2px] rounded-full bg-neutral-950 dark:bg-neutral-50"
                                  style={{ height: `${25 + 75 * Math.abs(Math.sin(t / 140 + i * 0.9) * Math.cos(t / 330 + i))}%` }}
                                />
                              ))}
                            </span>
                            <span className="h-[2px] flex-1 overflow-hidden rounded-full bg-neutral-300 dark:bg-neutral-700">
                              <span className="block h-full bg-neutral-950 dark:bg-neutral-50" style={{ width: `${playP * 100}%` }} />
                            </span>
                            <span className="text-[7px] tabular-nums text-neutral-500">0:0{Math.floor(playP * 9)}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div
                    data-demo="input"
                    className={`mt-1.5 flex items-center gap-1 rounded-full border px-2 py-1 text-[8px] transition ${
                      t >= T.typeStart - 300 && t < T.send ? "border-neutral-950 dark:border-neutral-50" : "border-neutral-200 dark:border-neutral-800"
                    }`}
                  >
                    <span className={`min-w-0 flex-1 truncate ${typed ? "" : "text-neutral-400"}`}>
                      {typed || "Ask a question…"}
                      {t >= T.typeStart - 300 && t < T.send && caretOn && <span className="ml-px inline-block h-2 w-px translate-y-px bg-current" />}
                    </span>
                    <SendHorizontal className={`h-2.5 w-2.5 shrink-0 transition ${pressed(T.send - 150) ? "scale-125" : ""}`} />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* quiz toast */}
          {quizToast && (
            <div className="absolute right-4 top-12 flex items-center gap-1.5 rounded-xl bg-neutral-950 px-3 py-2 text-[9px] font-medium text-neutral-50 shadow-lg animate-in fade-in slide-in-from-top-2 duration-300 dark:bg-neutral-50 dark:text-neutral-950">
              <CircleCheck className="h-3 w-3" /> Quiz ready · 10 questions from Biology Notes
            </div>
          )}
        </div>

        {/* cursor */}
        {cursor && !reduce && (
          <div
            className="pointer-events-none absolute left-0 top-0 z-20 transition-[transform] duration-[800ms] ease-[cubic-bezier(0.65,0,0.35,1)]"
            style={{ transform: `translate(${cursor.x - 3}px, ${cursor.y - 2}px)` }}
          >
            {clicking && <span className="absolute -left-2.5 -top-2.5 h-6 w-6 animate-ping rounded-full bg-neutral-950/25 dark:bg-neutral-50/30" />}
            <svg
              viewBox="0 0 24 24"
              className={`h-5 w-5 drop-shadow-[0_2px_3px_rgba(0,0,0,0.3)] transition-transform duration-150 ${clicking ? "scale-[0.82]" : ""}`}
            >
              <path d="M4 2 L4 19 L8.6 14.8 L11.6 21.4 L14.4 20.2 L11.4 13.6 L17.6 13.4 Z" fill="#181715" stroke="#faf9f5" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
