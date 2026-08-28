import { Button } from "@heroui/react";

import type { StudyNotice } from "@/components/study/types";

type StudySessionPlannerProps = {
  newWordTarget: number;
  notice: StudyNotice | null;
  onRestore: () => void;
  onStart: () => void;
  onTargetChange: (target: number) => void;
  starting: boolean;
};

export function StudySessionPlanner({
  newWordTarget,
  notice,
  onRestore,
  onStart,
  onTargetChange,
  starting,
}: StudySessionPlannerProps) {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-black tracking-tight">Start a focused session</h2>
        <p className="mt-2 max-w-2xl text-foreground/65">
          Due reviews come first. We&apos;ll then add up to your chosen number of new words, with a
          limit of 30 cards per sitting.
        </p>
        <p className="mt-4 max-w-2xl border-l-2 border-accent pl-4 text-sm leading-6 text-foreground/65">
          Recall each word first, reveal its meaning, then grade yourself honestly as Remembered or
          Forgot.
        </p>
      </div>

      {notice ? (
        <div className="space-y-3 rounded-2xl bg-rose-500/10 p-4" role="alert">
          <p className="text-sm font-medium">{notice.message}</p>
          {notice.retryable ? (
            <button
              className="text-sm font-bold text-accent underline-offset-4 hover:underline"
              onClick={onRestore}
              type="button"
            >
              Restore again
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-5 rounded-3xl border border-black/10 p-6 dark:border-white/10 sm:grid-cols-[1fr_auto] sm:items-end">
        <label className="grid gap-2 font-bold" htmlFor="new-word-target">
          New-word target
          <span className="text-sm font-normal text-foreground/60">
            Choose from 0 to 20. Current target: {newWordTarget}.
          </span>
          <input
            className="h-2 w-full cursor-pointer accent-accent"
            id="new-word-target"
            max={20}
            min={0}
            onChange={(event) => onTargetChange(Number(event.target.value))}
            type="range"
            value={newWordTarget}
          />
        </label>
        <Button isDisabled={starting} isPending={starting} onPress={onStart} variant="primary">
          {starting ? "Planning…" : "Start session"}
        </Button>
      </div>
    </div>
  );
}
