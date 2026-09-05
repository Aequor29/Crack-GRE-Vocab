import type {
  StudyAnswerResponse,
  StudySense,
  StudySession,
  StudySessionItem,
} from "@/lib/api/generated/schema.generated";

const defaultSense: StudySense = {
  definition: "To become less intense.",
  example: "The storm began to abate.",
  part_of_speech: "verb",
  position: 1,
};

export function buildStudyItem(overrides: Partial<StudySessionItem> = {}): StudySessionItem {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    kind: "new",
    position: 1,
    pronunciation: "/abate/",
    senses: [{ ...defaultSense }],
    term: "abate",
    word_id: "00000000-0000-4000-8000-000000000002",
    ...overrides,
  };
}

export function buildStudySession(overrides: Partial<StudySession> = {}): StudySession {
  const currentItem = Object.hasOwn(overrides, "current_item")
    ? (overrides.current_item ?? null)
    : buildStudyItem();
  return {
    cleared_word_count: 0,
    corpus_version: "m1-v1",
    created_at: "2026-08-07T05:00:00Z",
    current_item: currentItem,
    day_ends_at: "2026-08-08T05:00:00Z",
    id: "00000000-0000-4000-8000-000000000003",
    new_word_target: 1,
    planned_new_word_count: currentItem?.kind === "new" ? 1 : 0,
    planner_version: "m1-daily-queue-v1",
    queue_state: "ready",
    remaining_word_count: currentItem ? 1 : 0,
    status: "active",
    timezone: "America/Chicago",
    word_count: currentItem ? 1 : 0,
    ...overrides,
  };
}

export function buildCompletedStudySession(overrides: Partial<StudySession> = {}): StudySession {
  const wordCount = overrides.word_count ?? 1;
  return buildStudySession({
    cleared_word_count: wordCount,
    current_item: null,
    ended_at: "2026-08-07T05:01:00Z",
    queue_state: "completed",
    remaining_word_count: 0,
    status: "completed",
    word_count: wordCount,
    ...overrides,
  });
}

export function buildStudyAnswerResponse(
  session: StudySession,
  overrides: Partial<StudyAnswerResponse> = {},
): StudyAnswerResponse {
  return {
    answer: {
      accepted_at: "2026-08-07T05:01:00Z",
      client_request_id: "00000000-0000-4000-8000-000000000004",
      id: "00000000-0000-4000-8000-000000000005",
      item_id: "00000000-0000-4000-8000-000000000001",
      rating: "remembered",
      submitted_at: "2026-08-07T05:01:00Z",
    },
    outcome: {
      id: "00000000-0000-4000-8000-000000000006",
      next_due_at: "2026-08-07T05:11:00Z",
      next_phase: "learning",
      occurred_at: "2026-08-07T05:01:00Z",
      previous_phase: "",
      review_number: 1,
      scheduler_version: "m1-fsrs-6.3.1-binary-v1",
    },
    replayed: false,
    session,
    ...overrides,
  };
}
