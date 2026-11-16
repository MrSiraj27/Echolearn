"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { adminApi } from "@/lib/admin-api";

interface Step {
  step: string;
  ok: boolean;
  detail: string;
  ms: number;
}

/** Runs every step an upload needs to become searchable on the live server and shows
 *  which one fails, with the real error. Use when uploads fail with "indexing failed". */
export default function IndexHealthCard() {
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await adminApi.post<{ ok: boolean; steps: Step[] }>("/admin/system/index-health");
      setSteps(res.steps);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't run the check.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mb-8 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-neutral-800 dark:text-neutral-200">Search index health</p>
          <p className="text-xs text-neutral-500">
            Tests the embedding model and vector store on this server. Writes one test chunk and deletes it.
          </p>
        </div>
        <button
          onClick={run}
          disabled={running}
          className="flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {running && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {running ? "Checking…" : "Run check"}
        </button>
      </div>
      {error && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>}
      {steps && (
        <ul className="mt-3 space-y-2">
          {steps.map((s) => (
            <li key={s.step} className="flex items-start gap-2 text-sm">
              {s.ok ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              ) : (
                <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
              )}
              <span className="min-w-0">
                <span className="font-medium">{s.step}</span>
                {s.ms > 0 && <span className="text-xs text-neutral-400"> · {s.ms} ms</span>}
                <span className={`block break-words text-xs ${s.ok ? "text-neutral-500" : "text-red-600 dark:text-red-400"}`}>
                  {s.detail}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
