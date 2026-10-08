"use client";

import { Volume2, Square } from "lucide-react";
import { useSpeech } from "@/lib/speech-context";

/**
 * Read an Urdu-script explanation aloud with the browser's own Urdu voice.
 *
 * The server's default voices are English-only and would mangle Urdu, so this uses the
 * Web Speech API and only appears when the device actually has an Urdu voice installed
 * (otherwise just a muted icon with a tooltip explaining why).
 */
export default function UrduSpeakButton({ text, messageId }: { text: string; messageId: string }) {
  const { browserVoices, speakingId, setSpeakingId } = useSpeech();
  const speakingKey = `ur:${messageId}`;
  const isSpeaking = speakingId === speakingKey;

  const urduVoice = browserVoices.find((v) => v.lang.toLowerCase().replace("_", "-").startsWith("ur"));

  if (!urduVoice) {
    return (
      <span
        className="text-xs inline-flex items-center gap-1 opacity-50 cursor-help"
        title="Urdu voice not available on this device"
        aria-label="Urdu voice not available on this device"
      >
        <Volume2 className="h-3.5 w-3.5" />
      </span>
    );
  }

  function toggle() {
    if (!window.speechSynthesis || !urduVoice) return;
    window.speechSynthesis.cancel();
    if (isSpeaking) {
      setSpeakingId(null);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ur-PK";
    utterance.voice = urduVoice;
    utterance.onend = () => setSpeakingId(null);
    utterance.onerror = () => setSpeakingId(null);
    setSpeakingId(speakingKey);
    window.speechSynthesis.speak(utterance);
  }

  return (
    <button
      onClick={toggle}
      className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
      aria-label={isSpeaking ? "Stop reading" : "Read Urdu aloud"}
    >
      {isSpeaking ? <Square className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
      {isSpeaking ? "Stop" : "Listen"}
    </button>
  );
}
