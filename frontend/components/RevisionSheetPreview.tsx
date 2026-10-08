"use client";

import { useState } from "react";
import { AnimatePresence } from "framer-motion";
import SourceViewer from "@/components/SourceViewer";
import { Citation, RevisionSheetContent, RevisionSheetItem } from "@/lib/types";

// Nastaliq needs roughly double line spacing or its tall letters overlap.
const URDU_FONT = "font-[family-name:var(--font-urdu)] leading-[2.2]";
const BOLD = "font-semibold text-neutral-900 dark:text-neutral-100";

function RefChip({ item, onOpen }: { item: RevisionSheetItem; onOpen: (item: RevisionSheetItem) => void }) {
  // Timestamp sources (audio/video) can't be opened as a page; show them as plain text.
  if (item.page == null || item.t != null) {
    return <span className="text-[10px] text-neutral-400 shrink-0">[{item.ref}]</span>;
  }
  return (
    <button
      onClick={() => onOpen(item)}
      className="text-[10px] text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 underline-offset-2 hover:underline shrink-0"
      title="Open the source page"
    >
      [{item.ref}]
    </button>
  );
}

function ItemBody({
  item,
  isUrdu,
  onOpen,
}: {
  item: RevisionSheetItem;
  isUrdu: boolean;
  onOpen: (item: RevisionSheetItem) => void;
}) {
  const textClass = `text-sm text-neutral-800 dark:text-neutral-200 ${isUrdu ? URDU_FONT : "leading-relaxed"}`;
  const ref = <RefChip item={item} onOpen={onOpen} />;

  switch (item.kind) {
    case "definition":
      return (
        <p dir="auto" className={textClass}>
          <span className={BOLD}>{item.term}</span> {item.definition} {ref}
        </p>
      );
    case "formula":
      return (
        <div>
          <p className={`text-sm ${BOLD}`}>
            {item.name} {ref}
          </p>
          <pre
            dir="ltr"
            className="mt-1 rounded bg-neutral-100 dark:bg-neutral-800 px-2 py-1 text-[13px] whitespace-pre-wrap font-mono text-neutral-900 dark:text-neutral-100"
          >
            {item.expression}
          </pre>
          {item.when_to_use && (
            <p dir="auto" className={`mt-1 text-xs text-neutral-600 dark:text-neutral-400 ${isUrdu ? URDU_FONT : ""}`}>
              {item.when_to_use}
            </p>
          )}
        </div>
      );
    case "fact":
      return (
        <p dir="auto" className={textClass}>
          {item.fact} {ref}
        </p>
      );
    case "key_point":
      return (
        <p dir="auto" className={textClass}>
          {item.topic && <span className={BOLD}>{item.topic} </span>}
          {item.point} {ref}
        </p>
      );
    case "process":
      return (
        <div>
          <p className={`text-sm ${BOLD}`}>
            {item.name} {ref}
          </p>
          <ol className="mt-1 list-decimal list-inside space-y-0.5">
            {(item.steps || []).map((step, i) => (
              <li key={i} dir="auto" className={textClass}>
                {step}
              </li>
            ))}
          </ol>
        </div>
      );
    default:
      return (
        <p dir="auto" className={textClass}>
          {item.point} {ref}
        </p>
      );
  }
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500 dark:text-neutral-400 border-b border-neutral-300 dark:border-neutral-700 pb-1 mb-2.5">
      {children}
    </h3>
  );
}

/** On-screen preview of a revision sheet; every item shows its source and opens it on click. */
export default function RevisionSheetPreview({ content }: { content: RevisionSheetContent }) {
  const [viewing, setViewing] = useState<Citation | null>(null);
  const isUrdu = content.language === "ur";
  const labels = content.labels || {};

  function openSource(item: RevisionSheetItem) {
    const filename = content.sources.find((s) => s.document_id === item.doc_id)?.document ?? null;
    setViewing({ filename, page_number: item.page, document_id: item.doc_id });
  }

  return (
    <div className="space-y-6">
      {content.sections.map((section) => (
        <section key={section.type}>
          <SectionHeading>{labels[section.type] || section.type}</SectionHeading>
          <div className="space-y-2">
            {section.items.map((item) => (
              <div
                key={item.id}
                className={`rounded-lg border px-3 py-2 ${
                  item.kind === "watch_out"
                    ? "border-amber-300 bg-amber-50 dark:border-amber-800/60 dark:bg-amber-950/30"
                    : "border-neutral-200 dark:border-neutral-800"
                }`}
              >
                <ItemBody item={item} isUrdu={isUrdu} onOpen={openSource} />
                {item.gloss && (
                  <p dir="rtl" className={`mt-1 text-sm text-neutral-500 dark:text-neutral-400 ${URDU_FONT}`}>
                    {item.gloss}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}

      {content.self_check.length > 0 && (
        <section>
          <SectionHeading>{labels.self_check || "Self-check"}</SectionHeading>
          <ol className="list-decimal list-inside space-y-1 mb-3">
            {content.self_check.map((q, i) => (
              <li key={i} dir="auto" className={`text-sm text-neutral-800 dark:text-neutral-200 ${isUrdu ? URDU_FONT : ""}`}>
                {q.question}
              </li>
            ))}
          </ol>
          <details className="rounded-lg border border-neutral-200 dark:border-neutral-800 px-3 py-2">
            <summary className="text-xs font-medium text-neutral-600 dark:text-neutral-400 cursor-pointer">
              {labels.answers || "Answers"} — try first, then reveal
            </summary>
            <ol className="mt-2 list-decimal list-inside space-y-1">
              {content.self_check.map((q, i) => (
                <li
                  key={i}
                  dir="auto"
                  className={`text-sm text-neutral-700 dark:text-neutral-300 ${isUrdu ? URDU_FONT : ""}`}
                >
                  {q.answer}
                </li>
              ))}
            </ol>
          </details>
        </section>
      )}

      <AnimatePresence>{viewing && <SourceViewer citation={viewing} onClose={() => setViewing(null)} />}</AnimatePresence>
    </div>
  );
}
