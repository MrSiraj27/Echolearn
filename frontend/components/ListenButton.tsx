"use client";

import { useEffect, useRef, useState } from "react";
import { Volume2, Square, Loader2, User, Sparkles } from "lucide-react";
import { useSpeech } from "@/lib/speech-context";
import { api, ApiError } from "@/lib/api";

interface CloneRequestResponse {
  status: "done" | "queued";
  job_id: string | null;
  audio_url: string | null;
  truncated: boolean;
}

interface CloneStatusResponse {
  status: "queued" | "processing" | "done" | "failed";
  audio_url: string | null;
  error_message: string | null;
}

const CLONE_POLL_INTERVAL_MS = 3500;
const CLONE_POLL_MAX_MS = 5 * 60 * 1000;
const CLONE_POLL_MAX_ERRORS = 3;

function pickBrowserVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  return (
    voices.find((v) => v.lang.startsWith("en") && /female|natural|google/i.test(v.name)) ||
    voices.find((v) => v.lang.startsWith("en")) ||
    voices[0]
  );
}

type PlaybackState = "idle" | "loading" | "cloning" | "playing" | "unavailable" | "limited";

export default function ListenButton({ text, messageId }: { text: string; messageId: string }) {
  const { speakingId, setSpeakingId, voiceId, hasVoiceSample, useMyVoice, setUseMyVoice } = useSpeech();
  const [state, setState] = useState<PlaybackState>("idle");
  const [limitMessage, setLimitMessage] = useState<string | null>(null);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isActive = speakingId === messageId;

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    function loadVoices() {
      setVoices(window.speechSynthesis.getVoices());
    }
    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
  }, []);

  // Another message started playing — stop this one.
  useEffect(() => {
    if (!isActive) {
      stopPlayback();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive]);

  useEffect(() => {
    return () => {
      stopPlayback();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopPlayback() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    window.speechSynthesis?.cancel();
    setState((s) => (s === "unavailable" || s === "limited" ? s : "idle"));
  }

  function speakWithBrowserFallback() {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    const voice = pickBrowserVoice(voices);
    if (voice) utterance.voice = voice;

    utterance.onend = () => setSpeakingId(null);
    utterance.onerror = () => setSpeakingId(null);

    setState("playing");
    window.speechSynthesis.speak(utterance);
  }

  async function playAudioFromUrl(path: string) {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const { getAccessToken } = await import("@/lib/api");
    const token = getAccessToken();
    const res = await fetch(`${apiUrl}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
    });
    if (!res.ok) throw new ApiError(res.status, "Couldn't load cloned audio.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    objectUrlRef.current = url;
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => setSpeakingId(null);
    audio.onerror = () => {
      setState("unavailable");
      setSpeakingId(null);
    };
    setState("playing");
    await audio.play();
  }

  function showError(message: string) {
    // Keep speakingId set: clearing it makes isActive false and hides the message.
    setLimitMessage(message);
    setState("limited");
  }

  function pollCloneStatus(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    const startedAt = Date.now();
    let errors = 0;
    pollRef.current = setInterval(async () => {
      if (Date.now() - startedAt > CLONE_POLL_MAX_MS) {
        if (pollRef.current) clearInterval(pollRef.current);
        showError("Voice cloning is taking too long. Please try again in a bit.");
        return;
      }
      try {
        const status = await api.get<CloneStatusResponse>(`/voice/clone-status/${jobId}`, { auth: true });
        if (status.status === "done" && status.audio_url) {
          if (pollRef.current) clearInterval(pollRef.current);
          try {
            await playAudioFromUrl(status.audio_url);
          } catch {
            showError("Your cloned audio is ready but couldn't be played. Please try again.");
          }
        } else if (status.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          showError(status.error_message || "Voice cloning failed.");
        } else {
          errors = 0;
        }
      } catch (err) {
        // Tolerate a couple of transient network errors; a 404 means the job is gone.
        errors += 1;
        if ((err instanceof ApiError && err.status === 404) || errors >= CLONE_POLL_MAX_ERRORS) {
          if (pollRef.current) clearInterval(pollRef.current);
          showError("Couldn't check on your voice clone. Please try again.");
        }
      }
    }, CLONE_POLL_INTERVAL_MS);
  }

  async function handleMyVoiceClick() {
    setSpeakingId(messageId);
    setState("loading");
    setLimitMessage(null);
    try {
      const result = await api.post<CloneRequestResponse>("/voice/clone-request", { message_id: messageId }, { auth: true });
      if (result.status === "done" && result.audio_url) {
        await playAudioFromUrl(result.audio_url);
      } else if (result.status === "queued" && result.job_id) {
        setState("cloning");
        pollCloneStatus(result.job_id);
      }
    } catch (err) {
      if (err instanceof ApiError && [400, 403, 404, 429, 503].includes(err.status)) {
        showError(err.detail);
      } else {
        showError("Couldn't reach the voice service. Please try again.");
      }
    }
  }

  async function handleClick() {
    if (isActive && (state === "playing" || state === "loading" || state === "cloning")) {
      if (pollRef.current) clearInterval(pollRef.current);
      stopPlayback();
      setSpeakingId(null);
      return;
    }

    if (useMyVoice && hasVoiceSample) {
      await handleMyVoiceClick();
      return;
    }

    setSpeakingId(messageId);
    setState("loading");
    setLimitMessage(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const { getAccessToken } = await import("@/lib/api");
      const token = getAccessToken();

      const res = await fetch(`${apiUrl}/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: "include",
        body: JSON.stringify({ text, message_id: messageId, voice_id: voiceId }),
      });

      if (res.status === 429) {
        const data = await res.json().catch(() => ({}));
        showError(data.detail || "You've reached your text-to-speech limit.");
        return;
      }
      if (res.status === 503) {
        setState("unavailable");
        speakWithBrowserFallback();
        return;
      }
      if (!res.ok) throw new ApiError(res.status, "Voice synthesis failed.");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setSpeakingId(null);
      };
      audio.onerror = () => {
        setState("unavailable");
        setSpeakingId(null);
      };

      setState("playing");
      await audio.play();
    } catch {
      // Backend unreachable or synthesis failed — fall back to browser TTS so the
      // button still does something rather than silently failing.
      setState("unavailable");
      speakWithBrowserFallback();
    }
  }

  const isLoading = isActive && state === "loading";
  const isCloning = isActive && state === "cloning";
  const isPlaying = isActive && state === "playing";

  return (
    <span className="inline-flex items-center gap-1.5">
      <button
        onClick={handleClick}
        className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
        aria-label={isPlaying ? "Stop reading" : "Read aloud"}
        title={state === "unavailable" ? "Server voice unavailable — using browser voice" : undefined}
      >
        {isLoading || isCloning ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : isPlaying ? (
          <Square className="h-3.5 w-3.5" />
        ) : (
          <Volume2 className="h-3.5 w-3.5" />
        )}
        {isCloning ? "Cloning your voice..." : isLoading ? "Loading..." : isPlaying ? "Stop" : "Listen"}
      </button>

      {hasVoiceSample && (
        <button
          onClick={() => setUseMyVoice(!useMyVoice)}
          disabled={isLoading || isCloning}
          title={useMyVoice ? "Using your cloned voice" : "Using default voice"}
          className={`flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded-full border transition-colors disabled:opacity-50 ${
            useMyVoice
              ? "border-neutral-900 dark:border-neutral-100 text-neutral-900 dark:text-neutral-100"
              : "border-neutral-200 dark:border-neutral-700 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300"
          }`}
        >
          {useMyVoice ? <Sparkles className="h-3 w-3" /> : <User className="h-3 w-3" />}
          {useMyVoice ? "My Voice" : "Default Voice"}
        </button>
      )}

      {isCloning && (
        <span className="text-[11px] text-neutral-400">this can take up to a minute</span>
      )}
      {isActive && state === "limited" && limitMessage && (
        <span className="text-xs text-red-600 dark:text-red-400">{limitMessage}</span>
      )}
    </span>
  );
}
