"use client";

import { Button } from "@heroui/react";
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

  const restoreStudyProgress = useCallback(
    async (signal?: AbortSignal) => {
      if (!auth.account) {
        return;
      }
      setLoading(true);
      setNotice(null);

      const stored = loadPendingAnswer(auth.account.id);
      if (stored) {
        setPending(stored);
        try {
          const recovered = await submitRecallAnswer(stored, { signal });
          if (signal?.aborted) {
            return;
          }
          clearPendingAnswer();
          setPending(null);
          setSession(recovered.session);
          setRevealed(false);
          setLoading(false);
          return;
        } catch (error) {
          if (signal?.aborted) {
            return;
          }
          if (await refreshExpiredAuthentication(error)) {
            return;
          }
          if (
            !(error instanceof StudyApiError) ||
            !["conflict", "not-found"].includes(error.kind)
          ) {
            setNotice(studyNoticeFromError(error));
            setLoading(false);
            return;
          }
          clearPendingAnswer();
          setPending(null);
        }
      }

      try {
        const active = await getActiveStudySession({ signal });
        if (!signal?.aborted) {
          setSession(active);
          setRevealed(false);
        }
      } catch (error) {
        if (!signal?.aborted && !(await refreshExpiredAuthentication(error))) {
          setNotice(studyNoticeFromError(error));
        }
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [auth.account, refreshExpiredAuthentication],
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
      const created = await createStudySession(newWordTarget);
      setSession(created);
      setRevealed(false);
    } catch (error) {
      setNotice(studyNoticeFromError(error));
    } finally {
      setStarting(false);
    }
  }

  async function reloadAuthoritativeStudyProgress() {
    const active = await getActiveStudySession();
    setSession(active);
    setRevealed(false);
  }

  async function submitPendingRecallAnswer(operation: PendingStudyAnswer) {
    setSubmitting(true);
    setNotice(null);
    try {
      const recorded = await submitRecallAnswer(operation);
      clearPendingAnswer();
      setPending(null);
      setSession(recorded.session);
      setRevealed(false);
    } catch (error) {
      if (await refreshExpiredAuthentication(error)) {
        return;
      }
      if (error instanceof StudyApiError && ["conflict", "not-found"].includes(error.kind)) {
        clearPendingAnswer();
        setPending(null);
        try {
          await reloadAuthoritativeStudyProgress();
          setNotice({
            message: "Your study progress changed elsewhere, so this page was refreshed.",
            retryable: false,
          });
        } catch (refreshError) {
          setNotice(studyNoticeFromError(refreshError));
        }
      } else {
        setNotice(studyNoticeFromError(error));
      }
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
          The local backend is unavailable, so your learner session could not be restored.
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
        Restoring your study session…
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

  if (session.status === "completed" || !session.current_item) {
    return (
      <div className="py-10 text-center" role="status">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-accent">Session complete</p>
        <h2 className="mt-3 text-4xl font-black tracking-tight">
          You finished all {session.item_count} cards.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-foreground/65">
          Every accepted answer and its next review time are safely stored in PostgreSQL.
        </p>
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
