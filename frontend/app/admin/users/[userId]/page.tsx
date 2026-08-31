"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Copy, Loader2, Pencil } from "lucide-react";
import { adminApi, AdminApiError } from "@/lib/admin-api";

interface AdminUserDetail {
  id: string;
  name: string;
  email: string;
  is_verified: boolean;
  is_blocked: boolean;
  blocked_reason: string | null;
  blocked_at: string | null;
  blocked_by_name: string | null;
  is_admin: boolean;
  admin_role: string | null;
  admin_notes: string | null;
  created_at: string;
  plan_id: string | null;
  plan_name: string | null;
  documents: { id: string; filename: string; status: string; created_at: string }[];
  chats: { id: string; title: string | null; message_count: number; created_at: string }[];
  workspace_names: string[];
  quiz_attempts: { quiz_title: string; score: number; taken_at: string }[];
  recent_queries: { question: string; was_answered: boolean; created_at: string }[];
}

interface RecentError {
  kind: string;
  detail: string;
  created_at: string;
}
interface ActivityItem {
  kind: string;
  detail: string;
  created_at: string;
}

interface Plan {
  id: string;
  name: string;
  slug: string;
}

interface QuotaUsageItem {
  key: string;
  label: string;
  limit: number | boolean | null;
  current_usage: number;
  resets_in_seconds: number | null;
  resets_in_human: string | null;
}

interface UserLimitsResponse {
  plan_id: string | null;
  plan_name: string | null;
  custom_limits: Record<string, number | boolean | null> | null;
  effective_limits: Record<string, number | boolean | null>;
  usage: QuotaUsageItem[];
}

type Tab = "documents" | "chats" | "quizzes" | "limits" | "support";

const FRONTEND_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

export default function AdminUserDetailPage({ params }: { params: Promise<{ userId: string }> }) {
  const { userId } = use(params);
  const router = useRouter();
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [errors, setErrors] = useState<RecentError[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [notes, setNotes] = useState("");
  const [tab, setTab] = useState<Tab>("documents");
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"block" | "unblock" | "delete" | "impersonate" | null>(null);
  const [reasonInput, setReasonInput] = useState("");
  const [deleteConfirmEmail, setDeleteConfirmEmail] = useState("");

  const [plans, setPlans] = useState<Plan[]>([]);
  const [limits, setLimits] = useState<UserLimitsResponse | null>(null);
  const [limitsLoading, setLimitsLoading] = useState(false);
  const [editingLimitKey, setEditingLimitKey] = useState<string | null>(null);
  const [editingLimitValue, setEditingLimitValue] = useState("");
  const [limitsBusy, setLimitsBusy] = useState(false);

  function load() {
    setLoading(true);
    Promise.all([
      adminApi.get<AdminUserDetail>(`/admin/users/${userId}`),
      adminApi.get<RecentError[]>(`/admin/users/${userId}/recent-errors`),
      adminApi.get<ActivityItem[]>(`/admin/users/${userId}/recent-activity`),
    ])
      .then(([u, e, a]) => {
        setUser(u);
        setNotes(u.admin_notes || "");
        setErrors(e);
        setActivity(a);
      })
      .catch((err) => setActionError(err instanceof Error ? err.message : "Couldn't load user."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  function loadLimits() {
    setLimitsLoading(true);
    Promise.all([
      adminApi.get<Plan[]>("/admin/plans"),
      adminApi.get<UserLimitsResponse>(`/admin/users/${userId}/limits`),
    ])
      .then(([p, l]) => {
        setPlans(p);
        setLimits(l);
      })
      .catch((err) => setActionError(err instanceof AdminApiError ? err.detail : "Couldn't load limits."))
      .finally(() => setLimitsLoading(false));
  }

  useEffect(() => {
    if (tab === "limits") {
      loadLimits();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function handleChangePlan(planId: string) {
    setLimitsBusy(true);
    try {
      await adminApi.patch(`/admin/users/${userId}/plan`, { plan_id: planId });
      loadLimits();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Couldn't change plan.");
    } finally {
      setLimitsBusy(false);
    }
  }

  async function handleSaveCustomLimit(key: string) {
    const trimmed = editingLimitValue.trim();
    let value: number | boolean | null;
    if (trimmed === "") value = null;
    else if (trimmed === "true" || trimmed === "false") value = trimmed === "true";
    else {
      const n = Number(trimmed);
      if (Number.isNaN(n)) {
        setActionError("Enter a number, true/false, or leave blank for unlimited.");
        return;
      }
      value = n;
    }
    setLimitsBusy(true);
    try {
      await adminApi.patch(`/admin/users/${userId}/custom-limits`, { custom_limits: { [key]: value } });
      setEditingLimitKey(null);
      loadLimits();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Couldn't save override.");
    } finally {
      setLimitsBusy(false);
    }
  }

  async function handleClearCustomLimits() {
    setLimitsBusy(true);
    try {
      await adminApi.delete(`/admin/users/${userId}/custom-limits`);
      loadLimits();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Couldn't clear overrides.");
    } finally {
      setLimitsBusy(false);
    }
  }

  async function handleResetUsage() {
    if (!window.confirm("Reset this user's usage counters? This clears their rate-limit history immediately.")) return;
    setLimitsBusy(true);
    try {
      await adminApi.post(`/admin/users/${userId}/reset-usage`);
      loadLimits();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Couldn't reset usage.");
    } finally {
      setLimitsBusy(false);
    }
  }

  async function handleVerify() {
    setBusy(true);
    try {
      await adminApi.post(`/admin/users/${userId}/verify`);
      load();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleBlock() {
    setBusy(true);
    try {
      await adminApi.post(`/admin/users/${userId}/block`, { reason: reasonInput });
      setConfirmAction(null);
      setReasonInput("");
      load();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUnblock() {
    setBusy(true);
    try {
      await adminApi.post(`/admin/users/${userId}/unblock`);
      setConfirmAction(null);
      load();
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    try {
      await adminApi.delete(`/admin/users/${userId}`, { confirm_email: deleteConfirmEmail });
      router.push("/admin/users");
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Action failed.");
      setBusy(false);
    }
  }

  async function handleImpersonate() {
    setBusy(true);
    // Open the tab synchronously, in direct response to the click — opening it only
    // after the await below resolves breaks the user-gesture chain and gets silently
    // popup-blocked in most browsers.
    const newTab = window.open("about:blank", "_blank");
    try {
      const data = await adminApi.post<{ access_token: string; user_email: string }>(
        `/admin/users/${userId}/impersonate`
      );
      const url = `${FRONTEND_URL}/impersonate?token=${encodeURIComponent(data.access_token)}&email=${encodeURIComponent(
        data.user_email
      )}`;
      if (newTab) {
        newTab.location.href = url;
      } else {
        window.open(url, "_blank");
      }
      setConfirmAction(null);
    } catch (err) {
      newTab?.close();
      setActionError(err instanceof AdminApiError ? err.detail : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveNotes() {
    setBusy(true);
    try {
      await adminApi.patch(`/admin/users/${userId}/notes`, { notes });
    } catch (err) {
      setActionError(err instanceof AdminApiError ? err.detail : "Couldn't save notes.");
    } finally {
      setBusy(false);
    }
  }

  function copyDebugInfo() {
    const text = `User ID: ${userId}\nEmail: ${user?.email}\nRecent errors:\n${errors
      .slice(0, 5)
      .map((e) => `- ${e.detail}`)
      .join("\n")}`;
    navigator.clipboard.writeText(text);
  }

  if (loading) return <div className="max-w-4xl mx-auto px-6 py-8 text-sm text-neutral-400">Loading...</div>;
  if (!user) return <div className="max-w-4xl mx-auto px-6 py-8 text-sm text-red-600">User not found.</div>;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <button
        onClick={() => router.push("/admin/users")}
        className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-4"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to users
      </button>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
            {user.name}
          </h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">{user.email}</p>
          <div className="flex items-center gap-2 mt-2">
            {user.is_blocked && (
              <span className="text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 rounded-full px-2 py-0.5">
                Blocked
              </span>
            )}
            {!user.is_verified && (
              <span className="text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 rounded-full px-2 py-0.5">
                Unverified
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          {!user.is_verified && (
            <button
              onClick={handleVerify}
              disabled={busy}
              className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800"
            >
              Verify
            </button>
          )}
          {user.is_blocked ? (
            <button
              onClick={() => setConfirmAction("unblock")}
              className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800"
            >
              Unblock
            </button>
          ) : (
            <button
              onClick={() => setConfirmAction("block")}
              className="text-xs font-medium border border-amber-300 dark:border-amber-800 text-amber-700 dark:text-amber-400 rounded-lg px-3 py-1.5 hover:bg-amber-50 dark:hover:bg-amber-950/30"
            >
              Block
            </button>
          )}
          <button
            onClick={() => setConfirmAction("impersonate")}
            className="text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800"
          >
            Impersonate
          </button>
          <button
            onClick={() => setConfirmAction("delete")}
            className="text-xs font-medium border border-red-300 dark:border-red-900 text-red-600 dark:text-red-400 rounded-lg px-3 py-1.5 hover:bg-red-50 dark:hover:bg-red-950/30"
          >
            Delete
          </button>
        </div>
      </div>

      {actionError && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{actionError}</p>}

      <div className="flex gap-1 border-b border-neutral-200 dark:border-neutral-800 mb-4">
        {(["documents", "chats", "quizzes", "limits", "support"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-sm px-3 py-2 border-b-2 -mb-px capitalize transition-colors ${
              tab === t
                ? "border-neutral-900 dark:border-neutral-100 text-neutral-900 dark:text-neutral-100 font-medium"
                : "border-transparent text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
            }`}
          >
            {t === "limits" ? "Limits & Usage" : t}
          </button>
        ))}
      </div>

      {tab === "documents" && (
        <div className="space-y-1.5">
          {user.documents.map((d) => (
            <div key={d.id} className="flex items-center justify-between text-sm px-3 py-2 rounded-lg bg-neutral-50 dark:bg-neutral-900">
              <span className="text-neutral-800 dark:text-neutral-200 truncate">{d.filename}</span>
              <span className="text-xs text-neutral-400 shrink-0 ml-2">{d.status}</span>
            </div>
          ))}
          {user.documents.length === 0 && <p className="text-sm text-neutral-400">No documents.</p>}
        </div>
      )}

      {tab === "chats" && (
        <div className="space-y-1.5">
          {user.chats.map((c) => (
            <div key={c.id} className="flex items-center justify-between text-sm px-3 py-2 rounded-lg bg-neutral-50 dark:bg-neutral-900">
              <span className="text-neutral-800 dark:text-neutral-200 truncate">{c.title || "Untitled chat"}</span>
              <span className="text-xs text-neutral-400 shrink-0 ml-2">{c.message_count} messages</span>
            </div>
          ))}
          {user.chats.length === 0 && <p className="text-sm text-neutral-400">No chats.</p>}
        </div>
      )}

      {tab === "quizzes" && (
        <div className="space-y-1.5">
          {user.quiz_attempts.map((q, i) => (
            <div key={i} className="flex items-center justify-between text-sm px-3 py-2 rounded-lg bg-neutral-50 dark:bg-neutral-900">
              <span className="text-neutral-800 dark:text-neutral-200 truncate">{q.quiz_title}</span>
              <span className="text-xs text-neutral-400 shrink-0 ml-2">{q.score}%</span>
            </div>
          ))}
          {user.quiz_attempts.length === 0 && <p className="text-sm text-neutral-400">No quiz attempts.</p>}
        </div>
      )}

      {tab === "limits" && (
        <div className="space-y-6">
          {limitsLoading && !limits && <p className="text-sm text-neutral-400">Loading...</p>}

          {limits && (
            <>
              <div>
                <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">Plan</p>
                <select
                  value={limits.plan_id || ""}
                  onChange={(e) => handleChangePlan(e.target.value)}
                  disabled={limitsBusy}
                  className="text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                >
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Quotas</p>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={loadLimits}
                      disabled={limitsLoading}
                      className="text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                    >
                      {limitsLoading ? "Refreshing..." : "Refresh"}
                    </button>
                    {limits.custom_limits && Object.keys(limits.custom_limits).length > 0 && (
                      <button
                        onClick={handleClearCustomLimits}
                        disabled={limitsBusy}
                        className="text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                      >
                        Clear overrides
                      </button>
                    )}
                    <button
                      onClick={handleResetUsage}
                      disabled={limitsBusy}
                      className="text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                    >
                      Reset usage now
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900">
                        <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-3 py-2">Quota</th>
                        <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-3 py-2">Limit</th>
                        <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-3 py-2">Usage</th>
                        <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-3 py-2">Resets in</th>
                      </tr>
                    </thead>
                    <tbody>
                      {limits.usage.map((item) => {
                        const isEditing = editingLimitKey === item.key;
                        const hasOverride = limits.custom_limits && item.key in limits.custom_limits;
                        return (
                          <tr key={item.key} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
                            <td className="px-3 py-2 text-neutral-600 dark:text-neutral-400">{item.label}</td>
                            <td className="px-3 py-2">
                              {isEditing ? (
                                <input
                                  autoFocus
                                  defaultValue={item.limit === null ? "" : String(item.limit)}
                                  onChange={(e) => setEditingLimitValue(e.target.value)}
                                  onBlur={() => handleSaveCustomLimit(item.key)}
                                  onKeyDown={(e) => e.key === "Enter" && handleSaveCustomLimit(item.key)}
                                  placeholder="Unlimited"
                                  className="w-24 text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                                />
                              ) : (
                                <button
                                  onClick={() => {
                                    setEditingLimitKey(item.key);
                                    setEditingLimitValue(item.limit === null ? "" : String(item.limit));
                                  }}
                                  className="group flex items-center gap-1.5 text-neutral-800 dark:text-neutral-200"
                                >
                                  {item.limit === null ? "Unlimited" : String(item.limit)}
                                  {hasOverride && (
                                    <span className="text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 rounded-full px-1.5 py-0.5">
                                      Override
                                    </span>
                                  )}
                                  <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-100 text-neutral-400 transition-opacity" />
                                </button>
                              )}
                            </td>
                            <td className="px-3 py-2 text-neutral-800 dark:text-neutral-200">{item.current_usage}</td>
                            <td className="px-3 py-2 text-neutral-400 dark:text-neutral-500">
                              {item.resets_in_human || "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">Block history</p>
                {user.is_blocked ? (
                  <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/20">
                    Blocked {user.blocked_at && `on ${new Date(user.blocked_at).toLocaleString()}`}
                    {user.blocked_by_name && ` by ${user.blocked_by_name}`}
                    {user.blocked_reason && ` — "${user.blocked_reason}"`}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-400">Not currently blocked.</p>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "support" && (
        <div className="space-y-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Admin notes</p>
              <button onClick={handleSaveNotes} disabled={busy} className="text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200">
                Save
              </button>
            </div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Internal notes for support context..."
              className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Recent errors</p>
              <button onClick={copyDebugInfo} className="flex items-center gap-1 text-xs font-medium text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200">
                <Copy className="h-3 w-3" />
                Copy debug info
              </button>
            </div>
            <div className="space-y-1">
              {errors.map((e, i) => (
                <p key={i} className="text-xs text-red-600 dark:text-red-400 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-950/20">
                  {e.detail}
                </p>
              ))}
              {errors.length === 0 && <p className="text-sm text-neutral-400">No recent errors.</p>}
            </div>
          </div>

          <div>
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">Recent activity</p>
            <div className="space-y-1">
              {activity.map((a, i) => (
                <div key={i} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-neutral-50 dark:bg-neutral-900">
                  <span className="text-neutral-600 dark:text-neutral-400 truncate">
                    <span className="font-medium text-neutral-800 dark:text-neutral-200">{a.kind}</span>: {a.detail}
                  </span>
                  <span className="text-neutral-400 shrink-0 ml-2">{new Date(a.created_at).toLocaleString()}</span>
                </div>
              ))}
              {activity.length === 0 && <p className="text-sm text-neutral-400">No recent activity.</p>}
            </div>
          </div>
        </div>
      )}

      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => setConfirmAction(null)}>
          <div
            className="w-full max-w-sm bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 p-5"
            onClick={(e) => e.stopPropagation()}
          >
            {confirmAction === "block" && (
              <>
                <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-2">Block this user?</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">
                  They will be immediately unable to log in or use the app. Their data is preserved, not deleted.
                </p>
                <input
                  value={reasonInput}
                  onChange={(e) => setReasonInput(e.target.value)}
                  placeholder="Reason (required)"
                  className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 mb-3 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                />
                <div className="flex gap-2">
                  <button onClick={() => setConfirmAction(null)} className="flex-1 text-sm border border-neutral-300 dark:border-neutral-700 rounded-lg py-2">
                    Cancel
                  </button>
                  <button
                    onClick={handleBlock}
                    disabled={busy || !reasonInput.trim()}
                    className="flex-1 text-sm bg-amber-600 text-white rounded-lg py-2 disabled:opacity-50 flex items-center justify-center gap-1.5"
                  >
                    {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Block
                  </button>
                </div>
              </>
            )}
            {confirmAction === "unblock" && (
              <>
                <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-2">Unblock this user?</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">They will be able to log in again immediately.</p>
                <div className="flex gap-2">
                  <button onClick={() => setConfirmAction(null)} className="flex-1 text-sm border border-neutral-300 dark:border-neutral-700 rounded-lg py-2">
                    Cancel
                  </button>
                  <button onClick={handleUnblock} disabled={busy} className="flex-1 text-sm bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2">
                    Unblock
                  </button>
                </div>
              </>
            )}
            {confirmAction === "impersonate" && (
              <>
                <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-2">Impersonate this user?</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">
                  Opens the app as this user in a new tab for 10 minutes, read-only (no sending messages or deleting
                  documents). This is logged.
                </p>
                <div className="flex gap-2">
                  <button onClick={() => setConfirmAction(null)} className="flex-1 text-sm border border-neutral-300 dark:border-neutral-700 rounded-lg py-2">
                    Cancel
                  </button>
                  <button onClick={handleImpersonate} disabled={busy} className="flex-1 text-sm bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg py-2">
                    Impersonate
                  </button>
                </div>
              </>
            )}
            {confirmAction === "delete" && (
              <>
                <p className="text-sm font-medium text-red-600 dark:text-red-400 mb-2">Permanently delete this account?</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">
                  This deletes all documents, chats, quizzes, and data for {user.email}. This cannot be undone. Type
                  their email to confirm.
                </p>
                <input
                  value={deleteConfirmEmail}
                  onChange={(e) => setDeleteConfirmEmail(e.target.value)}
                  placeholder={user.email}
                  className="w-full text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 mb-3 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-red-500"
                />
                <div className="flex gap-2">
                  <button onClick={() => setConfirmAction(null)} className="flex-1 text-sm border border-neutral-300 dark:border-neutral-700 rounded-lg py-2">
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={busy || deleteConfirmEmail.trim().toLowerCase() !== user.email.toLowerCase()}
                    className="flex-1 text-sm bg-red-600 text-white rounded-lg py-2 disabled:opacity-40 flex items-center justify-center gap-1.5"
                  >
                    {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Delete permanently
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
