import { ProgressBar } from "@heroui/react/progress-bar";

type StudyProgressProps = {
  clearedWordCount: number;
  wordCount: number;
};

export function StudyProgress({ clearedWordCount, wordCount }: StudyProgressProps) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-bold text-foreground/60">
        {clearedWordCount} of {wordCount} words done today
      </p>
      <ProgressBar
        aria-label="Words done today"
        className="w-full"
        maxValue={wordCount}
        value={clearedWordCount}
      >
        <ProgressBar.Track>
          <ProgressBar.Fill />
        </ProgressBar.Track>
      </ProgressBar>
    </div>
  );
}
