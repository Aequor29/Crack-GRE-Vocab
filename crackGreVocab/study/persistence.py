"""ORM locking and writes for backend-planned Study Sessions."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Subquery
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    SchedulingPhase,
    StudySession,
    StudySessionItem,
)
from .scheduling import SchedulerTransition
from .selectors import DueItem


def lock_learner(*, learner_id: int) -> LearnerAccount:
    return LearnerAccount.objects.select_for_update().get(pk=learner_id)


def lock_session(
    *,
    learner: LearnerAccount,
    session_id: UUID,
) -> StudySession | None:
    return (
        StudySession.objects.select_for_update()
        .filter(pk=session_id, learner=learner)
        .first()
    )


def lock_session_item(
    *,
    session: StudySession,
    item_id: UUID,
) -> StudySessionItem | None:
    return (
        StudySessionItem.objects.select_for_update()
        .select_related("corpus_entry__word")
        .filter(pk=item_id, session=session)
        .first()
    )


def lock_current_session_item(
    *,
    session: StudySession,
) -> StudySessionItem | None:
    answered_item_ids = RecallAnswer.objects.values("item_id")
    return (
        StudySessionItem.objects.select_for_update()
        .select_related("corpus_entry__word")
        .filter(session=session)
        .exclude(pk__in=Subquery(answered_item_ids))
        .order_by("position")
        .first()
    )


def lock_word_state(
    *,
    learner: LearnerAccount,
    item: StudySessionItem,
) -> LearnerWordState | None:
    return (
        LearnerWordState.objects.select_for_update()
        .filter(learner=learner, word_id=item.corpus_entry.word_id)
        .first()
    )


def _decimal_snapshot(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _state_snapshot(state: LearnerWordState) -> dict[str, object]:
    return {
        "difficulty": _decimal_snapshot(state.difficulty),
        "lapse_count": state.lapse_count,
        "last_reviewed_at": state.last_reviewed_at.isoformat(),
        "phase": state.phase,
        "review_count": state.review_count,
        "scheduler_state": state.scheduler_state,
        "stability": _decimal_snapshot(state.stability),
    }


def _session_items(
    *,
    session: StudySession,
    due_items: Sequence[DueItem],
    new_entries: Sequence[CorpusEntry],
) -> list[StudySessionItem]:
    items = [
        StudySessionItem(
            session=session,
            corpus_entry=entry,
            position=position,
            kind=StudySessionItem.Kind.DUE,
            due_at_snapshot=state.next_due_at,
            scheduler_version=state.scheduler_version,
            scheduling_state_snapshot=_state_snapshot(state),
        )
        for position, (state, entry) in enumerate(due_items, start=1)
    ]
    items.extend(
        StudySessionItem(
            session=session,
            corpus_entry=entry,
            position=position,
            kind=StudySessionItem.Kind.NEW,
        )
        for position, entry in enumerate(new_entries, start=len(items) + 1)
    )
    return items


def create_session_plan(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    new_word_target: int,
    due_items: Sequence[DueItem],
    new_entries: Sequence[CorpusEntry],
    planner_version: str,
) -> StudySession:
    """Persist one complete plan; the caller owns the surrounding transaction."""
    session = StudySession.objects.create(
        learner=learner,
        corpus=corpus,
        status=StudySession.Status.ACTIVE,
        new_word_target=new_word_target,
        planned_new_word_count=len(new_entries),
        item_count=len(due_items) + len(new_entries),
        planner_version=planner_version,
    )
    StudySessionItem.objects.bulk_create(
        _session_items(
            session=session,
            due_items=due_items,
            new_entries=new_entries,
        )
    )
    return session


def create_recall_records(
    *,
    learner: LearnerAccount,
    item: StudySessionItem,
    state: LearnerWordState | None,
    rating: str,
    request_id: UUID,
    occurred_at: datetime,
    transition: SchedulerTransition,
) -> tuple[RecallAnswer, RecallOutcome, LearnerWordState]:
    """Persist one complete transition; the caller owns the transaction."""
    previous_phase = state.phase if state is not None else ""
    previous_due_at = state.next_due_at if state is not None else None
    previous_state = dict(state.scheduler_state) if state is not None else {}
    review_number = state.review_count + 1 if state is not None else 1
    lapse_count = state.lapse_count if state is not None else 0
    if (
        state is not None
        and state.phase == SchedulingPhase.REVIEW
        and rating == RecallAnswer.Rating.FORGOT
    ):
        lapse_count += 1

    answer = RecallAnswer.objects.create(
        item=item,
        rating=rating,
        client_request_id=request_id,
        submitted_at=occurred_at,
    )
    outcome = RecallOutcome.objects.create(
        answer=answer,
        review_number=review_number,
        scheduler_version=transition.scheduler_version,
        previous_phase=previous_phase,
        next_phase=transition.next_phase,
        previous_due_at=previous_due_at,
        next_due_at=transition.next_due_at,
        previous_state=previous_state,
        next_state=transition.next_state,
        occurred_at=occurred_at,
    )

    values = {
        "phase": transition.next_phase,
        "difficulty": transition.difficulty,
        "stability": transition.stability,
        "review_count": review_number,
        "lapse_count": lapse_count,
        "last_reviewed_at": occurred_at,
        "next_due_at": transition.next_due_at,
        "scheduler_version": transition.scheduler_version,
        "scheduler_state": transition.next_state,
    }
    if state is None:
        state = LearnerWordState.objects.create(
            learner=learner,
            word_id=item.corpus_entry.word_id,
            **values,
        )
    else:
        for field, value in values.items():
            setattr(state, field, value)
        state.save(update_fields=(*values, "updated_at"))
    return answer, outcome, state


def complete_session(*, session: StudySession, ended_at: datetime) -> None:
    session.close("completed", at=ended_at)
    session.save(update_fields=("status", "ended_at", "updated_at"))
