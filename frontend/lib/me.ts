"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface Me {
  id: string;
  name: string;
  email: string;
  plan_name: string | null;
  is_admin: boolean;
}

// One request per page load, shared by every component that asks (shell, dashboard).
let cached: Promise<Me | null> | null = null;

export function clearMe() {
  cached = null;
}

export function useMe(): Me | null {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    if (!cached) cached = api.get<Me>("/users/me", { auth: true }).catch(() => null);
    let alive = true;
    cached.then((m) => alive && setMe(m));
    return () => {
      alive = false;
    };
  }, []);
  return me;
}

export function firstName(name: string | undefined | null): string {
  return (name || "").trim().split(/\s+/)[0] || "there";
}

export function initial(name: string | undefined | null): string {
  return ((name || "").trim()[0] || "?").toUpperCase();
}
