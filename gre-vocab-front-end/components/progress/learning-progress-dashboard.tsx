"use client";

import { Button, buttonVariants } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { ProgressBar } from "@heroui/react/progress-bar";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { LearningProgressSummary } from "@/lib/api/generated/schema.generated";
import { getLearningProgress, ProgressApiError } from "@/lib/api/progress";

type ProgressState =
  | { status: "loading" }
  | { status: "loaded"; summary: LearningProgressSummary }
  | { status: "error" };

type LearningProgressDashboardProps = {
  onAuthenticationExpired: () => void;
};

const numberFormatter = new Intl.NumberFormat("en-US");

function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

function formatNumber(value: number): string {
  return numberFormatter.format(value);
}

function ProgressLoading() {
  return (
    <Card
      aria-label="Loading your progress"
      className="grid min-h-72 place-items-center rounded-[2rem]"
      role="status"
      variant="secondary"
    >
      <p className="text-foreground/65">Loading your progress…</p>
    </Card>
  );
}

function ProgressError({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="rounded-[2rem] p-7 sm:p-9" variant="secondary">
      <h2 className="text-2xl font-black tracking-tight">Progress</h2>
      <p className="mt-3 text-foreground/70" role="alert">
        We couldn&apos;t load your progress.
      </p>
      <Button className="mt-6" onPress={onRetry} type="button" variant="primary">
        Try again
      </Button>
    </Card>
  );
}

function Coverage({ summary }: { summary: LearningProgressSummary }) {
  const seen = summary.corpus.total - summary.corpus.unseen;
  const percent = summary.corpus.total === 0 ? 0 : Math.round((seen / summary.corpus.total) * 100);

  return (
    <Card className="rounded-[2rem] p-7 sm:p-9 lg:col-span-2" variant="secondary">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-accent">Learning progress</p>
      <p className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
        {formatNumber(seen)} of {formatNumber(summary.corpus.total)} words seen
      </p>
      <ProgressBar
        aria-label={`${percent}% of words seen`}
        className="mt-7"
        color="accent"
        maxValue={100}
        value={percent}
      >
        <ProgressBar.Track>
          <ProgressBar.Fill />
        </ProgressBar.Track>
      </ProgressBar>
      <dl className="mt-7 grid grid-cols-3 gap-4 border-t border-black/10 pt-6 dark:border-white/10">
        <div>
          <dt className="text-sm text-foreground/60">Learning</dt>
          <dd className="mt-1 text-2xl font-black">{formatNumber(summary.corpus.learning)}</dd>
        </div>
        <div>
          <dt className="text-sm text-foreground/60">Review</dt>
          <dd className="mt-1 text-2xl font-black">{formatNumber(summary.corpus.review)}</dd>
        </div>
        <div>
          <dt className="text-sm text-foreground/60">Unseen</dt>
          <dd className="mt-1 text-2xl font-black">{formatNumber(summary.corpus.unseen)}</dd>
        </div>
      </dl>
    </Card>
  );
}

function StudyAction({ summary }: { summary: LearningProgressSummary }) {
  const actionLabel = summary.actionable.has_active_session
    ? "Continue studying"
    : "Start studying";
  return (
    <Card
      className="flex flex-col rounded-[2rem] bg-foreground p-7 text-background sm:p-9"
      variant="transparent"
    >
      <p className="text-sm font-bold uppercase tracking-[0.18em] opacity-60">Next up</p>
      <p className="mt-4 text-5xl font-black tracking-[-0.05em]">
        {formatNumber(summary.actionable.due_now)}
      </p>
      <p className="mt-1 text-lg font-bold">due now</p>
      <p className="mt-3 opacity-65">{formatNumber(summary.actionable.due_today)} due today</p>
      <Link className={`${buttonVariants({ variant: "primary" })} mt-8 w-fit`} href="/study">
        {actionLabel}
      </Link>
    </Card>
  );
}

function TodayActivity({ summary }: { summary: LearningProgressSummary }) {
  return (
    <Card className="rounded-[2rem] p-7 sm:p-8 lg:col-span-3" variant="secondary">
      <div className="grid gap-6 sm:grid-cols-[minmax(12rem,1fr)_2fr] sm:items-end">
        <div>
          <h2 className="text-2xl font-black tracking-tight">Today</h2>
          <p className="mt-4 text-4xl font-black tracking-tight">
            {formatNumber(summary.today.answers)} answers
          </p>
        </div>
        <dl className="grid grid-cols-3 gap-3">
          <div className="rounded-2xl bg-background p-4">
            <dt className="text-sm text-foreground/60">Remembered</dt>
            <dd className="mt-1 text-2xl font-black">{formatNumber(summary.today.remembered)}</dd>
          </div>
          <div className="rounded-2xl bg-background p-4">
            <dt className="text-sm text-foreground/60">Forgot</dt>
            <dd className="mt-1 text-2xl font-black">{formatNumber(summary.today.forgot)}</dd>
          </div>
          <div className="rounded-2xl bg-background p-4">
            <dt className="text-sm text-foreground/60">Sessions</dt>
            <dd className="mt-1 text-2xl font-black">
              {formatNumber(summary.today.sessions_completed)}
            </dd>
          </div>
        </dl>
      </div>
    </Card>
  );
}

function LoadedProgress({ summary }: { summary: LearningProgressSummary }) {
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Coverage summary={summary} />
      <StudyAction summary={summary} />
      <TodayActivity summary={summary} />
    </div>
  );
}

export function LearningProgressDashboard({
  onAuthenticationExpired,
}: LearningProgressDashboardProps) {
  const [state, setState] = useState<ProgressState>({ status: "loading" });

  const loadProgress = useCallback(
    async (signal?: AbortSignal) => {
      setState({ status: "loading" });
      try {
        const summary = await getLearningProgress(browserTimezone(), { signal });
        setState({ status: "loaded", summary });
      } catch (error) {
        if (signal?.aborted) {
          return;
        }
        if (error instanceof ProgressApiError && error.kind === "unauthenticated") {
          onAuthenticationExpired();
        }
        setState({ status: "error" });
      }
    },
    [onAuthenticationExpired],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadProgress(controller.signal);
    return () => controller.abort();
  }, [loadProgress]);

  if (state.status === "loading") {
    return <ProgressLoading />;
  }
  if (state.status === "error") {
    return <ProgressError onRetry={() => void loadProgress()} />;
  }
  return <LoadedProgress summary={state.summary} />;
}
