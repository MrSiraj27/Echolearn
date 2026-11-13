"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BarChart3,
  Bell,
  BookOpen,
  CalendarCheck,
  ChevronDown,
  CircleCheckBig,
  Crown,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  NotebookPen,
  ScrollText,
  Search,
  Settings,
  Shield,
  Sparkles,
  Sun,
  Volume2,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useChatStore } from "@/lib/chat-store";
import { clearMe, initial, useMe } from "@/lib/me";
import { isReady } from "@/components/documents/docUi";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, match: ["/dashboard"] },
  { href: "/documents", label: "My Documents", icon: FileText, match: ["/documents"] },
  { href: "/chat", label: "AI Assistant", icon: Sparkles, match: ["/chat"] },
  { href: "/read", label: "Document Reader", icon: BookOpen, match: ["/read"] },
  { href: "/tutor", label: "Tutor Mode", icon: GraduationCap, match: ["/tutor"] },
  { href: "/quizzes", label: "Quizzes", icon: CircleCheckBig, match: ["/quizzes", "/quiz/", "/review"] },
  { href: "/study-plans", label: "Study Plans", icon: CalendarCheck, match: ["/study-plans"] },
  { href: "/practice-papers", label: "Practice Papers", icon: NotebookPen, match: ["/practice-papers"] },
  { href: "/revision-sheets", label: "Revision Sheets", icon: ScrollText, match: ["/revision-sheets"] },
  { href: "/analytics", label: "Analytics", icon: BarChart3, match: ["/analytics"] },
  { href: "/settings#voice", label: "Voice & Listening", icon: Volume2, match: [] as string[] },
  { href: "/settings", label: "Settings", icon: Settings, match: ["/settings"] },
];

interface QuotaItem {
  key: string;
  label: string;
  limit: number | boolean | string[] | null;
  current_usage: number;
}
interface UsageResponse {
  plan_name: string | null;
  quotas: QuotaItem[];
  has_pending_reviews?: boolean;
}

function useUsage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const pathname = usePathname();
  useEffect(() => {
    let alive = true;
    api
      .get<UsageResponse>("/users/me/usage", { auth: true })
      .then((u) => alive && setUsage(u))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [pathname]);
  return usage;
}

/** The quota closest to its limit, e.g. "Messages: 82% used". */
function topQuota(usage: UsageResponse | null): { label: string; pct: number } | null {
  if (!usage) return null;
  let best: { label: string; pct: number } | null = null;
  for (const q of usage.quotas) {
    if (typeof q.limit !== "number" || q.limit <= 0) continue;
    const pct = Math.min(100, Math.round((q.current_usage / q.limit) * 100));
    if (!best || pct > best.pct) best = { label: q.label, pct };
  }
  return best;
}

function NavRail({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const me = useMe();
  const usage = useUsage();
  const { logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const quota = topQuota(usage);
  const planName = usage?.plan_name || me?.plan_name || "Free";

  function signOut() {
    clearMe();
    logout();
    router.replace("/login");
  }

  return (
    // One scroll area for the whole rail, so short screens never get a cramped inner scrollbox.
    <div className="flex h-full flex-col overflow-y-auto bg-neutral-950 text-neutral-300 [scrollbar-width:thin]">
      <Link href="/dashboard" onClick={onNavigate} className="flex shrink-0 items-center gap-2.5 px-5 py-5">
        <BookOpen className="h-7 w-7 text-neutral-50" strokeWidth={1.6} />
        <span>
          <span className="block font-serif text-[20px] leading-none tracking-tight text-neutral-50">EchoLearn</span>
          <span className="mt-1 block text-[11px] text-neutral-500">Study smarter</span>
        </span>
      </Link>

      <nav className="flex-1 space-y-px px-3 pb-3" aria-label="Main">
        {NAV.map((item) => {
          // "/quiz/" style entries match a prefix; plain entries match the page and its children.
          const active = item.match.some((m) =>
            m.endsWith("/") ? pathname.startsWith(m) : pathname === m || pathname.startsWith(`${m}/`)
          );
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-[7px] text-[13.5px] transition-colors ${
                active
                  ? "bg-neutral-50 font-medium text-neutral-950"
                  : "text-neutral-400 hover:bg-white/[0.06] hover:text-neutral-50"
              }`}
            >
              <Icon className="h-[17px] w-[17px] shrink-0" strokeWidth={active ? 2 : 1.7} />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="shrink-0 px-3 pb-2">
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="flex min-w-0 items-center gap-1.5 text-[12.5px] font-medium text-neutral-50">
              <Crown className="h-3.5 w-3.5 shrink-0 text-coral" /> <span className="truncate">{planName} plan</span>
            </p>
            <Link href="/upgrade" onClick={onNavigate} className="shrink-0 rounded-md bg-coral px-2 py-1 text-[11px] font-medium text-white hover:bg-coral-active">
              Upgrade
            </Link>
          </div>
          {quota ? (
            <>
              <p className="mt-1.5 truncate text-[11px] text-neutral-500" title={`${quota.label}: ${quota.pct}% of your limit used`}>
                {quota.label}: {quota.pct}% used
              </p>
              <div className="mt-1.5 h-1 rounded-full bg-white/10" role="progressbar" aria-valuenow={quota.pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${quota.label} usage`}>
                <div className={`h-1 rounded-full ${quota.pct >= 90 ? "bg-coral" : "bg-neutral-50"}`} style={{ width: `${Math.max(quota.pct, 2)}%` }} />
              </div>
            </>
          ) : (
            <p className="mt-1.5 text-[11px] text-neutral-500">Within all plan limits</p>
          )}
        </div>
      </div>

      <div className="relative shrink-0 border-t border-white/[0.08] px-3 py-2.5">
        <button
          onClick={() => setMenuOpen((v) => !v)}
          className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left hover:bg-white/[0.06]"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neutral-50 text-[13px] font-semibold text-neutral-950">
            {initial(me?.name)}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-medium text-neutral-50">{me?.name ?? " "}</span>
            <span className="block truncate text-[11px] text-neutral-500">{me?.email ?? ""}</span>
          </span>
          <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${menuOpen ? "rotate-180" : ""}`} />
        </button>
        {menuOpen && (
          <div role="menu" className="absolute bottom-full left-3 right-3 mb-2 overflow-hidden rounded-xl border border-white/10 bg-neutral-900 py-1 shadow-xl">
            <Link role="menuitem" href="/settings" onClick={onNavigate} className="flex items-center gap-2 px-3 py-2 text-[13px] hover:bg-white/[0.06]">
              <Settings className="h-4 w-4" /> Settings
            </Link>
            {me?.is_admin && (
              <Link role="menuitem" href="/admin" className="flex items-center gap-2 px-3 py-2 text-[13px] hover:bg-white/[0.06]">
                <Shield className="h-4 w-4" /> Admin console
              </Link>
            )}
            <button role="menuitem" onClick={signOut} className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] hover:bg-white/[0.06]">
              <LogOut className="h-4 w-4" /> Log out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <div className="flex items-center rounded-full border border-neutral-200 bg-neutral-50 p-0.5 dark:border-neutral-800 dark:bg-neutral-900" role="group" aria-label="Theme">
      <button
        onClick={() => setTheme("light")}
        aria-pressed={resolvedTheme === "light"}
        aria-label="Light theme"
        className={`rounded-full p-1.5 ${resolvedTheme === "light" ? "bg-white text-neutral-950 shadow-sm" : "text-neutral-500 hover:text-neutral-950 dark:hover:text-neutral-50"}`}
      >
        <Sun className="h-4 w-4" />
      </button>
      <button
        onClick={() => setTheme("dark")}
        aria-pressed={resolvedTheme === "dark"}
        aria-label="Dark theme"
        className={`rounded-full p-1.5 ${resolvedTheme === "dark" ? "bg-neutral-800 text-neutral-50 shadow-sm" : "text-neutral-500 hover:text-neutral-950 dark:hover:text-neutral-50"}`}
      >
        <Moon className="h-4 w-4" />
      </button>
    </div>
  );
}

function Notifications() {
  const documents = useChatStore((s) => s.documents);
  const usage = useUsage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const items = useMemo(() => {
    const out: { href: string; text: string; tone: "bad" | "info" }[] = [];
    if (usage?.has_pending_reviews) out.push({ href: "/review", text: "You have flashcards due for review today", tone: "info" });
    for (const d of documents.filter((x) => x.status === "failed").slice(0, 4))
      out.push({ href: "/documents", text: `“${d.filename}” couldn't be processed`, tone: "bad" });
    const processing = documents.filter((d) => !isReady(d) && d.status !== "failed").length;
    if (processing) out.push({ href: "/documents", text: `${processing} document${processing > 1 ? "s are" : " is"} still processing`, tone: "info" });
    return out;
  }, [documents, usage]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex h-9 w-9 items-center justify-center rounded-full border border-neutral-200 bg-neutral-50 text-neutral-700 hover:bg-white dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
        aria-label={`Notifications${items.length ? ` (${items.length})` : ""}`}
        aria-expanded={open}
      >
        <Bell className="h-4 w-4" />
        {items.length > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-coral ring-2 ring-neutral-50 dark:ring-neutral-900" />}
      </button>
      {open && (
        <div className="absolute right-0 top-12 z-50 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-xl dark:border-neutral-800 dark:bg-neutral-900">
          <p className="border-b border-neutral-100 px-4 py-3 text-sm font-semibold dark:border-neutral-800">Notifications</p>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-neutral-500">You&apos;re all caught up.</p>
          ) : (
            <ul>
              {items.map((it, i) => (
                <li key={i}>
                  <Link
                    href={it.href}
                    onClick={() => setOpen(false)}
                    className="flex items-start gap-2.5 px-4 py-3 text-sm text-neutral-700 hover:bg-neutral-50 dark:text-neutral-200 dark:hover:bg-neutral-800"
                  >
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${it.tone === "bad" ? "bg-red-600" : "bg-neutral-400"}`} />
                    {it.text}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function GlobalSearch() {
  const router = useRouter();
  const documents = useChatStore((s) => s.documents);
  const createChat = useChatStore((s) => s.createChat);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [asking, setAsking] = useState(false);
  const query = q.trim();

  function searchDocs() {
    setOpen(false);
    router.push(query ? `/documents?q=${encodeURIComponent(query)}` : "/documents");
  }

  async function askAi() {
    const ready = documents.filter(isReady).map((d) => d.id);
    if (!query) return;
    if (!ready.length) {
      router.push("/documents");
      return;
    }
    setAsking(true);
    try {
      const id = await createChat(ready, query.slice(0, 60));
      setQ("");
      setOpen(false);
      router.push(`/chat/${id}?q=${encodeURIComponent(query)}`);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="relative min-w-0 flex-1 max-w-xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (query.endsWith("?")) void askAi();
          else searchDocs();
        }}
        className="flex h-10 items-center gap-2.5 rounded-lg border border-neutral-200 bg-white px-3.5 focus-within:border-coral focus-within:ring-[3px] focus-within:ring-coral/15 dark:border-neutral-800 dark:bg-neutral-900"
      >
        <Search className="h-4 w-4 shrink-0 text-neutral-500" />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(!!e.target.value.trim());
          }}
          onFocus={() => setOpen(!!q.trim())}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search your documents or ask a question..."
          aria-label="Search your documents or ask a question"
          className="min-w-0 flex-1 bg-transparent text-sm text-neutral-900 outline-none placeholder:text-neutral-400 dark:text-neutral-100"
        />
      </form>
      {open && query && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl border border-neutral-200 bg-white py-1 shadow-xl dark:border-neutral-800 dark:bg-neutral-900">
          <button onMouseDown={(e) => e.preventDefault()} onClick={searchDocs} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-neutral-50 dark:hover:bg-neutral-800">
            <FileText className="h-4 w-4 text-neutral-500" /> Find documents matching “{query}”
          </button>
          <button onMouseDown={(e) => e.preventDefault()} onClick={askAi} disabled={asking} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-neutral-50 disabled:opacity-60 dark:hover:bg-neutral-800">
            <Sparkles className="h-4 w-4 text-neutral-500" /> Ask AI across all your documents
          </button>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const me = useMe();
  const [drawer, setDrawer] = useState(false);
  const loadChats = useChatStore((s) => s.loadChats);
  const loadDocuments = useChatStore((s) => s.loadDocuments);
  const loadFolders = useChatStore((s) => s.loadFolders);
  const loadWorkspaces = useChatStore((s) => s.loadWorkspaces);
  const loadPreferences = useChatStore((s) => s.loadPreferences);

  // The shell owns the app-wide data the old sidebar used to load.
  useEffect(() => {
    loadChats().catch(() => {});
    loadDocuments().catch(() => {});
    loadFolders().catch(() => {});
    loadWorkspaces().catch(() => {});
    loadPreferences().catch(() => {});
  }, [loadChats, loadDocuments, loadFolders, loadWorkspaces, loadPreferences]);

  // Close the phone drawer on navigation.
  const [lastPath, setLastPath] = useState(pathname);
  if (lastPath !== pathname) {
    setLastPath(pathname);
    setDrawer(false);
  }

  return (
    <div className="flex min-h-0 flex-1 bg-neutral-100 dark:bg-neutral-950">
      <aside className="hidden w-[232px] shrink-0 lg:block">
        <NavRail />
      </aside>
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-black/40" aria-label="Close menu" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] shadow-2xl">
            <NavRail onNavigate={() => setDrawer(false)} />
          </aside>
          <button onClick={() => setDrawer(false)} className="absolute left-[min(18rem,85vw)] top-4 ml-2 rounded-full bg-white p-2 text-neutral-900" aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-neutral-200 bg-neutral-50/80 px-4 backdrop-blur sm:px-6 dark:border-neutral-800 dark:bg-neutral-950/80">
          <button
            onClick={() => setDrawer(true)}
            className="rounded-full p-2 text-neutral-700 hover:bg-neutral-200 lg:hidden dark:text-neutral-200 dark:hover:bg-neutral-800"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <span className="hidden sm:block">
              <ThemeToggle />
            </span>
            <Notifications />
            <Link
              href="/settings"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-neutral-950 text-[13px] font-semibold text-neutral-50 dark:bg-neutral-50 dark:text-neutral-950"
              aria-label="Account settings"
              title={me?.name}
            >
              {initial(me?.name)}
            </Link>
          </div>
        </header>
        <div className="flex min-h-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
