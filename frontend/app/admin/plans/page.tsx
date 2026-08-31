"use client";

import { useEffect, useState } from "react";
import { Loader2, Pencil } from "lucide-react";
import { adminApi, AdminApiError } from "@/lib/admin-api";

interface PlanLimits {
  max_documents: number | null;
  max_file_size_mb: number | null;
  max_audio_video_minutes: number | null;
  messages_per_window: number | null;
  message_window_hours: number;
  max_workspaces: number | null;
  quiz_generations_per_month: number | null;
  tts_uses_per_day: number | null;
  diagrams_infographics_per_month: number | null;
  max_storage_mb: number | null;
  priority_processing: boolean;
}

interface Plan {
  id: string;
  name: string;
  slug: string;
  is_default: boolean;
  limits: PlanLimits;
  price_monthly: number | null;
  created_at: string;
  updated_at: string;
}

const LIMIT_ROWS: { key: keyof PlanLimits; label: string; type: "number" | "bool" }[] = [
  { key: "max_documents", label: "Max documents", type: "number" },
  { key: "max_file_size_mb", label: "Max file size (MB)", type: "number" },
  { key: "max_audio_video_minutes", label: "Max audio/video (minutes)", type: "number" },
  { key: "messages_per_window", label: "Messages per window", type: "number" },
  { key: "message_window_hours", label: "Message window (hours)", type: "number" },
  { key: "max_workspaces", label: "Max workspaces", type: "number" },
  { key: "quiz_generations_per_month", label: "Quiz generations / month", type: "number" },
  { key: "tts_uses_per_day", label: "TTS uses / day", type: "number" },
  { key: "diagrams_infographics_per_month", label: "Diagrams & infographics / month", type: "number" },
  { key: "max_storage_mb", label: "Max storage (MB)", type: "number" },
  { key: "priority_processing", label: "Priority processing", type: "bool" },
];

function formatLimit(value: number | boolean | null): string {
  if (value === null) return "Unlimited";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

export default function AdminPlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingCell, setEditingCell] = useState<{ planId: string; key: keyof PlanLimits } | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    adminApi
      .get<Plan[]>("/admin/plans")
      .then(setPlans)
      .catch((err) => setError(err instanceof AdminApiError ? err.detail : "Couldn't load plans."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit(plan: Plan, key: keyof PlanLimits) {
    const current = plan.limits[key];
    setEditingCell({ planId: plan.id, key });
    setEditValue(current === null ? "" : String(current));
  }

  async function saveEdit(plan: Plan, key: keyof PlanLimits) {
    const rowType = LIMIT_ROWS.find((r) => r.key === key)?.type;
    let value: number | boolean | null;
    if (rowType === "bool") {
      value = editValue === "true";
    } else {
      value = editValue.trim() === "" ? null : Number(editValue);
      if (value !== null && Number.isNaN(value)) {
        setError("Enter a valid number, or leave blank for unlimited.");
        return;
      }
    }

    const confirmed = window.confirm(
      `Set "${LIMIT_ROWS.find((r) => r.key === key)?.label}" for ${plan.name} to ${
        value === null ? "Unlimited" : String(value)
      }?`
    );
    if (!confirmed) {
      setEditingCell(null);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const updatedLimits = { ...plan.limits, [key]: value };
      const updated = await adminApi.patch<Plan>(`/admin/plans/${plan.id}`, { limits: updatedLimits });
      setPlans((prev) => prev.map((p) => (p.id === plan.id ? updated : p)));
      setEditingCell(null);
    } catch (err) {
      setError(err instanceof AdminApiError ? err.detail : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="max-w-5xl mx-auto px-6 py-8 text-sm text-neutral-400">Loading...</div>;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">Plans</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        Click any limit to edit it. Leave a numeric field blank to make it unlimited.
      </p>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}

      <div className="overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900">
              <th className="text-left font-medium text-neutral-500 dark:text-neutral-400 px-4 py-3">Limit</th>
              {plans.map((plan) => (
                <th key={plan.id} className="text-left font-medium text-neutral-900 dark:text-neutral-100 px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    {plan.name}
                    {plan.is_default && (
                      <span className="text-[10px] font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 rounded-full px-1.5 py-0.5">
                        Default
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-normal text-neutral-400 dark:text-neutral-500 mt-0.5">
                    {plan.price_monthly == null ? "Custom pricing" : `$${plan.price_monthly}/mo`}
                  </p>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {LIMIT_ROWS.map((row) => (
              <tr key={row.key} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
                <td className="px-4 py-2.5 text-neutral-600 dark:text-neutral-400">{row.label}</td>
                {plans.map((plan) => {
                  const isEditing = editingCell?.planId === plan.id && editingCell.key === row.key;
                  return (
                    <td key={plan.id} className="px-4 py-2.5">
                      {isEditing ? (
                        row.type === "bool" ? (
                          <select
                            autoFocus
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onBlur={() => saveEdit(plan, row.key)}
                            className="text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                          >
                            <option value="true">Yes</option>
                            <option value="false">No</option>
                          </select>
                        ) : (
                          <input
                            autoFocus
                            type="number"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onBlur={() => saveEdit(plan, row.key)}
                            onKeyDown={(e) => e.key === "Enter" && saveEdit(plan, row.key)}
                            placeholder="Unlimited"
                            disabled={saving}
                            className="w-28 text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                          />
                        )
                      ) : (
                        <button
                          onClick={() => startEdit(plan, row.key)}
                          className="group flex items-center gap-1.5 text-neutral-800 dark:text-neutral-200 hover:text-neutral-950 dark:hover:text-white transition-colors"
                        >
                          {formatLimit(plan.limits[row.key])}
                          <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-100 text-neutral-400 transition-opacity" />
                        </button>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {saving && (
        <p className="mt-3 text-xs text-neutral-400 flex items-center gap-1.5">
          <Loader2 className="h-3 w-3 animate-spin" /> Saving...
        </p>
      )}
    </div>
  );
}
