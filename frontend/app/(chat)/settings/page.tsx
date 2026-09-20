"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Mic, Square, Trash2, Upload, Loader2, Check } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import { useSpeech } from "@/lib/speech-context";
import { ReviewSettingsResponse } from "@/lib/types";
import { blobToWav } from "@/lib/wav";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MIN_SECONDS = 3;
const MAX_SECONDS = 20;

interface MyUsageResponse {
  quotas: { key: string; limit: number | boolean | null; current_usage: number; resets_in_human: string | null }[];
  has_voice_sample: boolean;
}

export default function SettingsPage() {
  const router = useRouter();
  const { refreshVoiceSample } = useSpeech();
  const [usage, setUsage] = useState<MyUsageResponse | null>(null);
  const [hasSample, setHasSample] = useState(false);
  const [loading, setLoading] = useState(true);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [cloneAvailable, setCloneAvailable] = useState(true);
  const [pregenerate, setPregenerate] = useState(false);

  const [dailyCap, setDailyCap] = useState<number | null>(null);
  const [dailyCapInput, setDailyCapInput] = useState("");
  const [savingCap, setSavingCap] = useState(false);
  const [capSaved, setCapSaved] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
      const { getAccessToken } = await import("@/lib/api");
      const token = getAccessToken();
      const res = await fetch(`${API_URL}/voice/sample/audio`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
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
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
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

  const cloneQuota = usage?.quotas.find((q) => q.key === "voice_clone_uses_per_day");
  const cloningLocked = cloneQuota ? cloneQuota.limit === 0 : false;

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        void uploadSample(new File([blob], "voice_sample.webm", { type: "audio/webm" }));
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => {
        setSeconds((s) => {
          const next = s + 1;
          if (next >= MAX_SECONDS) stopRecording();
          return next;
        });
      }, 1000);
    } catch {
      setError("Couldn't access your microphone. Check browser permissions, or upload a file instead.");
    }
  }

  function stopRecording() {
    if (timerRef.current) clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  }

  async function uploadSample(file: File) {
    setUploading(true);
    setError(null);
    try {
      // The backend only accepts plain WAV; convert recordings/uploads in the browser first.
      let wav: Blob;
      let seconds: number;
      try {
        ({ wav, seconds } = await blobToWav(file));
      } catch {
        throw new ApiError(400, "Couldn't read that audio file. Try a different file or record a new sample.");
      }
      if (seconds < MIN_SECONDS || seconds > MAX_SECONDS) {
        throw new ApiError(
          400,
          `Your sample is ${seconds.toFixed(1)}s long. Please use a clip between ${MIN_SECONDS} and ${MAX_SECONDS} seconds.`,
        );
      }
      const formData = new FormData();
      formData.append("file", new File([wav], "voice_sample.wav", { type: "audio/wav" }));
      const { getAccessToken } = await import("@/lib/api");
      const token = getAccessToken();
      const res = await fetch(`${API_URL}/voice/upload-sample`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new ApiError(res.status, data.detail || "Upload failed.");
      }
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(wav);
      });
      setHasSample(true);
      loadUsage();
      refreshVoiceSample();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void uploadSample(file);
    e.target.value = "";
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
    try {
      await api.delete("/voice/sample", { auth: true });
      setHasSample(false);
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });
      refreshVoiceSample();
    } catch {
      setError("Couldn't delete your sample. Please try again.");
    }
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-y-auto bg-white dark:bg-neutral-950">
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

          <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 p-6 relative">
            <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">Voice Cloning</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-5">
              Upload a short (3-20 second) reference clip of your voice. Answers can then be read back using it,
              instead of the default voice.
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
                {hasSample ? (
                  <div className="space-y-3">
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      Voice sample uploaded.
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
                        onClick={() => fileInputRef.current?.click()}
                        className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        Replace
                      </button>
                      <button
                        onClick={deleteSample}
                        className="flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900 rounded-lg px-3 py-1.5 hover:bg-red-50 dark:hover:bg-red-950/30"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      {!recording ? (
                        <button
                          onClick={startRecording}
                          disabled={uploading}
                          className="flex items-center gap-1.5 text-xs font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-lg px-3 py-1.5 hover:bg-neutral-800 dark:hover:bg-white disabled:opacity-50"
                        >
                          <Mic className="h-3.5 w-3.5" />
                          Record sample
                        </button>
                      ) : (
                        <button
                          onClick={stopRecording}
                          className="flex items-center gap-1.5 text-xs font-medium bg-red-600 text-white rounded-lg px-3 py-1.5 hover:bg-red-700"
                        >
                          <Square className="h-3.5 w-3.5" />
                          Stop ({seconds}s)
                        </button>
                      )}
                      <span className="text-xs text-neutral-400">or</span>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading || recording}
                        className="flex items-center gap-1.5 text-xs font-medium border border-neutral-300 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        Upload file
                      </button>
                      {uploading && <Loader2 className="h-4 w-4 animate-spin text-neutral-400" />}
                    </div>
                    {recording && (
                      <p className="text-xs text-neutral-400">
                        Recording... {MIN_SECONDS}-{MAX_SECONDS}s needed, stops automatically at {MAX_SECONDS}s.
                      </p>
                    )}
                  </div>
                )}

                <input ref={fileInputRef} type="file" accept="audio/*" className="hidden" onChange={onFilePicked} />

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
