"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";
import { Copy, Check, RotateCcw, BookOpen, Sparkles } from "lucide-react";
import { ChatMessage } from "@/lib/types";
import ListenButton from "@/components/ListenButton";
import ExplainModal from "@/components/ExplainModal";
import SourceViewer from "@/components/SourceViewer";
import MermaidDiagram from "@/components/MermaidDiagram";
import InfographicRenderer from "@/components/InfographicRenderer";
import { api, ApiError } from "@/lib/api";
import { Citation } from "@/lib/types";

function stripMarkdown(md: string): string {
  return md
    .replace(/`{1,3}[^`]*`{1,3}/g, "")
    .replace(/[#*_>~-]/g, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .trim();
}

function isMarkdownTable(text?: string | null): boolean {
  if (!text) return false;
  const lines = text.trim().split("\n");
  return (
    lines.length >= 2 &&
    lines[0].includes("|") &&
    /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(lines[1].trim())
  );
}

function parseMarkdownTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function MarkdownTablePreview({ markdown }: { markdown: string }) {
  const lines = markdown.trim().split("\n").filter(Boolean);
  const header = parseMarkdownTableRow(lines[0]);
  const rows = lines.slice(2).map(parseMarkdownTableRow);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            {header.map((h, i) => (
              <th
                key={i}
                className="text-left font-semibold text-neutral-600 dark:text-neutral-300 border-b border-neutral-200 dark:border-neutral-700 px-2 py-1 whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className="text-neutral-700 dark:text-neutral-300 border-b border-neutral-100 dark:border-neutral-800 px-2 py-1 whitespace-nowrap"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface SelectionPopover {
  x: number;
  y: number;
  text: string;
}

function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default function ChatBubble({
  message,
  chatId,
  onRegenerate,
  onFollowUp,
  onSeek,
  onDeleteMessage,
}: {
  message: ChatMessage;
  chatId?: string;
  onRegenerate?: () => void;
  onFollowUp?: (question: string) => void;
  onSeek?: (seconds: number) => void;
  onDeleteMessage?: (messageId: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [viewingSource, setViewingSource] = useState<Citation | null>(null);
  const [popover, setPopover] = useState<SelectionPopover | null>(null);
  const [expandedTable, setExpandedTable] = useState<number | null>(null);
  const [explainState, setExplainState] = useState<{
    text: string;
    loading: boolean;
    explanation: string | null;
    error: string | null;
  } | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const isUser = message.role === "user";

  async function handleCopy() {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function handleMouseUp() {
    if (!chatId) return;
    const selection = window.getSelection();
    const text = selection?.toString().trim();

    if (!text || text.length < 3 || !selection || selection.rangeCount === 0) {
      setPopover(null);
      return;
    }

    const container = contentRef.current;
    if (!container || !container.contains(selection.anchorNode)) {
      setPopover(null);
      return;
    }

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    setPopover({ x: rect.left + rect.width / 2, y: rect.top, text });
  }

  async function handleExplain() {
    if (!popover || !chatId) return;
    const text = popover.text;
    setPopover(null);
    window.getSelection()?.removeAllRanges();
    setExplainState({ text, loading: true, explanation: null, error: null });

    try {
      const data = await api.post<{ explanation: string }>(
        `/chats/${chatId}/explain`,
        { text },
        { auth: true }
      );
      setExplainState({ text, loading: false, explanation: data.explanation, error: null });
    } catch (err) {
      setExplainState({
        text,
        loading: false,
        explanation: null,
        error: err instanceof ApiError ? err.detail : "Couldn't get an explanation. Please try again.",
      });
    }
  }

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex justify-end"
      >
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
      </motion.div>
    );
  }

  const citations = message.citations || [];

  if (message.content_type === "mermaid") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex justify-start"
      >
        <div className="max-w-[95%] min-w-0 w-full">
          <MermaidDiagram
            code={message.content}
            onDelete={onDeleteMessage ? () => onDeleteMessage(message.id) : undefined}
          />
          <div className="flex items-center gap-3 mt-1.5 text-neutral-400 dark:text-neutral-500">
            <button
              onClick={handleCopy}
              className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
              aria-label="Copy diagram source"
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy source"}
            </button>
          </div>
        </div>
      </motion.div>
    );
  }

  if (message.content_type === "infographic") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex justify-start"
      >
        <div className="max-w-[95%] min-w-0 w-full">
          <InfographicRenderer
            content={message.content}
            onDelete={onDeleteMessage ? () => onDeleteMessage(message.id) : undefined}
          />
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="flex justify-start relative"
    >
      <div className="max-w-[85%] min-w-0">
        <div
          ref={contentRef}
          onMouseUp={handleMouseUp}
          className="prose prose-sm dark:prose-invert prose-neutral max-w-none break-words text-neutral-800 dark:text-neutral-200 leading-relaxed [&_pre]:bg-neutral-900 [&_pre]:text-neutral-50 dark:[&_pre]:bg-neutral-950 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_code]:text-[13px] selection:bg-amber-200/60 dark:selection:bg-amber-400/30"
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>

        <div className="flex items-center gap-3 mt-1.5 text-neutral-400 dark:text-neutral-500">
          <ListenButton text={stripMarkdown(message.content)} messageId={message.id} />
          <button
            onClick={handleCopy}
            className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
            aria-label="Copy message"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          {onRegenerate && (
            <button
              onClick={onRegenerate}
              className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Regenerate
            </button>
          )}
          {citations.length > 0 && (
            <button
              onClick={() => setSourcesOpen((v) => !v)}
              className="text-xs hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors inline-flex items-center gap-1"
            >
              <BookOpen className="h-3.5 w-3.5" />
              Sources ({citations.length})
            </button>
          )}
        </div>

        <AnimatePresence>
          {sourcesOpen && citations.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2 space-y-2 overflow-hidden"
            >
              {(() => {
                const groups = new Map<string, { citation: Citation; index: number }[]>();
                citations.forEach((c, i) => {
                  const key = c.filename || "Unknown source";
                  if (!groups.has(key)) groups.set(key, []);
                  groups.get(key)!.push({ citation: c, index: i });
                });
                const multiSource = groups.size > 1;

                return Array.from(groups.entries()).map(([filename, items]) => (
                  <div key={filename}>
                    {multiSource && (
                      <p className="text-[10px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide px-0.5 mb-1">
                        From {filename}
                      </p>
                    )}
                    <div className="space-y-1">
                      {items.map(({ citation: c, index: i }) => {
                        const isTable = isMarkdownTable(c.chunk_text);
                        const isTimestamp = c.start_time_seconds != null;
                        return (
                          <div key={i}>
                            <button
                              onClick={() => {
                                if (isTimestamp && onSeek) {
                                  onSeek(c.start_time_seconds!);
                                } else if (isTable) {
                                  setExpandedTable((v) => (v === i ? null : i));
                                } else {
                                  setViewingSource(c);
                                }
                              }}
                              disabled={!c.document_id && !isTable && !isTimestamp}
                              className="w-full text-left text-xs text-neutral-500 dark:text-neutral-400 bg-neutral-50 dark:bg-neutral-800/60 border border-neutral-200 dark:border-neutral-700 rounded-lg px-2.5 py-1.5 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-600 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors disabled:cursor-default disabled:hover:bg-neutral-50 dark:disabled:hover:bg-neutral-800/60"
                            >
                              {isTimestamp ? (
                                <>
                                  {multiSource ? `${formatTimestamp(c.start_time_seconds!)}` : filename}
                                  {!multiSource ? ` — ${formatTimestamp(c.start_time_seconds!)}` : ""}
                                </>
                              ) : (
                                <>
                                  {multiSource ? (c.page_number ? `Page ${c.page_number}` : filename) : filename}
                                  {!multiSource && c.page_number ? ` — page ${c.page_number}` : ""}
                                </>
                              )}
                              {isTable ? " · table" : ""}
                            </button>
                            <AnimatePresence>
                              {isTable && expandedTable === i && c.chunk_text && (
                                <motion.div
                                  initial={{ opacity: 0, height: 0 }}
                                  animate={{ opacity: 1, height: "auto" }}
                                  exit={{ opacity: 0, height: 0 }}
                                  className="mt-1 border border-neutral-200 dark:border-neutral-700 rounded-lg p-2 bg-white dark:bg-neutral-900 overflow-hidden"
                                >
                                  <MarkdownTablePreview markdown={c.chunk_text} />
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ));
              })()}
            </motion.div>
          )}
        </AnimatePresence>

        {onFollowUp && message.followUps && message.followUps.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.25 }}
            className="flex flex-wrap gap-2 mt-3"
          >
            {message.followUps.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowUp(q)}
                title={q.length > 60 ? q : undefined}
                className="max-w-[280px] truncate text-xs text-neutral-600 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-full px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 transition-colors"
              >
                {q.length > 60 ? `${q.slice(0, 60)}…` : q}
              </button>
            ))}
          </motion.div>
        )}
      </div>

      <AnimatePresence>
        {popover && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.12 }}
            style={{ position: "fixed", left: popover.x, top: popover.y - 42, transform: "translateX(-50%)" }}
            onClick={handleExplain}
            className="z-40 bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-xs font-medium px-3 py-1.5 rounded-full shadow-lg hover:bg-neutral-800 dark:hover:bg-white inline-flex items-center gap-1"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Explain
          </motion.button>
        )}
      </AnimatePresence>

      {explainState && (
        <ExplainModal
          selectedText={explainState.text}
          loading={explainState.loading}
          explanation={explainState.explanation}
          error={explainState.error}
          onClose={() => setExplainState(null)}
        />
      )}

      {viewingSource && <SourceViewer citation={viewingSource} onClose={() => setViewingSource(null)} />}
    </motion.div>
  );
}
