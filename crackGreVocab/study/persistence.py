"""ORM locking and writes for backend-planned Study Sessions."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Case, IntegerField, Max, When
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    SchedulingPhase,
    StudySession,
    StudySessionItem,
    StudySessionWord,
)
from .scheduling import SchedulerTransition
from .selectors import DueItem


def lock_learner(*, learner_id: int) -> LearnerAccount:
    """Lock and return the learner that owns the surrounding transaction."""
    return LearnerAccount.objects.select_for_update().get(pk=learner_id)


def lock_session(
    *,
    learner: LearnerAccount,
    session_id: UUID,
) -> StudySession | None:
    """Lock and return a learner-owned Study Session, if it exists."""
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
    """Lock and return a session-owned study item, if it exists."""
    return (
        StudySessionItem.objects.select_for_update(of=("self",))
        .select_related("corpus_entry__word")
        .filter(pk=item_id, session=session)
        .first()
    )


def lock_current_session_item(*, session: StudySession) -> StudySessionItem | None:
    """Lock and return the presentation attempt issued for this session."""
    if session.current_item_id is None:
        return None
    return (
        StudySessionItem.objects.select_for_update(of=("self",))
        .select_related("corpus_entry__word")
        .filter(pk=session.current_item_id, session=session, answer__isnull=True)
        .first()
    )


def persist_current_session_item(
    *,
    session: StudySession,
    item: StudySessionItem | None,
) -> None:
    """Persist the single card currently issued to the learner."""
    session.current_item = item
    session.save(update_fields=("current_item", "updated_at"))


def lock_word_state(
    *,
    learner: LearnerAccount,
    item: StudySessionItem,
) -> LearnerWordState | None:
    """Lock and return the learner's scheduling state for an item."""
    return (
        LearnerWordState.objects.select_for_update()
        .filter(learner=learner, word_id=item.corpus_entry.word_id)
        .first()
    )


def _session_words(
    *,
    session: StudySession,
    due_items: Sequence[DueItem],
    new_entries: Sequence[CorpusEntry],
    planned_at: datetime,
) -> list[StudySessionWord]:
    words = [
        StudySessionWord(
            session=session,
            corpus_entry=entry,
            position=position,
            kind=StudySessionWord.Kind.DUE,
            ready_at=(
                planned_at
                if state.phase == SchedulingPhase.REVIEW
                or state.next_due_at <= planned_at
                else state.next_due_at
            ),
        )
        for position, (state, entry) in enumerate(due_items, start=1)
    ]
    words.extend(
        StudySessionWord(
            session=session,
            corpus_entry=entry,
            position=position,
            kind=StudySessionWord.Kind.NEW,
            ready_at=planned_at,
        )
        for position, entry in enumerate(new_entries, start=len(words) + 1)
    )
    return words


def _initial_attempt_for_session_word(
    *,
    session: StudySession,
    session_word: StudySessionWord,
    position: int,
    state: LearnerWordState | None,
) -> StudySessionItem:
    """Build the first presentation attempt for an activated session Word."""
    if session_word.kind == StudySessionWord.Kind.DUE:
        if state is None:
            raise ValueError("A due session Word must have scheduling state.")
        return StudySessionItem(
            session=session,
            session_word=session_word,
            corpus_entry=session_word.corpus_entry,
            position=position,
            kind=StudySessionItem.Kind.DUE,
            due_at_snapshot=state.next_due_at,
            scheduler_version=state.scheduler_version,
            scheduling_state_snapshot=state.scheduler_state,
            ready_at=session_word.ready_at,
        )
    return StudySessionItem(
        session=session,
        session_word=session_word,
        corpus_entry=session_word.corpus_entry,
        position=position,
        kind=StudySessionItem.Kind.NEW,
        ready_at=session_word.ready_at,
    )


def refill_study_session_window(
    *,
    session: StudySession,
    observed_at: datetime,
    max_active_words: int,
) -> None:
    """Activate pending Words in the session’s working window."""
    active_count = session.session_words.filter(
        is_in_active_window=True,
        cleared_at__isnull=True,
    ).count()
    capacity = max_active_words - active_count
    if capacity <= 0:
        return

    candidates = list(
        session.session_words.filter(
            is_in_active_window=False,
            cleared_at__isnull=True,
        )
        .select_related("corpus_entry__word")
        .annotate(
            ready_priority=Case(
                When(ready_at__lte=observed_at, then=0),
                default=1,
                output_field=IntegerField(),
            )
        )
        .order_by("ready_priority", "ready_at", "position")[:capacity]
    )
    if not candidates:
        return

    candidate_ids = [candidate.pk for candidate in candidates]
    attempted_word_ids = set(
        StudySessionItem.objects.filter(
            session_word_id__in=candidate_ids,
        ).values_list("session_word_id", flat=True)
    )
    unstarted = [
        candidate for candidate in candidates if candidate.pk not in attempted_word_ids
    ]
    due_word_ids = [
        candidate.corpus_entry.word_id
        for candidate in unstarted
        if candidate.kind == StudySessionWord.Kind.DUE
    ]
    states_by_word_id = {
        state.word_id: state
        for state in LearnerWordState.objects.filter(
            learner=session.learner,
            word_id__in=due_word_ids,
        )
    }
    next_position = (
        StudySessionItem.objects.filter(session=session).aggregate(
            last=Max("position")
        )["last"]
        or 0
    )
    attempts = []
    for offset, session_word in enumerate(unstarted, start=1):
        attempts.append(
            _initial_attempt_for_session_word(
                session=session,
                session_word=session_word,
                position=next_position + offset,
                state=states_by_word_id.get(session_word.corpus_entry.word_id),
            )
        )
    if attempts:
        StudySessionItem.objects.bulk_create(attempts)

    StudySessionWord.objects.filter(pk__in=candidate_ids).update(
        is_in_active_window=True
    )
    for candidate in candidates:
        candidate.is_in_active_window = True


def persist_study_session_plan(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    timezone_name: str,
    day_ends_at: datetime,
    planned_at: datetime,
    new_word_target: int,
    max_active_words: int,
    due_items: Sequence[DueItem],
    new_entries: Sequence[CorpusEntry],
    planner_version: str,
) -> StudySession:
    """Persist one complete plan; the caller owns the surrounding transaction."""
    entries = tuple(entry for _, entry in due_items) + tuple(new_entries)
    if any(entry.corpus_id != corpus.pk for entry in entries):
        raise ValueError("Every Study Session item must belong to the session corpus.")
    session = StudySession.objects.create(
        learner=learner,
        corpus=corpus,
        status=StudySession.Status.ACTIVE,
        timezone_name=timezone_name,
        day_ends_at=day_ends_at,
        new_word_target=new_word_target,
        planner_version=planner_version,
    )
    StudySessionWord.objects.bulk_create(
        _session_words(
            session=session,
            due_items=due_items,
            new_entries=new_entries,
            planned_at=planned_at,
        )
    )
    refill_study_session_window(
        session=session,
        observed_at=planned_at,
        max_active_words=max_active_words,
    )
    return session


def persist_session_word_after_answer(
    *,
    session: StudySession,
    item: StudySessionItem,
    occurred_at: datetime,
    transition: SchedulerTransition,
) -> None:
    """Update daily progress and enqueue a later attempt when still due today."""
    session_word = item.session_word
    session_word.last_presented_position = item.position
    session_word.ready_at = transition.next_due_at
    session_word.is_in_active_window = False
    update_fields = [
        "last_presented_position",
        "ready_at",
        "is_in_active_window",
    ]
    if transition.next_due_at >= session.day_ends_at:
        session_word.cleared_at = occurred_at
        update_fields.append("cleared_at")
    session_word.save(update_fields=update_fields)

    if session_word.cleared_at is not None:
        return
    last_position = (
        StudySessionItem.objects.filter(session=session).aggregate(
            last=Max("position")
        )["last"]
        or 0
    )
    StudySessionItem.objects.create(
        session=session,
        session_word=session_word,
        corpus_entry=item.corpus_entry,
        position=last_position + 1,
        kind=StudySessionItem.Kind.DUE,
        due_at_snapshot=transition.next_due_at,
        scheduler_version=transition.scheduler_version,
        scheduling_state_snapshot=transition.next_state,
        ready_at=transition.next_due_at,
    )


def persist_recall_answer_transition(
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


def mark_study_session_completed(
    *,
    session: StudySession,
    ended_at: datetime,
) -> None:
    """Mark a Study Session completed at the accepted answer time."""
    session.close("completed", at=ended_at)
    session.save(update_fields=("status", "ended_at", "updated_at"))
