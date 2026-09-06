"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { adminApi, AdminApiError } from "@/lib/admin-api";

interface ConfigData {
  feature_flags: Record<string, boolean>;
  model_selection: Record<string, string>;
}

const FLAG_LABELS: Record<string, string> = {
  audio_upload_enabled: "Audio upload",
  video_upload_enabled: "Video upload",
  quiz_generation_enabled: "Quiz generation",
  diagram_generation_enabled: "Diagram generation",
  infographic_generation_enabled: "Infographic generation",
  voice_output_enabled: "Voice output (TTS)",
  voice_input_enabled: "Voice input (speech-to-text)",
};

export default function AdminConfigPage() {
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [draft, setDraft] = useState<ConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    adminApi
      .get<ConfigData>("/admin/config/")
      .then((data) => {
        setConfig(data);
        setDraft(JSON.parse(JSON.stringify(data)));
      })
      .catch((err) => setError(err instanceof AdminApiError ? err.detail : "Couldn't load config."))
      .finally(() => setLoading(false));
  }, []);

  async function saveSection(key: keyof ConfigData) {
    if (!draft) return;
    setSaving(key);
    setError(null);
    setMessage(null);
    try {
      await adminApi.patch("/admin/config/", { key, value: draft[key] });
      setConfig((prev) => (prev ? { ...prev, [key]: draft[key] } : prev));
      setMessage(`Saved ${key.replace(/_/g, " ")}.`);
    } catch (err) {
      setError(err instanceof AdminApiError ? err.detail : "Couldn't save changes.");
    } finally {
      setSaving(null);
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-6 py-8 text-sm text-neutral-400">Loading...</div>;
  if (!draft) return <div className="max-w-3xl mx-auto px-6 py-8 text-sm text-red-600">{error}</div>;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-1">
        Configuration
      </h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        Feature flags and model selection — changes apply immediately, no redeploy needed. Per-plan
        limits (documents, messages, storage, etc.) are managed on the{" "}
        <a href="/admin/plans" className="underline hover:text-neutral-700 dark:hover:text-neutral-200">
          Plans
        </a>{" "}
        page.
      </p>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>}
      {message && <p className="text-sm text-emerald-600 dark:text-emerald-400 mb-4">{message}</p>}

      <div className="space-y-8">
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Feature flags</p>
            <button
              onClick={() => saveSection("feature_flags")}
              disabled={saving === "feature_flags"}
              className="flex items-center gap-1.5 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-1.5 hover:bg-neutral-800 dark:hover:bg-white disabled:opacity-50"
            >
              {saving === "feature_flags" && <Loader2 className="h-3 w-3 animate-spin" />}
              Save Changes
            </button>
          </div>
          <div className="space-y-2">
            {Object.entries(draft.feature_flags).map(([key, value]) => (
              <label key={key} className="flex items-center justify-between text-sm py-1.5">
                <span className="text-neutral-700 dark:text-neutral-300">{FLAG_LABELS[key] || key}</span>
                <input
                  type="checkbox"
                  checked={value}
                  onChange={(e) =>
                    setDraft((prev) =>
                      prev ? { ...prev, feature_flags: { ...prev.feature_flags, [key]: e.target.checked } } : prev
                    )
                  }
                  className="h-4 w-4 accent-neutral-900 dark:accent-neutral-100"
                />
              </label>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">Model selection</p>
            <button
              onClick={() => saveSection("model_selection")}
              disabled={saving === "model_selection"}
              className="flex items-center gap-1.5 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-1.5 hover:bg-neutral-800 dark:hover:bg-white disabled:opacity-50"
            >
              {saving === "model_selection" && <Loader2 className="h-3 w-3 animate-spin" />}
              Save Changes
            </button>
          </div>
          <div className="space-y-2">
            {Object.entries(draft.model_selection).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-sm py-1.5">
                <span className="text-neutral-700 dark:text-neutral-300 capitalize">{key.replace(/_/g, " ")}</span>
                <select
                  value={value}
                  onChange={(e) =>
                    setDraft((prev) =>
                      prev
                        ? { ...prev, model_selection: { ...prev.model_selection, [key]: e.target.value } }
                        : prev
                    )
                  }
                  className="text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1 text-neutral-900 dark:text-neutral-100 focus:outline-none"
                >
                  <option value="groq">groq</option>
                  <option value="gemini">gemini</option>
                </select>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
