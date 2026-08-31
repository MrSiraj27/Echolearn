"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import { getMediaUrl } from "@/lib/api";
import { api } from "@/lib/api";
import { VIDEO_EXTENSIONS } from "@/lib/types";

interface TranscriptSegment {
  start_time: number | null;
  end_time: number | null;
  text: string;
}

export interface MediaPlayerHandle {
  seekTo: (seconds: number) => void;
}

function formatTimestamp(seconds: number): string {
  const total = Math.floor(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

const MediaPlayer = forwardRef<MediaPlayerHandle, { documentId: string; fileType: string }>(
  function MediaPlayer({ documentId, fileType }, ref) {
    const mediaRef = useRef<HTMLVideoElement & HTMLAudioElement>(null);
    const segmentRefs = useRef<Record<number, HTMLButtonElement | null>>({});
    const [showTranscript, setShowTranscript] = useState(false);
    const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
    const [loadingTranscript, setLoadingTranscript] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);

    const isVideo = VIDEO_EXTENSIONS.has(fileType);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        const el = mediaRef.current;
        if (!el) return;
        el.currentTime = seconds;
        el.play().catch(() => {});
      },
    }));

    useEffect(() => {
      if (!showTranscript || transcript.length > 0) return;
      setLoadingTranscript(true);
      api
        .get<TranscriptSegment[]>(`/documents/${documentId}/transcript`, { auth: true })
        .then(setTranscript)
        .catch(() => setTranscript([]))
        .finally(() => setLoadingTranscript(false));
    }, [showTranscript, documentId, transcript.length]);

    const activeIndex = transcript.findIndex(
      (s) => s.start_time != null && s.end_time != null && currentTime >= s.start_time && currentTime < s.end_time
    );

    useEffect(() => {
      if (activeIndex < 0) return;
      segmentRefs.current[activeIndex]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }, [activeIndex]);

    const mediaProps = {
      ref: mediaRef,
      src: getMediaUrl(documentId),
      controls: true,
      onTimeUpdate: (e: React.SyntheticEvent<HTMLMediaElement>) => setCurrentTime(e.currentTarget.currentTime),
      className: "w-full rounded-lg bg-black",
    };

    return (
      <div className="border-b border-neutral-200 dark:border-neutral-800 px-6 py-3">
        <div className="max-w-2xl mx-auto">
          {isVideo ? (
            // eslint-disable-next-line jsx-a11y/media-has-caption
            <video {...mediaProps} style={{ maxHeight: 220 }} />
          ) : (
            // eslint-disable-next-line jsx-a11y/media-has-caption
            <audio {...mediaProps} className="w-full" />
          )}

          <button
            onClick={() => setShowTranscript((v) => !v)}
            className="mt-2 flex items-center gap-1 text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 transition-colors"
          >
            {showTranscript ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {showTranscript ? "Hide transcript" : "View transcript"}
          </button>

          <AnimatePresence>
            {showTranscript && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-neutral-200 dark:border-neutral-800 divide-y divide-neutral-100 dark:divide-neutral-800">
                  {loadingTranscript && (
                    <p className="text-xs text-neutral-400 dark:text-neutral-500 px-3 py-2">Loading transcript...</p>
                  )}
                  {!loadingTranscript && transcript.length === 0 && (
                    <p className="text-xs text-neutral-400 dark:text-neutral-500 px-3 py-2">No transcript available.</p>
                  )}
                  {transcript.map((seg, i) => (
                    <button
                      key={i}
                      ref={(el) => {
                        segmentRefs.current[i] = el;
                      }}
                      onClick={() => {
                        if (seg.start_time != null && mediaRef.current) {
                          mediaRef.current.currentTime = seg.start_time;
                          mediaRef.current.play().catch(() => {});
                        }
                      }}
                      className={`w-full flex gap-2 text-left px-3 py-1.5 text-xs transition-colors ${
                        i === activeIndex
                          ? "bg-amber-50 dark:bg-amber-950/30 text-neutral-900 dark:text-neutral-100"
                          : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
                      }`}
                    >
                      <span className="shrink-0 font-mono text-neutral-400 dark:text-neutral-500">
                        {seg.start_time != null ? formatTimestamp(seg.start_time) : "--:--"}
                      </span>
                      <span>{seg.text}</span>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    );
  }
);

export default MediaPlayer;
