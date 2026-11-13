"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Loader2, Mic, Pause, Play, RotateCcw, Square, Upload } from "lucide-react";
import { blobToWav } from "@/lib/wav";

export const MIN_SAMPLE_SECONDS = 3;
export const MAX_SAMPLE_SECONDS = 20;
const MIN_RMS = 0.004; // below this the clip is effectively silence

type Phase = "idle" | "requesting" | "recording" | "paused" | "ready" | "submitting";

interface Prepared {
  wav: Blob;
  seconds: number;
  url: string;
  source: "recording" | "upload";
}

function micErrorMessage(err: unknown): string {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Microphone access was blocked. Allow the microphone for this site in your browser's address bar, then try again, or upload a file instead.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "No microphone was found. Connect one and try again, or upload a file instead.";
  if (name === "NotReadableError" || name === "AbortError")
    return "Your microphone is being used by another app or couldn't start. Close other apps using it and try again.";
  return "Couldn't start recording. Try again, or upload a file instead.";
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find((t) =>
    MediaRecorder.isTypeSupported(t)
  );
}

function fmt(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Record (or pick) a voice sample, preview it, confirm consent, then hand a validated WAV
 * to `onSubmit`. Nothing is uploaded until the user presses "Use this sample".
 */
export default function VoiceSampleRecorder({
  onSubmit,
  onCancel,
}: {
  onSubmit: (wav: Blob) => Promise<void>;
  onCancel?: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const segmentStartRef = useRef(0); // when the current (un-paused) stretch began
  const accumulatedRef = useRef(0); // ms recorded before the current stretch
  const interruptedRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const stopVisuals = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (tickRef.current) clearInterval(tickRef.current);
    tickRef.current = null;
  }, []);

  const releaseMic = useCallback(() => {
    stopVisuals();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, [stopVisuals]);

  // Release the microphone and object URLs if the component goes away mid-recording.
  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.onstop = null;
        recorderRef.current.stop();
      }
      releaseMic();
    };
  }, [releaseMic]);
  useEffect(() => {
    const url = prepared?.url;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [prepared]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    const bars = 48;
    const step = Math.floor(data.length / bars);
    const color = getComputedStyle(canvas).color;
    ctx.fillStyle = color;
    for (let i = 0; i < bars; i++) {
      let peak = 0;
      for (let j = 0; j < step; j++) peak = Math.max(peak, Math.abs(data[i * step + j] - 128) / 128);
      const h = Math.max(2, peak * height * 0.95);
      const x = (i * width) / bars;
      ctx.fillRect(x + 1, (height - h) / 2, width / bars - 2, h);
    }
    rafRef.current = requestAnimationFrame(draw);
  }, []);

  const currentElapsed = () =>
    accumulatedRef.current + (segmentStartRef.current ? performance.now() - segmentStartRef.current : 0);

  async function prepare(blob: Blob, source: Prepared["source"]) {
    try {
      const { wav, seconds, rms } = await blobToWav(blob);
      if (seconds < MIN_SAMPLE_SECONDS || seconds > MAX_SAMPLE_SECONDS) {
        setError(
          `That clip is ${seconds.toFixed(1)}s long. Please use ${MIN_SAMPLE_SECONDS}–${MAX_SAMPLE_SECONDS} seconds of speech.`
        );
        setPhase("idle");
        return;
      }
      if (rms < MIN_RMS) {
        setError("We couldn't hear any speech in that clip. Check your microphone is unmuted and speak clearly, then try again.");
        setPhase("idle");
        return;
      }
      setPrepared({ wav, seconds, url: URL.createObjectURL(wav), source });
      setPhase("ready");
    } catch {
      setError(
        source === "upload"
          ? "That file couldn't be read as audio. Try a WAV, MP3, M4A, OGG or WebM file."
          : "The recording couldn't be processed. Please record again."
      );
      setPhase("idle");
    }
  }

  async function start() {
    setError(null);
    setPrepared(null);
    setConsent(false);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError(
        window.isSecureContext
          ? "Recording isn't supported in this browser. Upload a file instead."
          : "Recording only works on a secure (https) page. Upload a file instead."
      );
      return;
    }
    setPhase("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      setError(micErrorMessage(err));
      setPhase("idle");
      return;
    }
    streamRef.current = stream;
    interruptedRef.current = false;

    const AudioCtx: typeof AudioContext =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    try {
      const actx = new AudioCtx();
      const analyser = actx.createAnalyser();
      analyser.fftSize = 1024;
      actx.createMediaStreamSource(stream).connect(analyser);
      audioCtxRef.current = actx;
      analyserRef.current = analyser;
    } catch {
      // The waveform is decoration; recording still works without it.
    }

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunksRef.current = [];
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      const recordedMs = currentElapsed();
      segmentStartRef.current = 0;
      releaseMic();
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      if (interruptedRef.current) {
        setError("Recording stopped because the microphone was disconnected. Please record again.");
        setPhase("idle");
        return;
      }
      if (!blob.size || recordedMs < 500) {
        setError("Nothing was recorded. Please try again.");
        setPhase("idle");
        return;
      }
      void prepare(blob, "recording");
    };
    // A mic that's unplugged (or revoked) mid-recording ends the track.
    stream.getAudioTracks().forEach((t) =>
      t.addEventListener("ended", () => {
        interruptedRef.current = true;
        if (recorder.state !== "inactive") recorder.stop();
      })
    );

    recorderRef.current = recorder;
    recorder.start(250);
    accumulatedRef.current = 0;
    segmentStartRef.current = performance.now();
    setElapsedMs(0);
    setPhase("recording");
    rafRef.current = requestAnimationFrame(draw);
    tickRef.current = setInterval(() => {
      const ms = currentElapsed();
      setElapsedMs(ms);
      if (ms >= MAX_SAMPLE_SECONDS * 1000) stop();
    }, 200);
  }

  function pause() {
    const r = recorderRef.current;
    if (!r || r.state !== "recording") return;
    r.pause();
    accumulatedRef.current = currentElapsed();
    segmentStartRef.current = 0;
    stopVisuals();
    setElapsedMs(accumulatedRef.current);
    setPhase("paused");
  }

  function resume() {
    const r = recorderRef.current;
    if (!r || r.state !== "paused") return;
    r.resume();
    segmentStartRef.current = performance.now();
    setPhase("recording");
    rafRef.current = requestAnimationFrame(draw);
    tickRef.current = setInterval(() => {
      const ms = currentElapsed();
      setElapsedMs(ms);
      if (ms >= MAX_SAMPLE_SECONDS * 1000) stop();
    }, 200);
  }

  function stop() {
    const r = recorderRef.current;
    if (r && r.state !== "inactive") {
      stopVisuals();
      r.stop(); // -> onstop -> prepare()
    }
  }

  function reset() {
    setPrepared(null);
    setConsent(false);
    setError(null);
    setElapsedMs(0);
    setPhase("idle");
  }

  async function submit() {
    if (!prepared || !consent) return;
    setPhase("submitting");
    setError(null);
    try {
      await onSubmit(prepared.wav);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setPhase("ready");
    }
  }

  function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setConsent(false);
    if (file.size > 10 * 1024 * 1024) {
      setError("That file is too large. Use a clip under 10 MB.");
      return;
    }
    setPhase("submitting");
    void prepare(file, "upload");
  }

  const live = phase === "recording" || phase === "paused";
  const tooShort = elapsedMs < MIN_SAMPLE_SECONDS * 1000;

  return (
    <div className="space-y-4">
      {(phase === "idle" || phase === "requesting") && !prepared && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={start}
              disabled={phase === "requesting"}
              className="flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3 py-2 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-60 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-white"
            >
              {phase === "requesting" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Mic className="h-3.5 w-3.5" />}
              {phase === "requesting" ? "Waiting for microphone…" : "Record voice"}
            </button>
            <span className="text-xs text-neutral-400">or</span>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-2 text-xs font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
            >
              <Upload className="h-3.5 w-3.5" />
              Upload audio
            </button>
            {onCancel && (
              <button onClick={onCancel} className="ml-auto text-xs text-neutral-500 hover:underline">
                Cancel
              </button>
            )}
          </div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            Your browser will ask to use the microphone. Find a quiet place and read a few natural sentences for{" "}
            {MIN_SAMPLE_SECONDS}–{MAX_SAMPLE_SECONDS} seconds. You can listen before anything is uploaded.
          </p>
        </div>
      )}

      {live && (
        <div className="rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
          <div className="mb-3 flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 font-medium" aria-live="polite">
              <span
                className={`h-2 w-2 rounded-full ${phase === "recording" ? "bg-red-500 animate-pulse" : "bg-neutral-400"}`}
                aria-hidden
              />
              {phase === "recording" ? "Recording" : "Paused"}
            </span>
            <span className="tabular-nums text-neutral-500">
              {fmt(elapsedMs)} / {fmt(MAX_SAMPLE_SECONDS * 1000)}
            </span>
          </div>
          <canvas
            ref={canvasRef}
            width={480}
            height={56}
            className="h-14 w-full text-neutral-800 dark:text-neutral-200"
            aria-hidden
          />
          <div className="mt-1 h-1 rounded bg-neutral-100 dark:bg-neutral-800">
            <div
              className={`h-1 rounded ${tooShort ? "bg-neutral-400" : "bg-emerald-500"}`}
              style={{ width: `${Math.min(100, (elapsedMs / (MAX_SAMPLE_SECONDS * 1000)) * 100)}%` }}
            />
          </div>
          <div className="mt-3 flex items-center gap-2">
            {phase === "recording" ? (
              <button onClick={pause} className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-medium dark:border-neutral-700">
                <Pause className="h-3.5 w-3.5" /> Pause
              </button>
            ) : (
              <button onClick={resume} className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-medium dark:border-neutral-700">
                <Play className="h-3.5 w-3.5" /> Resume
              </button>
            )}
            <button
              onClick={stop}
              disabled={tooShort}
              title={tooShort ? `Record at least ${MIN_SAMPLE_SECONDS} seconds` : undefined}
              className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              <Square className="h-3.5 w-3.5" /> Stop
            </button>
            <span className="text-[11px] text-neutral-400">
              {tooShort ? `Keep going: at least ${MIN_SAMPLE_SECONDS}s` : `Stops automatically at ${MAX_SAMPLE_SECONDS}s`}
            </span>
          </div>
        </div>
      )}

      {phase === "submitting" && !prepared && (
        <p className="flex items-center gap-2 text-xs text-neutral-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Checking the audio…
        </p>
      )}

      {prepared && (phase === "ready" || phase === "submitting") && (
        <div className="space-y-3 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
          <p className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
            Listen back ({prepared.seconds.toFixed(1)}s{prepared.source === "upload" ? ", from your file" : ""})
          </p>
          <audio controls src={prepared.url} className="h-9 w-full" />
          <label className="flex cursor-pointer items-start gap-2.5 text-xs text-neutral-600 dark:text-neutral-300">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              disabled={phase === "submitting"}
              className="mt-0.5 h-4 w-4 accent-neutral-900 dark:accent-neutral-100"
            />
            <span>
              This is my own voice, or I have the speaker&apos;s explicit permission to clone it. I understand it will be
              used to read answers aloud in this voice.
            </span>
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={submit}
              disabled={!consent || phase === "submitting"}
              className="flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
            >
              {phase === "submitting" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              {phase === "submitting" ? "Uploading…" : "Use this sample"}
            </button>
            <button
              onClick={reset}
              disabled={phase === "submitting"}
              className="flex items-center gap-1.5 rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-medium disabled:opacity-40 dark:border-neutral-700"
            >
              <RotateCcw className="h-3.5 w-3.5" /> {prepared.source === "upload" ? "Choose another" : "Record again"}
            </button>
          </div>
          {phase === "submitting" && (
            <p className="text-[11px] text-neutral-500">
              Uploading and preparing your voice. Creating the voice model can take a little while; you can keep using
              the app.
            </p>
          )}
        </div>
      )}

      <input ref={fileInputRef} type="file" accept="audio/*" className="hidden" onChange={onFilePicked} />
      {error && (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
