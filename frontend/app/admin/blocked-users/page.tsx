"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { adminApi, AdminApiError } from "@/lib/admin-api";

interface BlockedUser {
  id: string;
  name: string;
  email: string;
  blocked_reason: string | null;
  blocked_at: string | null;
  blocked_by_name: string | null;
  is_auto_blocked: boolean;
}

type Filter = "all" | "manual" | "auto";

export default function AdminBlockedUsersPage() {
  const [users, setUsers] = useState<BlockedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    setLoading(true);
    adminApi
      .get<BlockedUser[]>("/admin/system/blocked-users")
      .then(setUsers)
      .catch((err) => setError(err instanceof AdminApiError ? err.detail : "Couldn't load blocked users."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleUnblock(userId: string) {
    setBusyId(userId);
    try {
      await adminApi.post(`/admin/users/${userId}/unblock`);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    } catch (err) {
      setError(err instanceof AdminApiError ? err.detail : "Couldn't unblock this user.");
    } finally {
      setBusyId(null);
    }
  }

  const filtered = users.filter((u) => {
    if (filter === "manual") return !u.is_auto_blocked;
    if (filter === "auto") return u.is_auto_blocked;
    return true;
  });

  if (loading) return <div className="max-w-4xl mx-auto px-6 py-8 text-sm text-neutral-400">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
        Blocked Users
      </h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        Accounts currently blocked, either by an admin or automatically for abuse.
      </p>

      <div className="flex gap-1.5 mb-4">
        {(["all", "manual", "auto"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors capitalize ${
              filter === f
                ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}

      <div className="space-y-1.5">
        {filtered.map((u) => (
          <div
            key={u.id}
            className="flex items-center justify-between gap-3 text-sm px-3 py-2.5 rounded-lg bg-neutral-50 dark:bg-neutral-900"
          >
            <div className="min-w-0">
              <Link href={`/admin/users/${u.id}`} className="font-medium text-neutral-900 dark:text-neutral-100 hover:underline">
                {u.name}
              </Link>
              <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">{u.email}</p>
              <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-0.5">
                {u.blocked_reason || "No reason given"}
                {u.blocked_at && ` · ${new Date(u.blocked_at).toLocaleString()}`}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                  u.is_auto_blocked
                    ? "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400"
                    : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
                }`}
              >
                {u.is_auto_blocked ? "Auto (System)" : `By ${u.blocked_by_name}`}
              </span>
              <button
                onClick={() => handleUnblock(u.id)}
                disabled={busyId === u.id}
                className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-2.5 py-1 hover:bg-neutral-100 dark:hover:bg-neutral-800 flex items-center gap-1 disabled:opacity-50"
              >
                {busyId === u.id && <Loader2 className="h-3 w-3 animate-spin" />}
                Unblock
              </button>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <p className="text-sm text-neutral-400">No blocked users.</p>}
      </div>
    </div>
  );
}
