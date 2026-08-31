"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, Sun, Moon, Monitor, Check } from "lucide-react";
import { useSpeech, RECOGNITION_LANGUAGES } from "@/lib/speech-context";
import { api } from "@/lib/api";

interface VoiceOption {
  id: string;
  label: string;
}

export default function SettingsMenu() {
  const { theme, setTheme } = useTheme();
  const { voiceId, setVoiceId, recognitionLang, setRecognitionLang } = useSpeech();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    api
      .get<VoiceOption[]>("/voice/voices", { auth: true })
      .then(setVoices)
      .catch(() => setVoices([]));
  }, []);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const themeOptions = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
    { id: "system", label: "System", icon: Monitor },
  ] as const;

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 px-1 py-1 transition-colors"
      >
        <Settings className="h-4 w-4" />
        Settings
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className="absolute left-0 bottom-full mb-2 w-56 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-lg overflow-hidden z-20"
          >
            <div className="px-3 py-2 border-b border-neutral-100 dark:border-neutral-700">
              <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1.5">
                Theme
              </p>
              <div className="flex gap-1">
                {themeOptions.map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    onClick={() => setTheme(id)}
                    className={`flex-1 flex items-center justify-center gap-1 text-xs px-2 py-1.5 rounded-md transition-colors ${
                      mounted && theme === id
                        ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900"
                        : "text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700"
                    }`}
                  >
                    <Icon className="h-3 w-3" />
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {voices.length > 0 && (
              <div className="px-3 py-2">
                <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1.5">
                  Voice
                </p>
                <div className="space-y-0.5">
                  {voices.map((voice) => (
                    <button
                      key={voice.id}
                      onClick={() => setVoiceId(voice.id)}
                      className="w-full flex items-center justify-between text-xs text-neutral-700 dark:text-neutral-200 px-2 py-1.5 rounded-md hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
                    >
                      {voice.label}
                      {voiceId === voice.id && <Check className="h-3.5 w-3.5" />}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="px-3 py-2 border-t border-neutral-100 dark:border-neutral-700">
              <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-1.5">
                Voice input language
              </p>
              <select
                value={recognitionLang}
                onChange={(e) => setRecognitionLang(e.target.value)}
                className="w-full text-xs text-neutral-700 dark:text-neutral-200 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
              >
                {RECOGNITION_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.label}
                  </option>
                ))}
              </select>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
