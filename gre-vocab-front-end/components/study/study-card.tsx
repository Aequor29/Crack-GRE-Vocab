import { Button } from "@heroui/react";
import type { RefObject } from "react";

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
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm font-bold text-foreground/60">
        <p>
          Card {session.answered_count + 1} of {session.item_count}
        </p>
        <p>{item.kind === "due" ? "Due review" : "New word"}</p>
      </div>

      <div
        className="h-2 overflow-hidden rounded-full bg-foreground/10"
        role="progressbar"
        aria-label="Study progress"
        aria-valuemax={session.item_count}
        aria-valuemin={0}
        aria-valuenow={session.answered_count}
      >
        <div
          className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${(session.answered_count / session.item_count) * 100}%` }}
        />
      </div>

      <article className="min-h-80 rounded-[2rem] border border-black/10 bg-background/70 p-7 text-center dark:border-white/10 sm:p-12">
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

        {revealed ? (
          <div className="mx-auto mt-10 max-w-2xl space-y-8 border-t border-black/10 pt-8 text-left dark:border-white/10">
            {item.senses.map((sense) => (
              <div className="space-y-3" key={`${sense.position}-${sense.definition}`}>
                <p className="text-xl font-semibold leading-8 sm:text-2xl sm:leading-9">
                  <span className="mr-3 text-sm italic text-foreground/55">
                    {sense.part_of_speech}
                  </span>
                  {sense.definition}
                </p>
                {sense.example ? (
                  <p className="text-base italic leading-7 text-foreground/70 sm:text-lg sm:leading-8">
                    “{sense.example}”
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mx-auto mt-10 max-w-md text-base leading-7 text-foreground/60">
            Say the meaning to yourself before revealing the answer.
          </p>
        )}
      </article>

      {notice ? (
        <div className="space-y-3 rounded-2xl bg-rose-500/10 p-4" role="alert">
          <p className="text-sm font-medium">{notice.message}</p>
          {notice.retryable && pending ? (
            <button
              className="text-sm font-bold text-accent underline-offset-4 hover:underline disabled:opacity-60"
              disabled={submitting}
              onClick={onRetry}
              type="button"
            >
              Retry the same answer
            </button>
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
