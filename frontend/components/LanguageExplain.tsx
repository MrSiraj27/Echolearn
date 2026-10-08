"use client";

/* eslint-disable @typescript-eslint/no-unused-vars -- react-markdown passes a `node` prop we deliberately drop */

import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AppLanguage } from "@/lib/types";

export const LANGUAGE_LABELS: Record<AppLanguage, string> = {
  en: "English",
  ur: "اردو",
  roman_ur: "Roman Urdu",
};

const PROSE_CLASS =
  "prose prose-sm dark:prose-invert prose-neutral max-w-none break-words text-neutral-800 dark:text-neutral-200 leading-relaxed [&_pre]:bg-neutral-900 [&_pre]:text-neutral-50 dark:[&_pre]:bg-neutral-950 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_code]:text-[13px]";

// Inside right-to-left text, every block picks its own direction from its first strong
// character (dir="auto"): Urdu paragraphs run right-to-left, while a line that is entirely
// English (e.g. "Formula: F = m × a") stays left-to-right instead of getting its
// punctuation shuffled. Code and formulas are always forced left-to-right.
const rtlComponents: Components = {
  p: ({ node, ...props }) => <p dir="auto" {...props} />,
  li: ({ node, ...props }) => <li dir="auto" {...props} />,
  h1: ({ node, ...props }) => <h1 dir="auto" {...props} />,
  h2: ({ node, ...props }) => <h2 dir="auto" {...props} />,
  h3: ({ node, ...props }) => <h3 dir="auto" {...props} />,
  h4: ({ node, ...props }) => <h4 dir="auto" {...props} />,
  blockquote: ({ node, ...props }) => <blockquote dir="auto" {...props} />,
  pre: ({ node, ...props }) => <pre dir="ltr" style={{ textAlign: "left" }} {...props} />,
  code: ({ node, ...props }) => <code style={{ direction: "ltr", unicodeBidi: "isolate" }} {...props} />,
};

/** An Urdu (right-to-left, Nastaliq) or Roman Urdu (normal left-to-right) answer body. */
export function TranslationBody({ text, language }: { text: string; language: AppLanguage }) {
  const isUrdu = language === "ur";
  return (
    <div
      dir={isUrdu ? "rtl" : "ltr"}
      lang={isUrdu ? "ur" : "ur-Latn"}
      // Nastaliq letters are tall and heavily stacked: it needs about double line spacing
      // or lines overlap. List markers sit inline (list-inside) so each line's bullet is next
      // to wherever that line's text starts, whichever direction the line runs.
      className={`${PROSE_CLASS} ${isUrdu ? "font-[family-name:var(--font-urdu)] text-[16px] leading-[2.4] [&_ul]:list-inside [&_ol]:list-inside [&_ul]:ps-0 [&_ol]:ps-0 [&_li]:ps-0" : ""}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={isUrdu ? rtlComponents : undefined}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

/** Placeholder lines shown while an explanation is being generated. */
export function TranslationSkeleton() {
  return (
    <div className="space-y-2.5 py-1" aria-busy="true" aria-label="Generating explanation">
      <div className="h-3 rounded bg-neutral-200 dark:bg-neutral-800 animate-pulse w-11/12" />
      <div className="h-3 rounded bg-neutral-200 dark:bg-neutral-800 animate-pulse w-full" />
      <div className="h-3 rounded bg-neutral-200 dark:bg-neutral-800 animate-pulse w-9/12" />
      <div className="h-3 rounded bg-neutral-200 dark:bg-neutral-800 animate-pulse w-10/12" />
    </div>
  );
}

const TAB_ORDER: AppLanguage[] = ["en", "ur", "roman_ur"];

/** English | اردو | Roman Urdu switcher shown above an answer that has an explanation. */
export function LanguageTabs({
  active,
  onSelect,
  disabled,
}: {
  active: AppLanguage;
  onSelect: (language: AppLanguage) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="tablist"
      className="inline-flex items-center gap-0.5 rounded-lg bg-neutral-100 dark:bg-neutral-800 p-0.5 mb-2"
    >
      {TAB_ORDER.map((language) => (
        <button
          key={language}
          role="tab"
          aria-selected={active === language}
          disabled={disabled}
          onClick={() => onSelect(language)}
          className={`text-xs px-2.5 py-1 rounded-md transition-colors disabled:opacity-60 ${
            active === language
              ? "bg-white dark:bg-neutral-700 text-neutral-900 dark:text-neutral-100 shadow-sm font-medium"
              : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200"
          }`}
        >
          {LANGUAGE_LABELS[language]}
        </button>
      ))}
    </div>
  );
}
