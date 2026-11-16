"use client";

import { buildSegments, type HighlightRange, type TextBlock } from "@/lib/reader";

const MARK: Record<string, string> = {
  explained:
    "rounded-sm bg-coral-soft text-inherit underline decoration-coral decoration-2 underline-offset-[3px] dark:bg-coral-active/30",
  "active-match": "rounded-sm bg-amber-300 text-neutral-950 dark:bg-amber-500",
  match: "rounded-sm bg-amber-100 text-inherit dark:bg-amber-700/50",
};

/** One reflowed page: headings, paragraphs and code blocks, with search and explanation
 *  highlights. `ranges` are offsets into `text` (the page's display string). */
export default function ReadableText({
  text,
  blocks,
  ranges,
}: {
  text: string;
  blocks: TextBlock[];
  ranges: HighlightRange[];
}) {
  return (
    <div className="space-y-[1.1em]">
      {blocks.map((b, bi) => {
        const local = ranges
          .filter((r) => r.end > b.start && r.start < b.end)
          .map((r) => ({ ...r, start: Math.max(r.start, b.start) - b.start, end: Math.min(r.end, b.end) - b.start }));
        const segs = buildSegments(text.slice(b.start, b.end), local);
        const body = segs.map((s, i) =>
          s.kind ? (
            <mark key={i} data-active-match={s.active ? "" : undefined} className={MARK[s.kind]}>
              {s.text}
            </mark>
          ) : (
            <span key={i}>{s.text}</span>
          )
        );
        if (b.kind === "heading")
          return (
            <h3 key={bi} className="pt-[0.4em] font-serif text-[1.15em] font-semibold leading-snug tracking-[-0.01em] text-neutral-950 dark:text-neutral-50">
              {body}
            </h3>
          );
        if (b.kind === "code")
          return (
            <pre
              key={bi}
              className="overflow-x-auto rounded-lg bg-neutral-100 px-4 py-3 font-mono text-[0.8em] leading-relaxed text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100"
            >
              {body}
            </pre>
          );
        return (
          <p key={bi} className="text-pretty hyphens-auto font-serif leading-[1.75] text-neutral-800 dark:text-neutral-200">
            {body}
          </p>
        );
      })}
    </div>
  );
}
