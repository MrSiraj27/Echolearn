"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Tracks which items have an async action in flight, so a button can show a spinner
 * (and ignore repeat clicks) for exactly the row/item being acted on.
 *
 *   const { isBusy, run } = useBusy();
 *   <button disabled={isBusy(`del:${id}`)} onClick={() => run(`del:${id}`, () => deleteThing(id))}>
 *
 * Errors are logged rather than rethrown: these handlers are fired from onClick, where a
 * rejection would otherwise surface as an unhandled promise rejection.
 */
export function useBusy() {
  const [busy, setBusy] = useState<ReadonlySet<string>>(new Set());
  const inFlight = useRef<Set<string>>(new Set());

  const run = useCallback(async <T,>(key: string, fn: () => Promise<T>): Promise<T | undefined> => {
    if (inFlight.current.has(key)) return undefined;
    inFlight.current.add(key);
    setBusy(new Set(inFlight.current));
    try {
      return await fn();
    } catch (err) {
      console.error(err);
      return undefined;
    } finally {
      inFlight.current.delete(key);
      setBusy(new Set(inFlight.current));
    }
  }, []);

  const isBusy = useCallback((key: string) => busy.has(key), [busy]);

  return { isBusy, run };
}
