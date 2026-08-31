"use client";

import { useRef, useState } from "react";
import { Download, X, AlertTriangle } from "lucide-react";
import { InfographicPayload, StatsData, TimelineData, ComparisonData, SummaryData } from "@/lib/types";
import StatsInfographic from "@/components/infographics/StatsInfographic";
import TimelineInfographic from "@/components/infographics/TimelineInfographic";
import ComparisonInfographic from "@/components/infographics/ComparisonInfographic";
import SummaryInfographic from "@/components/infographics/SummaryInfographic";

export default function InfographicRenderer({ content, onDelete }: { content: string; onDelete?: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  let payload: InfographicPayload | null = null;
  try {
    payload = JSON.parse(content);
  } catch {
    payload = null;
  }

  async function downloadAsImage() {
    if (!containerRef.current) return;
    setDownloadError(null);
    try {
      const html2canvas = (await import("html2canvas-pro")).default;
      const canvas = await html2canvas(containerRef.current, { backgroundColor: "#ffffff", scale: 2 });
      canvas.toBlob((blob) => {
        if (!blob) throw new Error("no blob");
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "infographic.png";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      });
    } catch {
      setDownloadError("Couldn't export this infographic as an image. Please try again.");
    }
  }

  if (!payload) {
    return (
      <div className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-xl px-4 py-3">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <span className="flex-1">Couldn&apos;t render this infographic — the data may be corrupted.</span>
        {onDelete && (
          <button
            onClick={onDelete}
            className="shrink-0 flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400 hover:text-amber-900 dark:hover:text-amber-200 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
            Remove
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="border border-neutral-200 dark:border-neutral-800 rounded-xl bg-neutral-50 dark:bg-neutral-900 p-3">
      <div ref={containerRef}>
        {payload.template === "stats" && <StatsInfographic data={payload.data as StatsData} />}
        {payload.template === "timeline" && <TimelineInfographic data={payload.data as TimelineData} />}
        {payload.template === "comparison" && <ComparisonInfographic data={payload.data as ComparisonData} />}
        {payload.template === "summary" && <SummaryInfographic data={payload.data as SummaryData} />}
      </div>
      <div className="flex items-center gap-3 mt-3 px-1">
        <button
          onClick={downloadAsImage}
          className="flex items-center gap-1.5 text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors"
        >
          <Download className="h-3.5 w-3.5" />
          Download as image
        </button>
        {onDelete && (
          <button
            onClick={onDelete}
            className="flex items-center gap-1 text-xs font-medium text-neutral-400 dark:text-neutral-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
            Remove
          </button>
        )}
      </div>
      {downloadError && <p className="mt-1.5 px-1 text-xs text-amber-600 dark:text-amber-400">{downloadError}</p>}
    </div>
  );
}
