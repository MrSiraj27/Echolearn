"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Trash2, Upload, Loader2, Check } from "lucide-react";
import { clearClonedAudioCache } from "@/components/ListenButton";
import { api, ApiError, authFetch } from "@/lib/api";
import { useSpeech } from "@/lib/speech-context";
import { useChatStore } from "@/lib/chat-store";
import { AppLanguage, ReviewSettingsResponse } from "@/lib/types";
import VoiceSampleRecorder, { MAX_SAMPLE_SECONDS, MIN_SAMPLE_SECONDS } from "@/components/VoiceSampleRecorder";


interface MyUsageResponse {
  quotas: { key: string; limit: number | boolean | null; current_usage: number; resets_in_human: string | null }[];
  has_voice_sample: boolean;
}

export default function SettingsPage() {
  const router = useRouter();
  const { refreshVoiceSample, browserVoices, browserVoiceURI, setBrowserVoiceURI, serverVoiceAvailable } =
    useSpeech();
  const [usage, setUsage] = useState<MyUsageResponse | null>(null);
  const [hasSample, setHasSample] = useState(false);
  const [loading, setLoading] = useState(true);
  const [replacing, setReplacing] = useState(false);
  const [deletingSample, setDeletingSample] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [cloneAvailable, setCloneAvailable] = useState(true);
  const [pregenerate, setPregenerate] = useState(false);

  const preferredLanguage = useChatStore((s) => s.preferredLanguage);
  const loadPreferences = useChatStore((s) => s.loadPreferences);
  const setPreferredLanguage = useChatStore((s) => s.setPreferredLanguage);
  const [languageError, setLanguageError] = useState<string | null>(null);

  const [dailyCap, setDailyCap] = useState<number | null>(null);
  const [dailyCapInput, setDailyCapInput] = useState("");
  const [savingCap, setSavingCap] = useState(false);
  const [capSaved, setCapSaved] = useState(false);

  function loadUsage() {
    api
      .get<MyUsageResponse>("/users/me/usage", { auth: true })
      .then((data) => {
        setUsage(data);
        setHasSample(data.has_voice_sample);
        if (data.has_voice_sample) {
          void loadPreview();
          api
            .get<{ pregenerate: boolean }>("/voice/sample", { auth: true })
            .then((r) => setPregenerate(r.pregenerate))
            .catch(() => {});
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  async function loadPreview() {
    try {
      const res = await authFetch("/voice/sample/audio");
      if (!res.ok) return;
      const url = URL.createObjectURL(await res.blob());
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return url;
      });
    } catch {
      // preview is a convenience; ignore
    }
  }

  useEffect(() => {
    loadUsage();
    api
      .get<{ available: boolean }>("/voice/clone-availability", { auth: true })
      .then((r) => setCloneAvailable(r.available))
      .catch(() => {});
    api
      .get<ReviewSettingsResponse>("/review/settings", { auth: true })
      .then((s) => {
        setDailyCap(s.daily_cap);
        setDailyCapInput(String(s.daily_cap));
      })
      .catch(() => {});
  }, []);

  async function saveDailyCap() {
    const n = parseInt(dailyCapInput, 10);
    if (isNaN(n) || n < 5 || n > 50) return;
    setSavingCap(true);
    try {
      const res = await api.patch<ReviewSettingsResponse>("/review/settings", { daily_cap: n }, { auth: true });
      setDailyCap(res.daily_cap);
      setCapSaved(true);
      setTimeout(() => setCapSaved(false), 1500);
    } finally {
      setSavingCap(false);
    }
  }

  useEffect(() => {
    loadPreferences().catch(() => {});
  }, [loadPreferences]);

  async function chooseLanguage(language: AppLanguage) {
    setLanguageError(null);
    try {
      await setPreferredLanguage(language);
    } catch {
      setLanguageError("Couldn't save that setting. Please try again.");
    }
  }

  const languageQuota = usage?.quotas.find((q) => q.key === "language_explanations_per_day");
  const cloneQuota = usage?.quotas.find((q) => q.key === "voice_clone_uses_per_day");
  const cloningLocked = cloneQuota ? cloneQuota.limit === 0 : false;

  /** Called by VoiceSampleRecorder with a validated WAV after the user ticked the consent box. */
  async function uploadSample(wav: Blob) {
    setError(null);
    const formData = new FormData();
    formData.append("file", new File([wav], "voice_sample.wav", { type: "audio/wav" }));
    formData.append("consent", "true");
    let res: Response;
    try {
      res = await authFetch("/voice/upload-sample", { method: "POST", body: formData });
    } catch {
      throw new Error("Couldn't reach the server. Check your connection and try again.");
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new ApiError(res.status, data.detail || "Upload failed. Please try again.");
    }
    setPreviewUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(wav);
    });
    setHasSample(true);
    setReplacing(false);
    clearClonedAudioCache();
    loadUsage();
    refreshVoiceSample();
  }

  async function togglePregenerate() {
    const next = !pregenerate;
    setPregenerate(next);
    try {
      await api.patch("/voice/pregenerate", { enabled: next }, { auth: true });
    } catch {
      setPregenerate(!next);
      setError("Couldn't save that setting. Please try again.");
    }
  }

  async function deleteSample() {
    setDeletingSample(true);
    try {
      await api.delete("/voice/sample", { auth: true });
      setHasSample(false);
      clearClonedAudioCache();
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });
      refreshVoiceSample();
    } catch {
      setError("Couldn't delete your sample. Please try again.");
    } finally {
      setDeletingSample(false);
    }
  }

  return (
    <>
      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 mb-6"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 mb-2">Settings</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-8">Manage your account preferences.</p>

          <section id="voice" className="scroll-mt-6 rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 mb-6">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">Read-Aloud Voice</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-4">
              {serverVoiceAvailable === false
                ? "Answers are read aloud using your device's own voices. Pick one below."
                : "Used when the server voice is unavailable, or on devices (like most phones) where it's used by default."}
            </p>
            {browserVoices.length > 0 ? (
              <select
                value={browserVoiceURI ?? ""}
                onChange={(e) => setBrowserVoiceURI(e.target.value || null)}
                className="w-full text-sm border border-neutral-300 dark:border-neutral-700 dark:bg-neutral-900 rounded-lg px-3 py-2"
              >
                <option value="">Auto (best available)</option>
                {browserVoices
                  .filter((v) => v.lang.toLowerCase().startsWith("en"))
                  .map((v) => (
                    <option key={v.voiceURI} value={v.voiceURI}>
                      {v.name} ({v.lang})
                    </option>
                  ))}
              </select>
            ) : (
              <p className="text-xs text-neutral-400">
                No voices found yet — your browser may still be loading them, or voice output isn&apos;t supported
                here.
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 relative">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">Voice Cloning</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-5">
              Record or upload a short ({MIN_SAMPLE_SECONDS}-{MAX_SAMPLE_SECONDS} second) clip of your voice. Answers
              can then be read back in it instead of the default voice. Only use your own voice, or one you have
              permission to use.
            </p>

            {cloningLocked && (
              <div className="absolute inset-0 rounded-2xl bg-white/80 dark:bg-neutral-950/80 backdrop-blur-[1px] flex flex-col items-center justify-center gap-3 z-10">
                <p className="text-sm text-neutral-600 dark:text-neutral-300">Voice cloning is a Pro feature.</p>
                <a
                  href="/upgrade"
                  className="text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-1.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors"
                >
                  Upgrade to Pro to unlock voice cloning
                </a>
              </div>
            )}

            {!loading && (
              <div className={cloningLocked ? "opacity-40 pointer-events-none select-none" : ""}>
                {!cloneAvailable && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 mb-3">
                    Voice cloning isn&apos;t set up on this server yet, so &quot;My Voice&quot; is unavailable. You can
                    still save a sample.
                  </p>
                )}
                {hasSample && !replacing ? (
                  <div className="space-y-3">
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      Voice sample saved.
                    </p>
                    {previewUrl && <audio controls src={previewUrl} className="w-full h-9" />}
                    <label className="flex items-start gap-3 cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
                      <input
                        type="checkbox"
                        checked={pregenerate}
                        onChange={togglePregenerate}
                        className="mt-0.5 h-4 w-4 accent-neutral-900 dark:accent-neutral-100"
                      />
                      <span>
                        <span className="block text-xs font-medium text-neutral-900 dark:text-neutral-100">
                          Pre-generate my voice for new answers
                        </span>
                        <span className="block text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
                          Clones each new reply in the background so Listen is usually instant. Uses server CPU and
                          counts toward your daily voice-clone limit even for answers you never play.
                        </span>
                      </span>
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setReplacing(true)}
                        className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        Replace
                      </button>
                      <button
                        onClick={deleteSample}
                        disabled={deletingSample}
                        className="flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900 rounded-lg px-3 py-1.5 hover:bg-red-50 dark:hover:bg-red-950/30 disabled:opacity-60"
                      >
                        {deletingSample ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                        {deletingSample ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <VoiceSampleRecorder onSubmit={uploadSample} onCancel={hasSample ? () => setReplacing(false) : undefined} />
                )}

                {error && <p className="text-xs text-red-600 dark:text-red-400 mt-3">{error}</p>}

                {cloneQuota && (
                  <p className="text-xs text-neutral-400 mt-4">
                    {typeof cloneQuota.limit === "number"
                      ? `${Math.max(0, cloneQuota.limit - cloneQuota.current_usage)}/${cloneQuota.limit} clones left today`
                      : "Unlimited clones"}
                    {cloneQuota.resets_in_human && cloneQuota.current_usage > 0 && ` · resets in ${cloneQuota.resets_in_human}`}
                  </p>
                )}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 mt-6">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">Preferred language</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-4">
              Get each new answer explained in Urdu or Roman Urdu automatically, right after the English answer.
              You can still switch any answer between languages with the buttons under it.
            </p>
            <div className="inline-flex rounded-lg bg-neutral-100 dark:bg-neutral-800 p-0.5">
              {(
                [
                  ["en", "English"],
                  ["ur", "اردو"],
                  ["roman_ur", "Roman Urdu"],
                ] as [AppLanguage, string][]
              ).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => chooseLanguage(value)}
                  aria-pressed={preferredLanguage === value}
                  className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                    preferredLanguage === value
                      ? "bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 shadow-sm font-medium"
                      : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {languageQuota && languageQuota.limit !== null && (
              <p className="text-xs text-neutral-400 mt-3">
                {languageQuota.current_usage} of {String(languageQuota.limit)} explanations used today
                {languageQuota.resets_in_human ? ` · resets in ${languageQuota.resets_in_human}` : ""}
              </p>
            )}
            {languageError && <p className="text-xs text-red-600 dark:text-red-400 mt-2">{languageError}</p>}
          </section>

          <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 mt-6">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">Daily Review</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-5">
              How many spaced-repetition flashcards show up in your Daily Review session at once.
            </p>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={5}
                max={50}
                value={dailyCapInput}
                onChange={(e) => setDailyCapInput(e.target.value)}
                className="w-24 text-sm rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-1.5 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
              />
              <span className="text-xs text-neutral-400">cards / day (5-50)</span>
              <button
                onClick={saveDailyCap}
                disabled={savingCap || dailyCap === null}
                className="flex items-center gap-1.5 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-1.5 hover:bg-neutral-800 dark:hover:bg-white disabled:opacity-50"
              >
                {capSaved ? <Check className="h-3.5 w-3.5" /> : null}
                Save
              </button>
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
