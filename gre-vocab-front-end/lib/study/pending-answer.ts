import type { RecallAnswerInput, RecallRating } from "@/lib/api/study";

const STORAGE_KEY = "crack-gre:study:pending-answer:v1";
const STORAGE_VERSION = 1;

export type PendingStudyAnswer = RecallAnswerInput & {
  learnerId: number;
  version: typeof STORAGE_VERSION;
};

function isRating(value: unknown): value is RecallRating {
  return value === "remembered" || value === "forgot";
}

function isPendingAnswer(value: unknown): value is PendingStudyAnswer {
  if (!value || typeof value !== "object") {
    return false;
  }
  const pending = value as Partial<PendingStudyAnswer>;
  return (
    pending.version === STORAGE_VERSION &&
    typeof pending.learnerId === "number" &&
    typeof pending.sessionId === "string" &&
    typeof pending.itemId === "string" &&
    typeof pending.client_request_id === "string" &&
    isRating(pending.rating)
  );
}

export function loadPendingAnswer(learnerId: number): PendingStudyAnswer | null {
  try {
    const serialized = window.sessionStorage.getItem(STORAGE_KEY);
    if (!serialized) {
      return null;
    }
    const value: unknown = JSON.parse(serialized);
    if (!isPendingAnswer(value) || value.learnerId !== learnerId) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return value;
  } catch {
    clearPendingAnswer();
    return null;
  }
}

export function savePendingAnswer(learnerId: number, input: RecallAnswerInput): PendingStudyAnswer {
  const pending: PendingStudyAnswer = {
    ...input,
    learnerId,
    version: STORAGE_VERSION,
  };
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pending));
  } catch {}
  return pending;
}

export function clearPendingAnswer(): void {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
}
