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
