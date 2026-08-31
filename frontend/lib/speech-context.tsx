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
}

const SpeechContext = createContext<SpeechContextValue | undefined>(undefined);

export function SpeechProvider({ children }: { children: ReactNode }) {
  const [speakingId, setSpeakingIdState] = useState<string | null>(null);
  const [voiceId, setVoiceIdState] = useState<string>(DEFAULT_VOICE_ID);
  const [recognitionLang, setRecognitionLangState] = useState<string>(DEFAULT_RECOGNITION_LANG);

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
      value={{ speakingId, setSpeakingId, voiceId, setVoiceId, recognitionLang, setRecognitionLang }}
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
