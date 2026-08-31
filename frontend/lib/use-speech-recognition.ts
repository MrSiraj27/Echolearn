"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Minimal shape of the Web Speech API's SpeechRecognition — not in default TS lib.
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  [index: number]: { transcript: string };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function useSpeechRecognition({
  onFinalResult,
  onInterimResult,
  lang = "en-US",
}: {
  onFinalResult?: (text: string) => void;
  onInterimResult?: (text: string) => void;
  lang?: string;
} = {}) {
  const [isListening, setIsListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const cancelledRef = useRef(false);
  const onFinalResultRef = useRef(onFinalResult);
  onFinalResultRef.current = onFinalResult;
  const onInterimResultRef = useRef(onInterimResult);
  onInterimResultRef.current = onInterimResult;

  const isSupported = typeof window !== "undefined" && getSpeechRecognitionConstructor() !== null;

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognitionConstructor();
    if (!Ctor) {
      setError("Voice input isn't supported in this browser. Try Chrome or Edge.");
      return;
    }

    setError(null);
    setInterimTranscript("");
    cancelledRef.current = false;

    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = lang;

    recognition.onresult = (event) => {
      let finalText = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }
      if (finalText.trim()) {
        onFinalResultRef.current?.(finalText.trim());
      } else if (interimText) {
        setInterimTranscript(interimText);
        onInterimResultRef.current?.(interimText);
      }
    };

    recognition.onerror = (event) => {
      if (cancelledRef.current) return;
      if (event.error === "no-speech") {
        setError("Didn't catch that — try again.");
      } else if (event.error === "not-allowed" || event.error === "permission-denied") {
        setError("Microphone access denied. Enable it in your browser's site settings.");
      } else if (event.error === "network") {
        setError("Voice input failed — network error.");
      } else {
        setError("Voice input failed. Please try again.");
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimTranscript("");
    };

    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  }, [lang]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    recognitionRef.current?.abort();
    setIsListening(false);
    setInterimTranscript("");
  }, []);

  return { isListening, interimTranscript, error, isSupported, start, stop, cancel };
}
