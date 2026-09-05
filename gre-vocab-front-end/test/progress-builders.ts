import type {
  LearningInsights,
  LearningProgressSummary,
} from "@/lib/api/generated/schema.generated";

export function learningProgress(): LearningProgressSummary {
  return {
    corpus: {
      version: "m1-v2",
      total: 3034,
      unseen: 3000,
      learning: 20,
      reviewing: 9,
      mastered: 5,
    },
    actionable: {
      due_now: 7,
      due_today: 11,
      has_active_session: true,
    },
    today: {
      date: "2026-08-28",
      timezone: "America/Chicago",
      sessions_started: 1,
      sessions_completed: 0,
      answers: 8,
      remembered: 6,
      forgot: 2,
    },
  };
}

function weeklyCurve(): LearningInsights["learning_curve"] {
  return Array.from({ length: 12 }, (_, index) => {
    const startsAt = new Date(Date.UTC(2026, 5, 8 + index * 7));
    const endsAt = new Date(startsAt);
    endsAt.setUTCDate(endsAt.getUTCDate() + (index === 11 ? 5 : 6));
    return {
      starts_on: startsAt.toISOString().slice(0, 10),
      ends_on: endsAt.toISOString().slice(0, 10),
      unseen: 3000 - index,
      learning: index,
      reviewing: 29,
      mastered: 5,
    };
  });
}

export function learningInsights(): LearningInsights {
  return {
    as_of_date: "2026-08-29",
    timezone: "America/Chicago",
    review_recall: {
      current: {
        starts_on: "2026-08-23",
        ends_on: "2026-08-29",
        remembered: 8,
        answers: 10,
        rate_percent: 80,
        has_sufficient_data: true,
      },
      previous: {
        starts_on: "2026-08-16",
        ends_on: "2026-08-22",
        remembered: 6,
        answers: 10,
        rate_percent: 60,
        has_sufficient_data: true,
      },
      change_percentage_points: 20,
    },
    consistency: {
      calendar_starts_on: "2026-06-08",
      calendar_ends_on: "2026-08-29",
      current_streak_days: 3,
      study_days: [{ date: "2026-08-29", answers: 5, words_practiced: 4 }],
    },
    learning_curve: weeklyCurve(),
  };
}
