"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export const IMPERSONATION_EMAIL_KEY = "echolearn_impersonating_email";

export default function ImpersonatePage() {
  const router = useRouter();
  const params = useSearchParams();
  const { login } = useAuth();

  useEffect(() => {
    const token = params.get("token");
    const email = params.get("email");
    if (token) {
      login(token);
      try {
        sessionStorage.setItem(IMPERSONATION_EMAIL_KEY, email || "");
      } catch {
        // ignore
      }
    }
    router.replace("/chat");
  }, [params, login, router]);

  return null;
}
