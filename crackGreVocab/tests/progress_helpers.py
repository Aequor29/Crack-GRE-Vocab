"""Persisted learning history for progress scenarios."""

import uuid
from datetime import UTC, datetime, timedelta

from accounts.models import LearnerAccount
from study.models import (
    RecallAnswer,
    RecallOutcome,
    StudySession,
    StudySessionItem,
    StudySessionWord,
)
from vocabulary.models import CorpusEntry


def create_recall_outcome(
    *,
    learner: LearnerAccount,
    entry: CorpusEntry,
    occurred_at: datetime,
    rating: str,
    previous_phase: str,
    next_phase: str = "review",
    review_number: int | None = None,
    next_interval: timedelta = timedelta(days=1),
    session: StudySession | None = None,
    position: int = 1,
) -> RecallOutcome:
    """Create an accepted answer and its scheduling outcome at a stated time."""
    if session is None:
        session = StudySession.objects.create(
            learner=learner,
            corpus=entry.corpus,
            status=StudySession.Status.COMPLETED,
            new_word_target=0,
            planner_version="test-planner",
            ended_at=occurred_at,
        )
    is_initial = previous_phase == ""
    kind = StudySessionItem.Kind.NEW if is_initial else StudySessionItem.Kind.DUE
    previous_due_at = None if is_initial else occurred_at - timedelta(days=1)
    previous_state = {} if is_initial else {"step": 1}
    session_word = StudySessionWord.objects.create(
        session=session,
        corpus_entry=entry,
        position=position,
        kind=kind,
        ready_at=occurred_at,
        cleared_at=occurred_at,
    )
    item = StudySessionItem.objects.create(
        session=session,
        session_word=session_word,
        corpus_entry=entry,
        position=position,
        kind=kind,
        due_at_snapshot=previous_due_at,
        scheduler_version="" if is_initial else "test-scheduler",
        scheduling_state_snapshot=previous_state,
    )
    answer = RecallAnswer.objects.create(
        item=item,
        rating=rating,
        client_request_id=uuid.uuid4(),
        submitted_at=datetime.now(UTC),
    )
    RecallAnswer.objects.filter(pk=answer.pk).update(
        submitted_at=occurred_at, accepted_at=occurred_at
    )
    return RecallOutcome.objects.create(
        answer=answer,
        review_number=review_number or (1 if is_initial else 2),
        scheduler_version="test-scheduler",
        previous_phase=previous_phase,
        next_phase=next_phase,
        previous_due_at=previous_due_at,
        next_due_at=occurred_at + next_interval,
        previous_state=previous_state,
        next_state={"step": 2},
        occurred_at=occurred_at,
    )
