import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import type { RefObject } from "react";

import { StudyProgress } from "@/components/study/study-progress";
import type { StudyNotice } from "@/components/study/types";
import type { StudySession } from "@/lib/api/generated/schema.generated";
import type { RecallRating } from "@/lib/api/study";
import type { PendingStudyAnswer } from "@/lib/study/pending-answer";

type StudyCardProps = {
  notice: StudyNotice | null;
  onRating: (rating: RecallRating) => void;
  onRetry: () => void;
  onReveal: () => void;
  pending: PendingStudyAnswer | null;
  revealed: boolean;
  session: StudySession;
  submitting: boolean;
  termHeading: RefObject<HTMLHeadingElement | null>;
};

export function StudyCard({
  notice,
  onRating,
  onRetry,
  onReveal,
  pending,
  revealed,
  session,
  submitting,
  termHeading,
}: StudyCardProps) {
  const item = session.current_item;
  if (!item) {
    return null;
  }

  return (
    <div aria-busy={submitting} className="space-y-7">
      <div className="flex justify-end text-sm font-bold text-foreground/60">
        <p>{item.kind === "due" ? "Due review" : "New word"}</p>
      </div>

      <StudyProgress clearedWordCount={session.cleared_word_count} wordCount={session.word_count} />

      <Card className="rounded-[2rem] bg-background/70 p-7 text-center sm:p-12" variant="secondary">
        <div className={revealed ? undefined : "grid min-h-64 content-center"}>
          <h2
            className="text-5xl font-black tracking-[-0.05em] outline-none sm:text-7xl"
            ref={termHeading}
            tabIndex={-1}
          >
            {item.term}
          </h2>
          {item.pronunciation ? (
            <p className="mt-3 text-lg text-foreground/50">{item.pronunciation}</p>
          ) : null}
        </div>

        {revealed ? (
          <div className="mx-auto mt-10 max-w-2xl space-y-8 border-t border-black/10 pt-8 text-left dark:border-white/10">
            {item.senses.map((sense) => (
              <div className="space-y-3" key={`${sense.position}-${sense.definition}`}>
                <p className="text-2xl font-semibold leading-9 sm:text-3xl sm:leading-10">
                  <span className="mr-3 text-sm italic text-foreground/55">
                    {sense.part_of_speech}
                  </span>
                  {sense.definition}
                </p>
                {sense.example ? (
                  <p className="text-lg italic leading-8 text-foreground/70 sm:text-xl sm:leading-9">
                    “{sense.example}”
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      {notice ? (
        <div className="space-y-3 rounded-2xl bg-rose-500/10 p-4" role="alert">
          <p className="text-sm font-medium">{notice.message}</p>
          {notice.retryable && pending ? (
            <Button
              className="w-fit"
              isDisabled={submitting}
              onPress={onRetry}
              size="sm"
              variant="tertiary"
            >
              Retry the same answer
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap justify-center gap-3">
        {!revealed ? (
          <Button onPress={onReveal} size="lg" variant="primary">
            Reveal meaning
          </Button>
        ) : (
          <>
            <Button
              isDisabled={submitting || Boolean(pending)}
              isPending={submitting && pending?.rating === "forgot"}
              onPress={() => onRating("forgot")}
              size="lg"
              variant="outline"
            >
              Forgot
            </Button>
            <Button
              isDisabled={submitting || Boolean(pending)}
              isPending={submitting && pending?.rating === "remembered"}
              onPress={() => onRating("remembered")}
              size="lg"
              variant="primary"
            >
              Remembered
            </Button>
          </>
        )}
      </div>

      <p aria-live="polite" className="sr-only" role="status">
        {submitting ? "Saving your answer." : ""}
      </p>
    </div>
  );
}
