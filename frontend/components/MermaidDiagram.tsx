"use client";

import { useEffect, useRef, useState, useId } from "react";
import { Download, AlertTriangle, X } from "lucide-react";

export default function MermaidDiagram({ code, onDelete }: { code: string; onDelete?: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
          // Plain SVG text instead of <foreignObject> HTML labels — foreignObject
          // content taints the canvas on export ("Tainted canvases may not be
          // exported"), even from a same-origin blob URL, so this avoids that class
          // of failure entirely for the PNG download below.
          flowchart: { htmlLabels: false },
          class: { htmlLabels: false },
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          state: { htmlLabels: false } as any,
        });
        const { svg: rendered } = await mermaid.render(`mermaid-${id}`, code);
        if (!cancelled) {
          setSvg(rendered);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setError("Couldn't render this diagram — the generated syntax may be malformed. Try generating it again.");
        }
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [code, id]);

  function downloadSvgFile(svgEl: SVGSVGElement) {
    const svgData = new XMLSerializer().serializeToString(svgEl);
    const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "diagram.svg";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadAsImage() {
    if (!containerRef.current) return;
    setDownloadError(null);

    // html2canvas reads the DOM directly (computed styles, laid-out text) rather than
    // rasterizing the SVG through an <img>, so it isn't affected by Mermaid's cluster/
    // subgraph titles rendering via <foreignObject> — which taints a canvas on any
    // browser's native drawImage-based export, even from a same-origin blob URL.
    try {
      const html2canvas = (await import("html2canvas-pro")).default;
      const canvas = await html2canvas(containerRef.current, { backgroundColor: "#ffffff", scale: 2 });
      canvas.toBlob((blob) => {
        if (!blob) throw new Error("no blob");
        const pngUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = pngUrl;
        a.download = "diagram.png";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(pngUrl);
      });
    } catch {
      const svgEl = containerRef.current.querySelector("svg");
      if (svgEl) {
        downloadSvgFile(svgEl);
        setDownloadError("Couldn't export as PNG, so we saved it as an SVG file instead (still opens fine, just a different format).");
      } else {
        setDownloadError("Couldn't export this diagram as an image. Please try again.");
      }
    }
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-xl px-4 py-3">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <span className="flex-1">{error}</span>
        {onDelete && (
          <button
            onClick={onDelete}
            className="shrink-0 flex items-center gap-1 text-xs font-medium text-amber-700 dark:text-amber-400 hover:text-amber-900 dark:hover:text-amber-200 transition-colors"
            aria-label="Delete this diagram"
          >
            <X className="h-3.5 w-3.5" />
            Remove
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="border border-neutral-200 dark:border-neutral-800 rounded-xl bg-neutral-50 dark:bg-neutral-900 p-4">
      {svg ? (
        <div ref={containerRef} className="overflow-x-auto [&_svg]:mx-auto" dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <div ref={containerRef} className="overflow-x-auto [&_svg]:mx-auto">
          <p className="text-xs text-neutral-400 dark:text-neutral-500">Rendering diagram...</p>
        </div>
      )}
      {svg && (
        <>
          <button
            onClick={downloadAsImage}
            className="mt-3 flex items-center gap-1.5 text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download as image
          </button>
          {downloadError && (
            <p className="mt-1.5 text-xs text-amber-600 dark:text-amber-400">{downloadError}</p>
          )}
        </>
      )}
    </div>
  );
}
