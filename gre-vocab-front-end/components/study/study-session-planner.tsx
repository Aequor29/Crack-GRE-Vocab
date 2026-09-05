import { Button } from "@heroui/react/button";
import { Slider } from "@heroui/react/slider";

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
          Start with today&apos;s reviews and your chosen number of new words. Keep practicing until
          every word is done for the day. You can pause and return anytime.
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
            <Button className="w-fit" onPress={onRestore} size="sm" variant="tertiary">
              Restore again
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-5 rounded-3xl border border-black/10 p-6 dark:border-white/10 sm:grid-cols-[1fr_auto] sm:items-end">
        <div>
          <p className="font-bold">New-word target</p>
          <p className="mt-2 text-sm font-normal text-foreground/60">
            Choose from 0 to 20. Current target: {newWordTarget}.
          </p>
          <Slider
            aria-label="New-word target"
            className="mt-4"
            maxValue={20}
            minValue={0}
            onChange={(value) => onTargetChange(Array.isArray(value) ? (value[0] ?? 0) : value)}
            value={newWordTarget}
          >
            <Slider.Track>
              <Slider.Fill />
              <Slider.Thumb />
            </Slider.Track>
          </Slider>
        </div>
        <Button isDisabled={starting} isPending={starting} onPress={onStart} variant="primary">
          {starting ? "Planning…" : "Start session"}
        </Button>
      </div>
    </div>
  );
}
