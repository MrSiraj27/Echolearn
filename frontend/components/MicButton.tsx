"use client";

import { Mic, Square } from "lucide-react";
import { useSpeechRecognition } from "@/lib/use-speech-recognition";
import { useSpeech } from "@/lib/speech-context";

export default function MicButton({
  disabled,
  onInterimResult,
  onFinalResult,
}: {
  disabled?: boolean;
  onInterimResult: (text: string) => void;
  onFinalResult: (text: string) => void;
}) {
  const { recognitionLang } = useSpeech();
  const { isListening, error, isSupported, start, stop, cancel } = useSpeechRecognition({
    lang: recognitionLang,
    onInterimResult,
    onFinalResult: (text) => {
      onFinalResult(text);
      stop();
    },
  });

  if (!isSupported) return null;

  function handleClick() {
    if (isListening) {
      cancel();
    } else {
      start();
    }
  }

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        aria-label={isListening ? "Stop voice input" : "Ask by voice"}
        className={`h-11 w-11 rounded-xl border flex items-center justify-center transition-colors disabled:opacity-40 ${
          isListening
            ? "bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900 text-red-600 dark:text-red-400"
            : "border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
        }`}
      >
        {isListening ? (
          <span className="relative flex h-4 w-4 items-center justify-center">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-60" />
            <Square className="h-3.5 w-3.5 relative" />
          </span>
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </button>
      {error && !isListening && (
        <p className="absolute top-full left-1/2 -translate-x-1/2 mt-1 w-max max-w-[180px] text-center text-[11px] text-amber-600 dark:text-amber-400">
          {error}
        </p>
      )}
    </div>
  );
}
