"use client";

import { Button } from "@heroui/react/button";
import { Card } from "@heroui/react/card";
import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  LearningInsights,
  ReviewRecallPeriod,
  StudyConsistency,
  WeeklyLearningCurvePoint,
} from "@/lib/api/generated/schema.generated";
import { getLearningInsights, ProgressApiError } from "@/lib/api/progress";

type InsightsState =
  | { status: "loading" }
  | { status: "loaded"; insights: LearningInsights }
  | { status: "error" };

type LearningInsightsDashboardProps = {
  onAuthenticationExpired: () => void;
};

const numberFormatter = new Intl.NumberFormat("en-US");
const dayFormatter = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  month: "long",
  timeZone: "UTC",
  year: "numeric",
});

function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

function parseCalendarDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function formatCalendarDate(value: string): string {
  return dayFormatter.format(parseCalendarDate(value));
}

function enumerateCalendarDates(startsOn: string, endsOn: string): string[] {
  const current = parseCalendarDate(startsOn);
  const end = parseCalendarDate(endsOn);
  const dates: string[] = [];
  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return dates;
}

function recallComparison(change: number | null): string | null {
  if (change === null) {
    return null;
  }
  const sign = change > 0 ? "+" : "";
  const unit = Math.abs(change) === 1 ? "point" : "points";
  return `${sign}${change} ${unit} from the previous 7 days`;
}

function ReviewRecallCard({
  period,
  change,
}: {
  period: ReviewRecallPeriod;
  change: number | null;
}) {
  const comparison = recallComparison(change);
  return (
    <Card className="rounded-[2rem] p-7 sm:p-9" variant="secondary">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-accent">Recall trend</p>
      <h2 className="mt-2 text-2xl font-black tracking-tight">Review recall</h2>
      {period.rate_percent === null ? (
        <p className="mt-7 text-lg font-bold">No review history yet</p>
      ) : (
        <>
          <div className="mt-6 flex flex-wrap items-end gap-x-4 gap-y-2">
            <p className="text-6xl font-black tracking-[-0.06em]">{period.rate_percent}%</p>
            {!period.has_sufficient_data && (
              <p className="mb-2 rounded-full bg-accent/10 px-3 py-1 text-sm font-bold text-accent">
                Early trend
              </p>
            )}
          </div>
          <p className="mt-3 text-foreground/70">
            {period.remembered} of {period.answers} review answers remembered
          </p>
        </>
      )}
      {comparison && <p className="mt-4 font-bold text-accent">{comparison}</p>}
      <p className="mt-5 border-t border-foreground/10 pt-5 text-sm text-foreground/60">
        Initial learning and relearning are excluded.
      </p>
    </Card>
  );
}

function calendarCellClass(wordsPracticed: number, maximumWords: number): string {
  if (wordsPracticed === 0) {
    return "bg-foreground/5";
  }
  const intensity = wordsPracticed / Math.max(1, maximumWords);
  if (intensity <= 0.25) {
    return "bg-accent/20";
  }
  if (intensity <= 0.5) {
    return "bg-accent/40";
  }
  if (intensity <= 0.75) {
    return "bg-accent/65";
  }
  return "bg-accent";
}

function StudyDaysCard({ consistency }: { consistency: StudyConsistency }) {
  const dates = useMemo(
    () => enumerateCalendarDates(consistency.calendar_starts_on, consistency.calendar_ends_on),
    [consistency.calendar_ends_on, consistency.calendar_starts_on],
  );
  const activityByDate = useMemo(
    () => new Map(consistency.study_days.map((day) => [day.date, day])),
    [consistency.study_days],
  );
  const maximumWords = Math.max(0, ...consistency.study_days.map((day) => day.words_practiced));

  return (
    <Card className="rounded-[2rem] p-7 sm:p-9" variant="secondary">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-accent">Consistency</p>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-2xl font-black tracking-tight">Study days</h2>
        <p className="font-bold">{consistency.current_streak_days} day streak</p>
      </div>
      <p className="mt-3 text-sm text-foreground/60">Words practiced, week by week</p>
      <div className="mt-6 overflow-x-auto pb-2">
        <fieldset className="grid min-w-[29rem] grid-flow-col grid-rows-7 gap-1.5">
          <legend className="sr-only">Study activity for the last 12 weeks</legend>
          {dates.map((date) => {
            const activity = activityByDate.get(date);
            const words = activity?.words_practiced ?? 0;
            const answers = activity?.answers ?? 0;
            const label = activity
              ? `${formatCalendarDate(date)}: ${words} words practiced across ${answers} answers`
              : `${formatCalendarDate(date)}: no study activity`;
            return (
              <span
                aria-label={label}
                className={`size-3.5 rounded-[0.28rem] ${calendarCellClass(words, maximumWords)}`}
                key={date}
                role="img"
                title={label}
              />
            );
          })}
        </fieldset>
      </div>
      <p className="mt-3 text-xs text-foreground/50">
        {formatCalendarDate(consistency.calendar_starts_on)}–
        {formatCalendarDate(consistency.calendar_ends_on)}
      </p>
    </Card>
  );
}

function learningCurvePoints(curve: WeeklyLearningCurvePoint[]): string {
  const maximumSeen = Math.max(1, ...curve.map((week) => week.learning + week.review));
  return curve
    .map((week, index) => {
      const x = 12 + (index * 576) / Math.max(1, curve.length - 1);
      const seen = week.learning + week.review;
      const y = 140 - (seen * 116) / maximumSeen;
      return `${x},${y}`;
    })
    .join(" ");
}

function LearningCurveCard({ curve }: { curve: WeeklyLearningCurvePoint[] }) {
  const latest = curve.at(-1);
  const first = curve[0];
  const latestSeen = latest ? latest.learning + latest.review : 0;
  const firstSeen = first ? first.learning + first.review : 0;
  return (
    <Card className="rounded-[2rem] p-7 sm:p-9 lg:col-span-2" variant="secondary">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-accent">12 weeks</p>
          <h2 className="mt-2 text-2xl font-black tracking-tight">Learning curve</h2>
        </div>
        <p className="text-sm text-foreground/60">Words encountered week by week</p>
      </div>
      <svg
        aria-labelledby="learning-curve-title learning-curve-description"
        className="mt-6 h-44 w-full overflow-visible"
        role="img"
        viewBox="0 0 600 160"
      >
        <title id="learning-curve-title">Weekly words encountered</title>
        <desc id="learning-curve-description">
          Words encountered changed from {numberFormatter.format(firstSeen)} to{" "}
          {numberFormatter.format(latestSeen)} over 12 weeks.
        </desc>
        <path d="M 12 140 H 588" stroke="currentColor" strokeOpacity="0.12" />
        <polyline
          fill="none"
          points={learningCurvePoints(curve)}
          stroke="var(--accent)"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="6"
        />
      </svg>
      {latest && (
        <p className="mt-2 font-bold">
          {numberFormatter.format(latestSeen)} seen · {numberFormatter.format(latest.learning)}{" "}
          learning · {numberFormatter.format(latest.review)} review
        </p>
      )}
      <ol className="sr-only">
        {curve.map((week) => (
          <li key={week.starts_on}>
            Week of {formatCalendarDate(week.starts_on)}: {week.unseen} unseen, {week.learning}{" "}
            learning, {week.review} review.
          </li>
        ))}
      </ol>
    </Card>
  );
}

function LoadedInsights({ insights }: { insights: LearningInsights }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <ReviewRecallCard
        change={insights.review_recall.change_percentage_points}
        period={insights.review_recall.current}
      />
      <StudyDaysCard consistency={insights.consistency} />
      <LearningCurveCard curve={insights.learning_curve} />
    </div>
  );
}

/** Load and present backend-authoritative recall and consistency insights. */
export function LearningInsightsDashboard({
  onAuthenticationExpired,
}: LearningInsightsDashboardProps) {
  const [state, setState] = useState<InsightsState>({ status: "loading" });

  const loadInsights = useCallback(
    async (signal?: AbortSignal) => {
      setState({ status: "loading" });
      try {
        const insights = await getLearningInsights(browserTimezone(), { signal });
        setState({ status: "loaded", insights });
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
    void loadInsights(controller.signal);
    return () => controller.abort();
  }, [loadInsights]);

  if (state.status === "loading") {
    return (
      <Card
        aria-label="Loading your learning trends"
        className="grid min-h-56 place-items-center rounded-[2rem]"
        role="status"
        variant="secondary"
      >
        <p className="text-foreground/65">Loading your learning trends…</p>
      </Card>
    );
  }
  if (state.status === "error") {
    return (
      <Card className="rounded-[2rem] p-7 sm:p-9" variant="secondary">
        <h2 className="text-2xl font-black tracking-tight">Learning trends</h2>
        <p className="mt-3 text-foreground/70" role="alert">
          We couldn&apos;t load your learning trends.
        </p>
        <Button
          className="mt-6"
          onPress={() => void loadInsights()}
          type="button"
          variant="primary"
        >
          Try again
        </Button>
      </Card>
    );
  }
  return <LoadedInsights insights={state.insights} />;
}
