"use client";

import { Button } from "@heroui/react/button";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { StudyCard } from "@/components/study/study-card";
import { StudySessionPlanner } from "@/components/study/study-session-planner";
import type { StudyNotice } from "@/components/study/types";
import type { StudySession as StudySessionContract } from "@/lib/api/generated/schema.generated";
import {
  createStudySession,
  getActiveStudySession,
  type RecallRating,
  StudyApiError,
  submitRecallAnswer,
} from "@/lib/api/study";
import {
  clearPendingAnswer,
  loadPendingAnswer,
  type PendingStudyAnswer,
  savePendingAnswer,
} from "@/lib/study/pending-answer";

function studyNoticeFromError(error: unknown): StudyNotice {
  if (error instanceof StudyApiError) {
    return { message: error.message, retryable: error.retryable };
  }
  return {
    message: "Something unexpected interrupted this study session. Please try again.",
    retryable: true,
  };
}

function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

export function StudySession() {
  const auth = useAuth();
  const router = useRouter();
  const [session, setSession] = useState<StudySessionContract | null>(null);
  const [newWordTarget, setNewWordTarget] = useState(10);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pending, setPending] = useState<PendingStudyAnswer | null>(null);
  const [notice, setNotice] = useState<StudyNotice | null>(null);
  const termHeading = useRef<HTMLHeadingElement>(null);

  const applyServerSession = useCallback((nextSession: StudySessionContract | null) => {
    setSession(nextSession);
    setRevealed(false);
  }, []);

  const clearPendingRecallAnswer = useCallback(() => {
    clearPendingAnswer();
    setPending(null);
  }, []);

  const refreshExpiredAuthentication = useCallback(
    async (error: unknown) => {
      if (!(error instanceof StudyApiError) || error.kind !== "unauthenticated") {
        return false;
      }
      await auth.refresh();
      return true;
    },
    [auth.refresh],
  );

  const reloadAuthoritativeStudyProgress = useCallback(
    async (signal?: AbortSignal) => {
      const active = await getActiveStudySession({ signal });
      if (!signal?.aborted) {
        applyServerSession(active);
      }
    },
    [applyServerSession],
  );

  const handleRejectedRecallAnswer = useCallback(
    async (error: unknown, signal?: AbortSignal) => {
      if (await refreshExpiredAuthentication(error)) {
        return;
      }
      const staleProgress =
        error instanceof StudyApiError && ["conflict", "not-found"].includes(error.kind);
      if (!staleProgress) {
        setNotice(studyNoticeFromError(error));
        return;
      }

      clearPendingRecallAnswer();
      applyServerSession(null);
      setLoading(true);
      try {
        await reloadAuthoritativeStudyProgress(signal);
        if (!signal?.aborted) {
          setNotice({
            message: "Your study progress changed elsewhere, so this page was refreshed.",
            retryable: false,
          });
        }
      } catch (refreshError) {
        if (!signal?.aborted && !(await refreshExpiredAuthentication(refreshError))) {
          setNotice(studyNoticeFromError(refreshError));
        }
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [
      applyServerSession,
      clearPendingRecallAnswer,
      refreshExpiredAuthentication,
      reloadAuthoritativeStudyProgress,
    ],
  );

  const restoreStudyProgress = useCallback(
    async (signal?: AbortSignal) => {
      if (!auth.account) {
        return;
      }
      setLoading(true);
      setNotice(null);

      try {
        const stored = loadPendingAnswer(auth.account.id);
        if (stored) {
          setPending(stored);
          try {
            const recovered = await submitRecallAnswer(stored, { signal });
            if (signal?.aborted) {
              return;
            }
            clearPendingRecallAnswer();
            applyServerSession(recovered.session);
            return;
          } catch (error) {
            if (signal?.aborted) {
              return;
            }
            await handleRejectedRecallAnswer(error, signal);
            return;
          }
        }

        try {
          await reloadAuthoritativeStudyProgress(signal);
        } catch (error) {
          if (!signal?.aborted && !(await refreshExpiredAuthentication(error))) {
            setNotice(studyNoticeFromError(error));
          }
        }
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [
      applyServerSession,
      auth.account,
      clearPendingRecallAnswer,
      handleRejectedRecallAnswer,
      refreshExpiredAuthentication,
      reloadAuthoritativeStudyProgress,
    ],
  );

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/sign-in");
      setLoading(false);
      return;
    }
    if (auth.status !== "authenticated" || !auth.account) {
      return;
    }
    const controller = new AbortController();
    void restoreStudyProgress(controller.signal);
    return () => controller.abort();
  }, [auth.account, auth.status, restoreStudyProgress, router]);

  const currentItemId = session?.current_item?.id;
  useEffect(() => {
    if (currentItemId) {
      termHeading.current?.focus();
    }
  }, [currentItemId]);

  async function startPlannedStudySession() {
    setStarting(true);
    setNotice(null);
    try {
      const created = await createStudySession(newWordTarget, browserTimezone());
      applyServerSession(created);
    } catch (error) {
      setNotice(studyNoticeFromError(error));
    } finally {
      setStarting(false);
    }
  }

  async function submitPendingRecallAnswer(operation: PendingStudyAnswer) {
    setSubmitting(true);
    setNotice(null);
    try {
      const recorded = await submitRecallAnswer(operation);
      clearPendingRecallAnswer();
      applyServerSession(recorded.session);
    } catch (error) {
      await handleRejectedRecallAnswer(error);
    } finally {
      setSubmitting(false);
    }
  }

  function recordRecallSelfGrade(rating: RecallRating) {
    if (!auth.account || !session?.current_item || pending) {
      return;
    }
    const operation = savePendingAnswer(auth.account.id, {
      client_request_id: crypto.randomUUID(),
      itemId: session.current_item.id,
      rating,
      sessionId: session.id,
    });
    setPending(operation);
    void submitPendingRecallAnswer(operation);
  }

  if (auth.status === "unavailable") {
    return (
      <div className="space-y-5">
        <p className="text-foreground/70" role="alert">
          We couldn&apos;t load your study progress. Please try again.
        </p>
        <Button onPress={() => void auth.refresh()} variant="primary">
          Try again
        </Button>
      </div>
    );
  }

  if (auth.status === "checking" || loading) {
    return (
      <p aria-live="polite" className="text-foreground/70" role="status">
        Loading your study progress…
      </p>
    );
  }

  if (auth.status !== "authenticated" || !auth.account) {
    return (
      <p className="text-foreground/70" role="status">
        Sign in is required to study.
      </p>
    );
  }

  if (!session && pending) {
    return (
      <div className="space-y-5">
        <p className="text-foreground/70" role="alert">
          {notice?.message ?? "Your saved answer still needs to be restored."}
        </p>
        <Button
          isDisabled={submitting}
          isPending={submitting}
          onPress={() => void submitPendingRecallAnswer(pending)}
          variant="primary"
        >
          Retry saved answer
        </Button>
      </div>
    );
  }

  if (!session) {
    return (
      <StudySessionPlanner
        newWordTarget={newWordTarget}
        notice={notice}
        onRestore={() => void restoreStudyProgress()}
        onStart={() => void startPlannedStudySession()}
        onTargetChange={setNewWordTarget}
        starting={starting}
      />
    );
  }

  if (session.status === "completed") {
    return (
      <div className="space-y-6 py-10 text-center">
        <div role="status">
          <h2 className="text-4xl font-black tracking-tight">Session complete</h2>
          <p className="mx-auto mt-4 max-w-xl text-foreground/65">
            All {session.word_count} words are done for today.
          </p>
        </div>
        <Link
          className="inline-flex rounded-full bg-accent px-6 py-3 font-bold text-accent-foreground shadow-lg shadow-accent/15 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-background motion-reduce:transform-none"
          href="/dashboard"
        >
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (session.status === "abandoned") {
    return (
      <div className="space-y-5 py-10 text-center">
        <div role="status">
          <h2 className="text-4xl font-black tracking-tight">Session ended</h2>
          <p className="mx-auto mt-4 max-w-xl text-foreground/65">
            This session is no longer active. You can plan another session from current progress.
          </p>
        </div>
        <Button
          onPress={() => {
            clearPendingRecallAnswer();
            setNotice(null);
            applyServerSession(null);
          }}
          variant="primary"
        >
          Plan another session
        </Button>
      </div>
    );
  }

  if (!session.current_item) {
    return (
      <div className="space-y-5 py-10 text-center">
        <div role="alert">
          <h2 className="text-3xl font-black tracking-tight">Study session needs attention</h2>
          <p className="mx-auto mt-4 max-w-xl text-foreground/65">
            We couldn&apos;t find your next card. Reload your study progress to continue.
          </p>
        </div>
        <Button onPress={() => void restoreStudyProgress()} variant="primary">
          Reload study progress
        </Button>
      </div>
    );
  }

  return (
    <StudyCard
      notice={notice}
      onRating={recordRecallSelfGrade}
      onRetry={() => pending && void submitPendingRecallAnswer(pending)}
      onReveal={() => setRevealed(true)}
      pending={pending}
      revealed={revealed}
      session={session}
      submitting={submitting}
      termHeading={termHeading}
    />
  );
}
