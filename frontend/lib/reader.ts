// Pure helpers for the document reader: in-document search, highlight segmentation,
// locating a selection inside a page, and detecting section headings for navigation.

import type { DocumentPage } from "@/lib/types";

export interface TextRange {
  start: number;
  end: number;
}

export interface PageMatch extends TextRange {
  /** Index into the pages array (not the page number). */
  pageIndex: number;
}

export const MAX_SEARCH_MATCHES = 500;

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Case-insensitive matches of `query` across all pages; whitespace in the query matches any run of whitespace. */
export function findMatches(pages: DocumentPage[], query: string, limit = MAX_SEARCH_MATCHES): PageMatch[] {
  const q = query.trim();
  if (q.length < 2) return [];
  const pattern = new RegExp(q.split(/\s+/).map(escapeRegExp).join("\\s+"), "gi");
  const out: PageMatch[] = [];
  pages.forEach((p, pageIndex) => {
    if (out.length >= limit) return;
    pattern.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = pattern.exec(p.text)) !== null) {
      out.push({ pageIndex, start: m.index, end: m.index + m[0].length });
      if (out.length >= limit) break;
      if (m[0].length === 0) pattern.lastIndex++;
    }
  });
  return out;
}

/** Where `selection` sits in `text`, tolerating whitespace/line-break differences from the DOM selection. */
export function locateSelection(text: string, selection: string): TextRange | null {
  const sel = selection.trim();
  if (!sel) return null;
  const exact = text.indexOf(sel);
  if (exact !== -1) return { start: exact, end: exact + sel.length };
  const words = sel.split(/\s+/).filter(Boolean);
  if (!words.length) return null;
  const m = new RegExp(words.map(escapeRegExp).join("\\s+")).exec(text);
  return m ? { start: m.index, end: m.index + m[0].length } : null;
}

export interface Segment {
  text: string;
  /** null = plain text */
  kind: "match" | "active-match" | "explained" | null;
  /** Set on the active search match so the reader can scroll it into view. */
  active?: boolean;
}

export interface HighlightRange extends TextRange {
  kind: "match" | "active-match" | "explained";
}

/** Split `text` into plain and highlighted runs. Overlapping ranges: the earlier-starting one wins. */
export function buildSegments(text: string, ranges: HighlightRange[]): Segment[] {
  const sorted = ranges
    .filter((r) => r.end > r.start && r.start >= 0 && r.end <= text.length)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  const out: Segment[] = [];
  let cursor = 0;
  for (const r of sorted) {
    if (r.start < cursor) continue; // overlaps the previous highlight
    if (r.start > cursor) out.push({ text: text.slice(cursor, r.start), kind: null });
    out.push({ text: text.slice(r.start, r.end), kind: r.kind, active: r.kind === "active-match" });
    cursor = r.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor), kind: null });
  return out;
}

export interface Heading {
  pageIndex: number;
  title: string;
}

const NUMBERED = /^(\d{1,2}(\.\d{1,2}){0,3}\.?|[IVX]{1,5}\.|chapter\s+\d+|section\s+\d+|unit\s+\d+|part\s+[\dIVX]+)[\s:.-]+\S/i;

/**
 * Lines that look like section headings (numbered headings, "Chapter 3", short ALL-CAPS lines).
 * Extracted text has no real structure, so this is a heuristic: it's labelled "detected" in the UI.
 */
export function detectHeadings(pages: DocumentPage[], limit = 200): Heading[] {
  const out: Heading[] = [];
  const seen = new Set<string>();
  for (let pageIndex = 0; pageIndex < pages.length && out.length < limit; pageIndex++) {
    for (const raw of pages[pageIndex].text.split("\n")) {
      const line = raw.trim();
      if (line.length < 3 || line.length > 80 || /[.,;:]$/.test(line)) continue;
      const words = line.split(/\s+/);
      const letters = line.replace(/[^A-Za-z]/g, "");
      const allCaps = letters.length >= 4 && letters === letters.toUpperCase() && words.length <= 8;
      const numbered = NUMBERED.test(line) && words.length <= 12 && /[A-Za-z]{3}/.test(line);
      if (!allCaps && !numbered) continue;
      const key = line.toLowerCase();
      if (seen.has(key)) continue; // running headers repeat on every page
      seen.add(key);
      out.push({ pageIndex, title: line });
      if (out.length >= limit) break;
    }
  }
  return out;
}

/** "1.2 MB" style size, or null if unknown. */
export function formatBytes(bytes: number | null | undefined): string | null {
  if (bytes == null) return null;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Reflowing extracted PDF text into readable blocks.
//
// PDF text arrives one printed line per "\n": short ragged lines, words split with a
// hyphen at line ends, the chapter title repeated at the top of every page, and page
// numbers. formatPages() turns each page into paragraphs, headings and code blocks, and
// returns `text` (the display string the reader searches, highlights and explains) plus
// `blocks` (offsets into that string, so each block can be styled).

export type BlockKind = "heading" | "paragraph" | "code";

export interface TextBlock extends TextRange {
  kind: BlockKind;
}

export interface FormattedPage extends DocumentPage {
  blocks: TextBlock[];
}

const CODE_LINE =
  /^(>>>|\.\.\.\s|def |class |import |from \S+ import |return\b|print\(|for .+:$|while .+:$|if .+:$|elif .+:$|else:$|try:$|except\b.*:$|with .+:$|\w+(\.\w+)* = \S|\w+\(.*\)$|[#}{])/;
const HEADING_NUMBERED = /^(chapter|section|part|unit|appendix)\s+[\dIVXA-Z]+\b|^\d{1,2}(\.\d{1,2}){0,3}\.?\s+\S/i;
// Ends a sentence, allowing a trailing footnote number: `it.”6`.
const SENTENCE_END = /[.!?:;"”’)\]]\d{0,2}$/;

function isCodeLine(line: string): boolean {
  return CODE_LINE.test(line.trim());
}

function isHeadingLine(line: string, next: string | undefined): boolean {
  const t = line.trim();
  if (t.length < 3 || t.length > 70 || SENTENCE_END.test(t) || /[,]$/.test(t)) return false;
  const words = t.split(/\s+/);
  if (words.length > 10) return false;
  const letters = t.replace(/[^A-Za-z]/g, "");
  const allCaps = letters.length >= 3 && letters === letters.toUpperCase();
  const numbered = HEADING_NUMBERED.test(t) && /[A-Za-z]{3}/.test(t);
  // A short Title Case line followed by a normal sentence start is very likely a heading.
  const titleCase =
    words.length <= 7 &&
    words.filter((w) => /^[A-Z]/.test(w)).length >= Math.ceil(words.length * 0.6) &&
    !!next &&
    /^[A-Z“"]/.test(next.trim());
  return allCaps || numbered || titleCase;
}

/** Lines that repeat as the first line of many pages (running headers), normalised. */
function runningHeaders(pages: DocumentPage[]): Set<string> {
  const counts = new Map<string, number>();
  for (const p of pages) {
    const lines = p.text.split("\n").map((l) => l.trim()).filter(Boolean);
    for (const l of lines.slice(0, 2)) {
      const key = l.replace(/\d+/g, "#").toLowerCase();
      if (l.length <= 80) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  const threshold = Math.max(3, Math.ceil(pages.length * 0.2));
  return new Set([...counts].filter(([, n]) => n >= threshold).map(([k]) => k));
}

function formatOne(raw: string, headers: Set<string>): { text: string; blocks: TextBlock[] } {
  let lines = raw.split("\n").map((l) => l.replace(/\s+$/, ""));
  // Drop running headers and bare page numbers at the top/bottom of the page.
  const isNoise = (l: string) => /^\s*\d{1,4}\s*$/.test(l) || headers.has(l.trim().replace(/\d+/g, "#").toLowerCase());
  while (lines.length && (lines[0].trim() === "" || isNoise(lines[0]))) lines = lines.slice(1);
  while (lines.length && (lines[lines.length - 1].trim() === "" || isNoise(lines[lines.length - 1]))) lines = lines.slice(0, -1);

  const nonEmpty = lines.map((l) => l.trim().length).filter((n) => n > 0).sort((a, b) => a - b);
  const typical = nonEmpty.length ? nonEmpty[Math.floor(nonEmpty.length * 0.8)] : 60;

  type Raw = { kind: BlockKind; lines: string[] };
  const raws: Raw[] = [];
  let cur: Raw | null = null;
  const flush = () => {
    if (cur && cur.lines.length) raws.push(cur);
    cur = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();
    if (!t) {
      flush();
      continue;
    }
    const code = isCodeLine(line) || (/^\s{2,}\S/.test(line) && cur?.kind === "code");
    if (code) {
      if (cur?.kind !== "code") {
        flush();
        cur = { kind: "code", lines: [] };
      }
      cur!.lines.push(line);
      continue;
    }
    if (isHeadingLine(line, lines[i + 1]) && (cur === null || cur.kind !== "paragraph" || SENTENCE_END.test(cur.lines[cur.lines.length - 1]))) {
      flush();
      raws.push({ kind: "heading", lines: [t] });
      continue;
    }
    if (cur?.kind !== "paragraph") {
      flush();
      cur = { kind: "paragraph", lines: [t] };
      continue;
    }
    const prev = cur.lines[cur.lines.length - 1];
    // A short line ending a sentence closes the paragraph; an indented line starts one.
    const prevEndsParagraph = SENTENCE_END.test(prev) && prev.length < typical * 0.85;
    if (prevEndsParagraph || /^\s{2,}/.test(line)) {
      flush();
      cur = { kind: "paragraph", lines: [t] };
    } else {
      cur.lines.push(t);
    }
  }
  flush();

  const blocks: TextBlock[] = [];
  let text = "";
  for (const r of raws) {
    let body: string;
    if (r.kind === "code") body = r.lines.join("\n");
    else {
      body = r.lines.reduce((acc, l) => {
        if (!acc) return l;
        // "inter-" + "national" -> "international"; keep real hyphens like "self-" + "Made".
        if (/[a-z]-$/.test(acc) && /^[a-z]/.test(l)) return acc.slice(0, -1) + l;
        return `${acc} ${l}`;
      }, "");
    }
    if (text) text += "\n\n";
    blocks.push({ kind: r.kind, start: text.length, end: text.length + body.length });
    text += body;
  }
  return { text, blocks };
}

/** Reflow every page for reading. Pages without text stay empty. */
export function formatPages(pages: DocumentPage[]): FormattedPage[] {
  const headers = runningHeaders(pages);
  return pages.map((p) => {
    if (!p.text.trim()) return { ...p, text: "", blocks: [] };
    const { text, blocks } = formatOne(p.text, headers);
    return { ...p, text, blocks };
  });
}
