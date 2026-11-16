"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { motion, MotionConfig } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  ChartColumnIncreasing,
  ChevronDown,
  CircleCheck,
  CloudUpload,
  FileText,
  MessageSquareMore,
  Mic,
  Moon,
  Play,
  ShieldCheck,
  Sparkles,
  Sun,
  Zap,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { StudyIllustration } from "./StudyIllustration";
import { HeroDemo } from "./HeroDemo";
import { fadeUp, Reveal, stagger, Stagger, StaggerItem } from "./motion";

const NAV = [
  { href: "#features", label: "Features", menu: true },
  { href: "#pricing", label: "Pricing" },
  { href: "#about", label: "About" },
  { href: "#faq", label: "FAQ" },
];

const FEATURE_MENU = [
  { href: "#features", label: "Ask your documents" },
  { href: "#features", label: "Document reader" },
  { href: "#features", label: "Voice & listening" },
  { href: "#about", label: "Quizzes & study plans" },
];

const HIGHLIGHTS = [
  { icon: FileText, title: "RAG-Powered", text: "Answers from your docs" },
  { icon: Zap, title: "Interactive", text: "Document reader" },
  { icon: Mic, title: "Voice & Listening", text: "With voice cloning" },
  { icon: ChartColumnIncreasing, title: "Track Progress", text: "& boost performance" },
  { icon: ShieldCheck, title: "Secure & Private", text: "Your data, your control" },
];

const CHECKS = [
  "Upload & read any document",
  "Ask questions with RAG",
  "Get AI explanations",
  "Take quizzes & practice papers",
  "Create study plans",
  "Track your progress",
  "Build revision sheets",
  "Learn in Urdu & English",
];

const STEPS = [
  { icon: CloudUpload, title: "Upload", text: "Your study material" },
  { icon: MessageSquareMore, title: "Ask Questions", text: "or read along" },
  { icon: CircleCheck, title: "Practice & Learn", text: "with AI tools" },
  { icon: ChartColumnIncreasing, title: "Track Progress", text: "and improve" },
];

// Sample quotes for the layout. Replace them with real feedback from your users before launch.
const QUOTES = [
  { quote: "EchoLearn has completely changed how I study. The AI explanations are super helpful!", name: "Ayesha Khan", role: "BS Student", tone: "bg-[#e8d5c4]" },
  { quote: "Simple, powerful and easy to use. Perfect for exam preparation!", name: "Usman Ahmed", role: "College Student", tone: "bg-[#d9d2c3]" },
  { quote: "The best study assistant I've ever used. Highly recommended!", name: "Fatima Rizwan", role: "University Student", tone: "bg-[#e3cbbd]" },
];

const FAQS = [
  {
    q: "Which files can I upload?",
    a: "PDF, Word, PowerPoint, text files, images, audio and video. EchoLearn reads the text (and transcribes recordings) so you can ask questions about any of them.",
  },
  {
    q: "Are the answers taken from my documents?",
    a: "Yes. Every answer is built from the passages EchoLearn finds in your files and shows the page it came from. If the answer is not in your documents, it says so instead of guessing.",
  },
  {
    q: "Can I study in Urdu?",
    a: "Yes. You can ask questions and get explanations in Urdu or English, and have answers read aloud.",
  },
  {
    q: "Is it free?",
    a: "The free plan covers uploading, chatting, quizzes and the reader with daily limits. Paid plans raise the limits for heavier use.",
  },
  {
    q: "Who can see my documents?",
    a: "Only you. Your files and chats are private to your account, and you can delete them at any time.",
  },
];

const AVATARS = [
  { i: "AK", c: "bg-[#e8d5c4]" },
  { i: "UA", c: "bg-[#d9d2c3]" },
  { i: "FR", c: "bg-[#e3cbbd]" },
  { i: "HS", c: "bg-[#cfc6b6]" },
  { i: "ZM", c: "bg-[#ead9c9]" },
];

function Logo({ small = false }: { small?: boolean }) {
  return (
    <span className="flex items-center gap-2 sm:gap-2.5">
      <BookOpen className={small ? "h-7 w-7" : "h-7 w-7 sm:h-8 sm:w-8"} strokeWidth={1.8} />
      <span className={`font-serif font-medium tracking-tight ${small ? "text-[20px]" : "text-[19px] sm:text-[22px]"}`}>EchoLearn</span>
    </span>
  );
}

const subscribeNothing = () => () => {};

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // false during server rendering, true in the browser: avoids a sun/moon mismatch on load.
  const mounted = useSyncExternalStore(subscribeNothing, () => true, () => false);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-neutral-700 sm:h-10 sm:w-10 transition hover:bg-neutral-200/70 dark:text-neutral-300 dark:hover:bg-neutral-800"
    >
      {dark ? <Moon className="h-[18px] w-[18px]" /> : <Sun className="h-[18px] w-[18px]" />}
    </button>
  );
}

function PrimaryButton({ href, children, className = "" }: { href: string; children: React.ReactNode; className?: string }) {
  return (
    <Link
      href={href}
      className={`group inline-flex items-center justify-center gap-2 rounded-full bg-neutral-950 px-6 py-3 text-[15px] font-medium text-neutral-50 shadow-sm transition duration-300 hover:-translate-y-0.5 hover:bg-neutral-800 hover:shadow-[0_10px_24px_-10px_rgba(24,23,21,0.55)] active:translate-y-0 [&>svg]:transition-transform [&>svg]:duration-300 group-hover:[&>svg]:translate-x-1 dark:bg-neutral-50 dark:text-neutral-950 dark:hover:bg-neutral-200 ${className}`}
    >
      {children}
    </Link>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-neutral-200/80 px-3 py-1 text-[13px] font-medium text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200">
      {children}
    </span>
  );
}

function Header({ authed }: { authed: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-transparent bg-neutral-50/85 backdrop-blur-md dark:bg-neutral-950/85">
      <div className="mx-auto flex h-[76px] max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" aria-label="EchoLearn home">
          <Logo />
        </Link>

        <nav className="hidden items-center gap-9 text-[15px] font-medium text-neutral-800 md:flex dark:text-neutral-200" aria-label="Main">
          {NAV.map((item) =>
            item.menu ? (
              <div key={item.label} className="group relative">
                <a href={item.href} className="flex items-center gap-1 hover:text-neutral-950 dark:hover:text-white">
                  {item.label} <ChevronDown className="h-4 w-4 transition group-hover:rotate-180" />
                </a>
                <div className="invisible absolute left-1/2 top-full w-56 -translate-x-1/2 pt-3 opacity-0 transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                  <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-2 shadow-lg dark:border-neutral-800 dark:bg-neutral-900">
                    {FEATURE_MENU.map((f) => (
                      <a key={f.label} href={f.href} className="block rounded-xl px-3 py-2 text-[14px] hover:bg-neutral-100 dark:hover:bg-neutral-800">
                        {f.label}
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <a key={item.label} href={item.href} className="hover:text-neutral-950 dark:hover:text-white">
                {item.label}
              </a>
            )
          )}
        </nav>

        <div className="flex items-center gap-1 sm:gap-3">
          <span className="max-[400px]:hidden">
            <ThemeToggle />
          </span>
          {authed ? (
            <PrimaryButton href="/dashboard" className="whitespace-nowrap px-4 py-2.5 text-[14px] sm:px-5">
              Open Dashboard <ArrowRight className="h-4 w-4" />
            </PrimaryButton>
          ) : (
            <>
              <Link
                href="/login"
                className="hidden rounded-full border border-neutral-950 px-5 py-2 text-[14px] font-medium transition hover:bg-neutral-950 hover:text-neutral-50 sm:inline-flex dark:border-neutral-50 dark:hover:bg-neutral-50 dark:hover:text-neutral-950"
              >
                Log In
              </Link>
              <PrimaryButton href="/signup" className="whitespace-nowrap px-4 py-2.5 text-[14px] sm:px-5">
                Get Started <ArrowRight className="hidden h-4 w-4 sm:block" />
              </PrimaryButton>
            </>
          )}
          <button
            type="button"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full md:hidden"
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-5 bg-current" />
              <span className="block h-0.5 w-5 bg-current" />
            </span>
          </button>
        </div>
      </div>
      {open && (
        <nav className="border-t border-neutral-200 bg-neutral-50 px-4 py-3 md:hidden dark:border-neutral-800 dark:bg-neutral-950" aria-label="Mobile">
          {NAV.map((item) => (
            <a key={item.label} href={item.href} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-3 text-[16px] font-medium hover:bg-neutral-100 dark:hover:bg-neutral-900">
              {item.label}
            </a>
          ))}
          {!authed && (
            <Link href="/login" className="block rounded-xl px-3 py-3 text-[16px] font-medium hover:bg-neutral-100 dark:hover:bg-neutral-900">
              Log In
            </Link>
          )}
          <div className="flex items-center justify-between px-3 py-1 text-[16px] font-medium min-[401px]:hidden">
            Theme <ThemeToggle />
          </div>
        </nav>
      )}
    </header>
  );
}

function Testimonials() {
  const rowRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const row = rowRef.current;
    if (!row) return;
    const cards = Array.from(row.children) as HTMLElement[];
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(cards.indexOf(e.target as HTMLElement));
      },
      { root: row, threshold: 0.6 }
    );
    cards.forEach((c) => io.observe(c));
    return () => io.disconnect();
  }, []);

  function go(i: number) {
    const card = rowRef.current?.children[i] as HTMLElement | undefined;
    card?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
  }

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <Reveal className="text-center">
        <Pill>Loved by Students</Pill>
        <h2 className="mt-4 font-serif text-[34px] font-semibold tracking-tight sm:text-[40px]">What Our Students Say</h2>
      </Reveal>
      <div
        ref={rowRef}
        className="-mx-4 mt-10 flex snap-x snap-mandatory gap-5 overflow-x-auto px-4 pb-2 [scrollbar-width:none] md:mx-0 md:grid md:grid-cols-3 md:overflow-visible md:px-0"
      >
        {QUOTES.map((t, i) => (
          <motion.figure
            key={t.name}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
            whileHover={{ y: -6, boxShadow: "0 22px 40px -24px rgba(24,23,21,0.35)" }}
            className="w-[85%] shrink-0 snap-start rounded-3xl border border-neutral-200 bg-neutral-50 p-7 shadow-[0_1px_0_rgba(24,23,21,0.04)] md:w-auto dark:border-neutral-800 dark:bg-neutral-900"
          >
            <span className="font-serif text-[44px] leading-none">&ldquo;</span>
            <blockquote className="mt-1 text-[16px] leading-relaxed text-neutral-800 dark:text-neutral-200">&ldquo;{t.quote}&rdquo;</blockquote>
            <figcaption className="mt-6 flex items-center gap-3">
              <span className={`grid h-11 w-11 place-items-center rounded-full text-[14px] font-semibold text-neutral-900 ${t.tone}`}>
                {t.name.split(" ").map((p) => p[0]).join("")}
              </span>
              <span>
                <span className="block text-[15px] font-semibold">{t.name}</span>
                <span className="block text-[13px] text-neutral-600 dark:text-neutral-400">{t.role}</span>
              </span>
            </figcaption>
          </motion.figure>
        ))}
      </div>
      <div className="mt-6 flex justify-center gap-2 md:hidden">
        {QUOTES.map((t, i) => (
          <button
            key={t.name}
            type="button"
            aria-label={`Show quote ${i + 1}`}
            onClick={() => go(i)}
            className={`h-2.5 w-2.5 rounded-full border border-neutral-950 transition dark:border-neutral-50 ${i === active ? "bg-neutral-950 dark:bg-neutral-50" : ""}`}
          />
        ))}
      </div>
    </section>
  );
}

export function LandingPage() {
  const { isAuthenticated } = useAuth();
  const start = isAuthenticated ? "/dashboard" : "/signup";

  return (
    <MotionConfig reducedMotion="user">
    <div className="relative min-h-screen overflow-x-clip bg-neutral-50 text-neutral-950 dark:bg-neutral-950 dark:text-neutral-50">
      {/* soft background shapes, drifting slowly */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -right-40 -top-40 h-[620px] w-[620px] rounded-full bg-neutral-100 dark:bg-neutral-900"
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: [1, 1.04, 1], opacity: 1, x: [0, -20, 0] }}
        transition={{ opacity: { duration: 1.2 }, scale: { duration: 16, repeat: Infinity, ease: "easeInOut" }, x: { duration: 16, repeat: Infinity, ease: "easeInOut" } }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -right-24 top-[360px] hidden h-[260px] w-[120px] rounded-[60px] bg-neutral-950 lg:block dark:bg-neutral-800"
        initial={{ opacity: 0, x: 80, rotate: -28 }}
        animate={{ opacity: 1, x: 0, rotate: [-28, -24, -28] }}
        transition={{ opacity: { duration: 1, delay: 0.6 }, x: { duration: 1.2, delay: 0.6, ease: [0.22, 1, 0.36, 1] }, rotate: { duration: 10, repeat: Infinity, ease: "easeInOut" } }}
      />

      <div className="relative">
        <Header authed={isAuthenticated} />

        {/* ---------------------------------------------------------------- hero */}
        <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-14 pt-10 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:px-8 lg:pt-14">
          <motion.div variants={stagger(0.12, 0.1)} initial="hidden" animate="show">
            <motion.div variants={fadeUp}>
              <Pill>
                <motion.span
                  className="inline-flex"
                  animate={{ rotate: [0, 18, -8, 0], scale: [1, 1.2, 1] }}
                  transition={{ duration: 1.6, delay: 1.2, repeat: Infinity, repeatDelay: 4 }}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                </motion.span>
                Your Personal AI Study Assistant
              </Pill>
            </motion.div>
            <h1 className="mt-6 font-serif text-[52px] font-bold leading-[0.98] tracking-[-0.03em] sm:text-[68px] lg:text-[76px]">
              <motion.span variants={fadeUp} className="block">
                Study Smarter.
              </motion.span>
              <motion.span variants={fadeUp} className="relative inline-block">
                Learn Better.
                <svg aria-hidden viewBox="0 0 300 20" className="absolute -bottom-4 left-[18%] w-[62%]" fill="none">
                  <motion.path
                    d="M4 14 C80 4 180 2 296 10"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.9, delay: 0.9, ease: "easeInOut" }}
                  />
                </svg>
              </motion.span>
            </h1>
            <motion.p variants={fadeUp} className="mt-9 max-w-[480px] text-[17px] leading-relaxed text-neutral-700 dark:text-neutral-300">
              Upload your study material, ask questions, and get instant AI-powered explanations — all from your own
              documents.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-8 flex flex-wrap items-center gap-5">
              <PrimaryButton href={start}>
                {isAuthenticated ? "Go to Dashboard" : "Start Learning Free"} <ArrowRight className="h-4 w-4" />
              </PrimaryButton>
              <a href="#how-it-works" className="group inline-flex items-center gap-3 text-[15px] font-medium">
                <span className="grid h-11 w-11 place-items-center rounded-full border border-neutral-950 transition group-hover:bg-neutral-950 group-hover:text-neutral-50 dark:border-neutral-50 dark:group-hover:bg-neutral-50 dark:group-hover:text-neutral-950">
                  <Play className="ml-0.5 h-4 w-4 fill-current" />
                </span>
                See How It Works
              </a>
            </motion.div>
            <motion.div variants={fadeUp} className="mt-9 flex items-center gap-3">
              <div className="flex -space-x-2.5">
                {AVATARS.map((a, i) => (
                  <motion.span
                    key={a.i}
                    initial={{ opacity: 0, scale: 0.4, x: -8 }}
                    animate={{ opacity: 1, scale: 1, x: 0 }}
                    transition={{ delay: 1 + i * 0.08, type: "spring", stiffness: 380, damping: 20 }}
                    whileHover={{ y: -4, zIndex: 10 }}
                    className={`relative grid h-9 w-9 place-items-center rounded-full border-2 border-neutral-50 text-[11px] font-semibold text-neutral-900 dark:border-neutral-950 ${a.c}`}
                  >
                    {a.i}
                  </motion.span>
                ))}
              </div>
              <p className="text-[14px] text-neutral-700 dark:text-neutral-300">Built for students · Urdu &amp; English</p>
            </motion.div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: 60, y: 20 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            transition={{ duration: 1.1, delay: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            <motion.div animate={{ y: [0, -10, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}>
              <HeroDemo />
            </motion.div>
          </motion.div>
        </section>

        {/* ------------------------------------------------------- highlight strip */}
        <section id="features" className="mx-auto max-w-7xl scroll-mt-24 px-4 sm:px-6 lg:px-8">
          <Stagger
            gap={0.09}
            className="grid grid-cols-2 gap-y-6 rounded-3xl bg-neutral-100 px-5 py-6 sm:grid-cols-3 lg:grid-cols-5 lg:divide-x lg:divide-neutral-300 dark:bg-neutral-900 dark:lg:divide-neutral-700"
          >
            {HIGHLIGHTS.map((h) => (
              <StaggerItem key={h.title} className="group flex items-center gap-3.5 lg:justify-center lg:px-4">
                <h.icon
                  className="h-8 w-8 shrink-0 transition-transform duration-300 group-hover:-translate-y-1 group-hover:scale-110"
                  strokeWidth={1.5}
                />
                <div>
                  <p className="text-[14px] font-medium">{h.title}</p>
                  <p className="text-[13px] text-neutral-600 dark:text-neutral-400">{h.text}</p>
                </div>
              </StaggerItem>
            ))}
          </Stagger>
        </section>

        {/* ---------------------------------------------------------- platform */}
        <section id="about" className="mx-auto grid max-w-7xl scroll-mt-24 items-center gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:px-8">
          <Reveal x={-40} y={0}>
            <StudyIllustration className="mx-auto w-full max-w-[520px] text-neutral-950 dark:text-neutral-100" />
          </Reveal>
          <div>
            <Reveal>
              <Pill>Everything You Need in One Place</Pill>
              <h2 className="mt-4 font-serif text-[34px] font-semibold leading-tight tracking-tight sm:text-[42px]">
                A Complete AI Learning Platform
              </h2>
              <p className="mt-4 max-w-[520px] text-[16px] leading-relaxed text-neutral-700 dark:text-neutral-300">
                From notes to quizzes, EchoLearn helps you read, understand, and master your study material with ease.
              </p>
            </Reveal>
            <Stagger as="ul" gap={0.06} className="mt-7 grid gap-x-10 gap-y-3.5 sm:grid-flow-col sm:grid-cols-2 sm:grid-rows-4">
              {CHECKS.map((c) => (
                <StaggerItem as="li" key={c} className="flex items-center gap-3 text-[15px]">
                  <CircleCheck className="h-5 w-5 shrink-0 fill-neutral-950 text-neutral-50 dark:fill-neutral-50 dark:text-neutral-950" />
                  {c}
                </StaggerItem>
              ))}
            </Stagger>
            <Reveal delay={0.2}>
              <PrimaryButton href={start} className="mt-9">
                Explore All Features <ArrowRight className="h-4 w-4" />
              </PrimaryButton>
            </Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------- how it works */}
        <section id="how-it-works" className="mx-auto grid max-w-7xl scroll-mt-24 items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[0.75fr_2fr] lg:px-8">
          <Reveal>
            <Pill>How It Works</Pill>
            <h2 className="mt-4 font-serif text-[34px] font-semibold leading-tight tracking-tight sm:text-[38px]">
              Your Learning Journey in 4 Simple Steps
            </h2>
          </Reveal>
          <Stagger
            as="ol"
            gap={0.15}
            className="grid grid-cols-2 gap-4 sm:grid-cols-4 sm:gap-0 sm:rounded-3xl sm:border sm:border-neutral-200 sm:bg-neutral-50 sm:py-8 dark:sm:border-neutral-800 dark:sm:bg-neutral-900"
          >
            {STEPS.map((s, i) => (
              <StaggerItem
                as="li"
                key={s.title}
                className="group relative flex flex-col items-center rounded-3xl border border-neutral-200 bg-neutral-50 px-3 py-6 text-center sm:rounded-none sm:border-0 sm:bg-transparent sm:py-0 dark:border-neutral-800 dark:bg-neutral-900 dark:sm:bg-transparent"
              >
                <span className="grid h-6 w-6 place-items-center rounded-full bg-neutral-950 text-[12px] font-semibold text-neutral-50 dark:bg-neutral-50 dark:text-neutral-950">
                  {i + 1}
                </span>
                <s.icon className="mt-4 h-10 w-10 transition-transform duration-300 group-hover:-translate-y-1 group-hover:scale-110" strokeWidth={1.4} />
                <p className="mt-3 text-[15px] font-semibold">{s.title}</p>
                <p className="text-[14px] text-neutral-600 dark:text-neutral-400">{s.text}</p>
                {i < STEPS.length - 1 && (
                  <motion.span
                    aria-hidden
                    className="absolute -right-2.5 top-1/2 hidden text-neutral-500 sm:block"
                    animate={{ x: [0, 5, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut", delay: i * 0.3 }}
                  >
                    <ArrowRight className="h-5 w-5" />
                  </motion.span>
                )}
              </StaggerItem>
            ))}
          </Stagger>
        </section>

        <Testimonials />

        {/* ---------------------------------------------------------------- FAQ */}
        <section id="faq" className="mx-auto max-w-3xl scroll-mt-24 px-4 py-12 sm:px-6">
          <Reveal className="text-center">
            <Pill>FAQ</Pill>
            <h2 className="mt-4 font-serif text-[34px] font-semibold tracking-tight sm:text-[40px]">Questions, Answered</h2>
          </Reveal>
          <Stagger
            gap={0.07}
            className="mt-8 divide-y divide-neutral-200 rounded-3xl border border-neutral-200 bg-neutral-50 dark:divide-neutral-800 dark:border-neutral-800 dark:bg-neutral-900"
          >
            {FAQS.map((f) => (
              <StaggerItem key={f.q}>
                <details className="faq group px-6 py-5">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[16px] font-medium [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <ChevronDown className="h-5 w-5 shrink-0 transition-transform duration-300 group-open:rotate-180" />
                  </summary>
                  <p className="mt-3 text-[15px] leading-relaxed text-neutral-700 dark:text-neutral-300">{f.a}</p>
                </details>
              </StaggerItem>
            ))}
          </Stagger>
        </section>

        {/* ---------------------------------------------------------------- CTA */}
        <section id="pricing" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8">
          <Reveal className="relative overflow-hidden rounded-[32px] border border-neutral-200 bg-neutral-100 px-6 py-12 sm:px-14 dark:border-neutral-800 dark:bg-neutral-900">
            <motion.div
              aria-hidden
              className="absolute -left-16 -top-20 h-56 w-56 rounded-full bg-neutral-200/70 dark:bg-neutral-800/60"
              animate={{ x: [0, 18, 0], y: [0, 12, 0] }}
              transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.div
              aria-hidden
              className="absolute -bottom-24 -right-10 h-64 w-64 rounded-full bg-neutral-200/70 dark:bg-neutral-800/60"
              animate={{ x: [0, -16, 0], y: [0, -10, 0] }}
              transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
            />
            <div className="relative flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
              <div>
                <h2 className="font-serif text-[34px] font-semibold tracking-tight sm:text-[40px]">Ready to Learn Smarter?</h2>
                <p className="mt-2 text-[16px] text-neutral-700 dark:text-neutral-300">
                  Start free today. Upgrade any time for higher daily limits.
                </p>
              </div>
              <div className="flex items-center gap-4">
                <svg aria-hidden viewBox="0 0 120 30" className="hidden w-28 lg:block" fill="none">
                  <motion.path
                    d="M2 10 C40 28 80 26 112 14"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    initial={{ pathLength: 0 }}
                    whileInView={{ pathLength: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.9, delay: 0.4, ease: "easeInOut" }}
                  />
                  <motion.path
                    d="M104 8 L113 14 L103 19"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: 1.25 }}
                  />
                </svg>
                <PrimaryButton href={start} className="px-7 py-3.5 text-[16px]">
                  {isAuthenticated ? "Go to Dashboard" : "Get Started Free"} <ArrowRight className="h-4 w-4" />
                </PrimaryButton>
              </div>
            </div>
          </Reveal>
        </section>

        {/* ------------------------------------------------------------- footer */}
        <footer className="border-t border-neutral-200 dark:border-neutral-800">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:grid-cols-2 sm:px-6 lg:grid-cols-[1.4fr_1fr_1fr_1fr] lg:px-8">
            <div>
              <Logo small />
              <p className="mt-2 text-[13px] text-neutral-600 dark:text-neutral-400">Study Smarter. Learn Better.</p>
            </div>
            <div>
              <p className="text-[14px] font-semibold">Quick Links</p>
              <ul className="mt-3 space-y-2 text-[14px] text-neutral-700 dark:text-neutral-300">
                <li><a href="#features" className="hover:underline">Features</a></li>
                <li><a href="#pricing" className="hover:underline">Pricing</a></li>
                <li><a href="#faq" className="hover:underline">FAQ</a></li>
              </ul>
            </div>
            <div>
              <p className="text-[14px] font-semibold">Account</p>
              <ul className="mt-3 space-y-2 text-[14px] text-neutral-700 dark:text-neutral-300">
                <li><Link href="/login" className="hover:underline">Log In</Link></li>
                <li><Link href="/signup" className="hover:underline">Create Account</Link></li>
                <li><Link href="/forgot-password" className="hover:underline">Reset Password</Link></li>
              </ul>
            </div>
            <div className="flex flex-col justify-end text-[13px] text-neutral-600 lg:items-end dark:text-neutral-400">
              © {new Date().getFullYear()} EchoLearn. All rights reserved.
            </div>
          </div>
        </footer>
      </div>
    </div>
    </MotionConfig>
  );
}
