"use client";

import { useEffect, useRef, useState } from "react";
import { Volume2, Square, Loader2 } from "lucide-react";
import { useSpeech } from "@/lib/speech-context";
import { ApiError } from "@/lib/api";

function pickBrowserVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  return (
    voices.find((v) => v.lang.startsWith("en") && /female|natural|google/i.test(v.name)) ||
    voices.find((v) => v.lang.startsWith("en")) ||
    voices[0]
  );
}

type PlaybackState = "idle" | "loading" | "playing" | "unavailable" | "limited";

export default function ListenButton({ text, messageId }: { text: string; messageId: string }) {
  const { speakingId, setSpeakingId, voiceId } = useSpeech();
  const [state, setState] = useState<PlaybackState>("idle");
  const [limitMessage, setLimitMessage] = useState<string | null>(null);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const isActive = speakingId === messageId;

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

  async function handleClick() {
    if (isActive && (state === "playing" || state === "loading")) {
      stopPlayback();
      setSpeakingId(null);
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
        setLimitMessage(data.detail || "You've reached your text-to-speech limit.");
        setState("limited");
        setSpeakingId(null);
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
  const isPlaying = isActive && state === "playing";

  return (
    <span className="inline-flex items-center gap-1.5">
      <button
        onClick={handleClick}
        className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
        aria-label={isPlaying ? "Stop reading" : "Read aloud"}
        title={state === "unavailable" ? "Server voice unavailable — using browser voice" : undefined}
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : isPlaying ? (
          <Square className="h-3.5 w-3.5" />
        ) : (
          <Volume2 className="h-3.5 w-3.5" />
        )}
        {isLoading ? "Loading..." : isPlaying ? "Stop" : "Listen"}
      </button>
      {isActive && state === "limited" && limitMessage && (
        <span className="text-xs text-red-600 dark:text-red-400">{limitMessage}</span>
      )}
    </span>
  );
}
