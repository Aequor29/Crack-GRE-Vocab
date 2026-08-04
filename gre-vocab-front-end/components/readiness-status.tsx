"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { checkReadiness, type ReadinessResult } from "@/lib/api/readiness";

type ReadinessDisplayState = "checking" | "retrying" | ReadinessResult;

const statusCopy: Record<ReadinessDisplayState, string> = {
  checking: "Checking local services…",
  retrying: "Retrying local services…",
  ready: "Backend and database ready",
  "database-unavailable": "Database unavailable",
  "backend-unavailable": "Backend unavailable",
};

const statusTone: Record<ReadinessDisplayState, string> = {
  checking: "bg-foreground/45",
  retrying: "bg-accent",
  ready: "bg-emerald-500 dark:bg-emerald-400",
  "database-unavailable": "bg-amber-500 dark:bg-amber-400",
  "backend-unavailable": "bg-rose-500 dark:bg-rose-400",
};

export function ReadinessStatus() {
  const [state, setState] = useState<ReadinessDisplayState>("checking");
  const activeRequest = useRef<AbortController | null>(null);
  const requestId = useRef(0);

  const runCheck = useCallback(async (pendingState: "checking" | "retrying") => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    const currentRequestId = ++requestId.current;
    activeRequest.current = controller;
    setState(pendingState);

    try {
      const result = await checkReadiness({ signal: controller.signal });
      if (!controller.signal.aborted && currentRequestId === requestId.current) {
        setState(result);
      }
    } catch {
      if (!controller.signal.aborted && currentRequestId === requestId.current) {
        setState("backend-unavailable");
      }
    }
  }, []);

  useEffect(() => {
    void runCheck("checking");
    return () => activeRequest.current?.abort();
  }, [runCheck]);

  const retryVisible =
    state === "retrying" || state === "database-unavailable" || state === "backend-unavailable";

  return (
    <div className="flex items-start justify-between gap-6 border-t border-black/10 py-4 dark:border-white/10">
      <dt className="text-sm text-foreground/70">Typed local health path</dt>
      <dd className="flex max-w-52 flex-col items-end gap-2 text-right">
        <p
          aria-atomic="true"
          aria-live="polite"
          className="inline-flex items-center gap-2 text-xs font-bold text-foreground"
          role="status"
        >
          <span
            aria-hidden="true"
            className={`size-2 shrink-0 rounded-full ${statusTone[state]}`}
          />
          {statusCopy[state]}
        </p>
        {retryVisible ? (
          <button
            className="rounded-full border border-foreground/20 px-3 py-1 text-xs font-bold text-foreground transition-colors hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-wait disabled:opacity-60"
            disabled={state === "retrying"}
            onClick={() => void runCheck("retrying")}
            type="button"
          >
            {state === "retrying" ? "Trying again…" : "Try again"}
          </button>
        ) : null}
      </dd>
    </div>
  );
}
