"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UserCog } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { IMPERSONATION_EMAIL_KEY } from "./impersonate/page";

export default function ChatSectionLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();
  const [impersonatingEmail, setImpersonatingEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    try {
      setImpersonatingEmail(sessionStorage.getItem(IMPERSONATION_EMAIL_KEY));
    } catch {
      setImpersonatingEmail(null);
    }
  }, []);

  function endImpersonation() {
    try {
      sessionStorage.removeItem(IMPERSONATION_EMAIL_KEY);
    } catch {
      // ignore
    }
    logout();
    router.replace("/login");
    window.close();
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white dark:bg-neutral-950">
        <div className="h-6 w-6 rounded-full border-2 border-neutral-200 dark:border-neutral-800 border-t-neutral-900 dark:border-t-neutral-100 animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-white dark:bg-neutral-950">
      {impersonatingEmail && (
        <div className="shrink-0 bg-amber-500 text-neutral-900 px-4 py-2 flex items-center justify-center gap-3 text-xs font-semibold">
          <UserCog className="h-3.5 w-3.5" />
          Impersonating {impersonatingEmail} — actions are read-only
          <button
            onClick={endImpersonation}
            className="underline underline-offset-2 hover:no-underline"
          >
            End Session
          </button>
        </div>
      )}
      <div className="flex flex-1 min-h-0">{children}</div>
    </div>
  );
}
