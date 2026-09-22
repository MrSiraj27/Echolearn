"use client";

import { createContext, useContext, useState, ReactNode, useCallback, useEffect } from "react";

const VOICE_ID_STORAGE_KEY = "echolearn_voice_id";
const DEFAULT_VOICE_ID = "lessac";
const RECOGNITION_LANG_STORAGE_KEY = "echolearn_recognition_lang";
const DEFAULT_RECOGNITION_LANG = "en-US";

export const RECOGNITION_LANGUAGES = [
  { code: "en-US", label: "English (US)" },
  { code: "en-GB", label: "English (UK)" },
  { code: "es-ES", label: "Spanish" },
  { code: "fr-FR", label: "French" },
  { code: "de-DE", label: "German" },
  { code: "hi-IN", label: "Hindi" },
  { code: "ur-PK", label: "Urdu" },
  { code: "ar-SA", label: "Arabic" },
  { code: "zh-CN", label: "Chinese (Mandarin)" },
];

interface SpeechContextValue {
  speakingId: string | null;
  setSpeakingId: (id: string | null) => void;
  voiceId: string;
  setVoiceId: (id: string) => void;
  recognitionLang: string;
  setRecognitionLang: (lang: string) => void;
  hasVoiceSample: boolean;
  refreshVoiceSample: () => void;
  useMyVoice: boolean;
  setUseMyVoice: (v: boolean) => void;
  // Whether the server has any default (non-cloned) voice installed at all. Checked once
  // at mount rather than per click: mobile browsers (notably iOS Safari) only allow
  // speechSynthesis.speak() when it's called synchronously inside the click handler, not
  // after an awaited network request — so ListenButton needs to know *before* the click
  // whether it should skip straight to the browser voice instead of trying the server first.
  serverVoiceAvailable: boolean | null; // null = not checked yet
}

const SpeechContext = createContext<SpeechContextValue | undefined>(undefined);

export function SpeechProvider({ children }: { children: ReactNode }) {
  const [speakingId, setSpeakingIdState] = useState<string | null>(null);
  const [voiceId, setVoiceIdState] = useState<string>(DEFAULT_VOICE_ID);
  const [recognitionLang, setRecognitionLangState] = useState<string>(DEFAULT_RECOGNITION_LANG);
  const [hasVoiceSample, setHasVoiceSample] = useState(false);
  const [useMyVoice, setUseMyVoice] = useState(false);
  const [serverVoiceAvailable, setServerVoiceAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(VOICE_ID_STORAGE_KEY);
      if (stored) setVoiceIdState(stored);
      const storedLang = localStorage.getItem(RECOGNITION_LANG_STORAGE_KEY);
      if (storedLang) setRecognitionLangState(storedLang);
    } catch {
      // localStorage unavailable — fall back to the defaults.
    }
  }, []);

  const refreshVoiceSample = useCallback(() => {
    import("@/lib/api").then(({ api }) => {
      api
        .get<{ has_voice_sample: boolean }>("/users/me/usage", { auth: true })
        .then((data) => setHasVoiceSample(!!data.has_voice_sample))
        .catch(() => setHasVoiceSample(false));
    });
  }, []);

  useEffect(() => {
    refreshVoiceSample();
  }, [refreshVoiceSample]);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/voice/voices`)
      .then((res) => (res.ok ? res.json() : []))
      .then((voices: unknown[]) => setServerVoiceAvailable(Array.isArray(voices) && voices.length > 0))
      .catch(() => setServerVoiceAvailable(false));
  }, []);

  const setSpeakingId = useCallback((id: string | null) => {
    setSpeakingIdState(id);
  }, []);

  const setVoiceId = useCallback((id: string) => {
    setVoiceIdState(id);
    try {
      localStorage.setItem(VOICE_ID_STORAGE_KEY, id);
    } catch {
      // ignore
    }
  }, []);

  const setRecognitionLang = useCallback((lang: string) => {
    setRecognitionLangState(lang);
    try {
      localStorage.setItem(RECOGNITION_LANG_STORAGE_KEY, lang);
    } catch {
      // ignore
    }
  }, []);

  return (
    <SpeechContext.Provider
      value={{
        speakingId,
        setSpeakingId,
        voiceId,
        setVoiceId,
        recognitionLang,
        setRecognitionLang,
        hasVoiceSample,
        refreshVoiceSample,
        useMyVoice,
        setUseMyVoice,
        serverVoiceAvailable,
      }}
    >
      {children}
    </SpeechContext.Provider>
  );
}

export function useSpeech() {
  const ctx = useContext(SpeechContext);
  if (!ctx) throw new Error("useSpeech must be used within SpeechProvider");
  return ctx;
}
