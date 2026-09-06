"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { adminApi } from "@/lib/admin-api";

interface AdminUserListItem {
  id: string;
  name: string;
  email: string;
  is_verified: boolean;
  is_blocked: boolean;
  is_admin: boolean;
  created_at: string;
  last_active: string | null;
  document_count: number;
  message_count: number;
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      adminApi
        .get<AdminUserListItem[]>(`/admin/users/${qs}`)
        .then(setUsers)
        .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load users."))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">Users</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        Search, review, and manage EchoLearn user accounts.
      </p>

      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by name or email"
          className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent pl-9 pr-3 py-2 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
        />
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}
      {loading && <p className="text-sm text-neutral-400 dark:text-neutral-500">Loading...</p>}

      {!loading && (
        <div className="border border-neutral-200 dark:border-neutral-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-neutral-50 dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-800">
                <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-2.5">Name</th>
                <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-2.5">Email</th>
                <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-2.5">Status</th>
                <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-2.5">Docs</th>
                <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-2.5">Messages</th>
                <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-2.5">Joined</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/admin/users/${user.id}`}
                      className="text-neutral-900 dark:text-neutral-100 font-medium hover:underline"
                    >
                      {user.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-neutral-600 dark:text-neutral-400">{user.email}</td>
                  <td className="px-4 py-2.5">
                    {user.is_blocked ? (
                      <span className="text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 rounded-full px-2 py-0.5">
                        Blocked
                      </span>
                    ) : user.is_verified ? (
                      <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 rounded-full px-2 py-0.5">
                        Verified
                      </span>
                    ) : (
                      <span className="text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 rounded-full px-2 py-0.5">
                        Unverified
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-neutral-600 dark:text-neutral-400">{user.document_count}</td>
                  <td className="px-4 py-2.5 text-neutral-600 dark:text-neutral-400">{user.message_count}</td>
                  <td className="px-4 py-2.5 text-neutral-400 dark:text-neutral-500">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <p className="text-sm text-neutral-400 dark:text-neutral-500 px-4 py-6 text-center">No users found.</p>
          )}
        </div>
      )}
    </div>
  );
}
