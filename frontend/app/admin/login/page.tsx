"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldAlert, Loader2 } from "lucide-react";
import { adminApi, AdminApiError } from "@/lib/admin-api";
import { useAdminAuth } from "@/lib/admin-auth-context";

export default function AdminLoginPage() {
  const router = useRouter();
  const { login } = useAdminAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await adminApi.post<{
        access_token: string;
        name: string;
        email: string;
        admin_role: string | null;
      }>("/admin/auth/login", { email, password });
      login(data.access_token, { id: "", name: data.name, email: data.email, admin_role: data.admin_role });
      router.push("/admin/users");
    } catch (err) {
      setError(err instanceof AdminApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white dark:bg-neutral-950 px-6">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8 justify-center text-neutral-900 dark:text-neutral-100">
          <ShieldAlert className="h-5 w-5" />
          <span className="text-lg font-semibold tracking-tight">EchoLearn Admin</span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5 block">
              Admin email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1.5 block">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
            />
          </div>

          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-sm font-medium rounded-lg py-2.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Log in
          </button>
        </form>

        <p className="text-xs text-neutral-400 dark:text-neutral-500 text-center mt-6">
          Admin access only. This is a separate login from the regular EchoLearn app.
        </p>
      </div>
    </div>
  );
}
