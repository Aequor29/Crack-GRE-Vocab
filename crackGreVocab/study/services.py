"""Transactional business orchestration for backend-planned Study Sessions."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from accounts.models import LearnerAccount
from django.db import transaction
from django.utils import timezone
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    StudySession,
    StudySessionItem,
)
from .persistence import (
    complete_session,
    create_recall_records,
    create_session_plan,
    lock_current_session_item,
    lock_learner,
    lock_session,
    lock_session_item,
    lock_word_state,
)
from .scheduling import SchedulingStateError, schedule_recall
from .selectors import (
    DueItem,
    get_active_corpus,
    get_active_session,
    get_answer_by_request_id,
    get_item_answer,
    get_session,
    select_due_items,
    select_new_entries,
)

PLANNER_VERSION = "m1-due-first-v1"


class StudyPlanningUnavailable(Exception):
    """The backend cannot form a useful Study Session from current state."""


class StudyAnswerNotFound(Exception):
    """The requested learner-owned session item does not exist."""


class StudyAnswerConflict(Exception):
    """The answer conflicts with authoritative Study Session progress."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        current_item_id: UUID | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.current_item_id = current_item_id


class StudyAnswerUnavailable(Exception):
    """Stored scheduling state cannot produce a safe Recall Outcome."""


@dataclass(frozen=True)
class StudyPlanPolicy:
    """Versioned Milestone 1 boundaries for one bounded study sitting."""

    max_items: int = 30
    max_new_words: int = 20


@dataclass(frozen=True)
class PlannedSession:
    session: StudySession
    created: bool


@dataclass(frozen=True)
class RecordedRecall:
    answer: RecallAnswer
    outcome: RecallOutcome
    session: StudySession
    created: bool


@dataclass(frozen=True)
class SelectedStudyItems:
    due_items: tuple[DueItem, ...]
    new_entries: tuple[CorpusEntry, ...]

    def __bool__(self) -> bool:
        return bool(self.due_items or self.new_entries)


def _validate_new_word_target(
    new_word_target: int,
    policy: StudyPlanPolicy,
) -> None:
    if not 0 <= new_word_target <= policy.max_new_words:
        raise ValueError(
            f"new_word_target must be between 0 and {policy.max_new_words}."
        )


def _active_corpus() -> CorpusVersion:
    corpus = get_active_corpus()
    if corpus is None:
        raise StudyPlanningUnavailable("No active vocabulary corpus is available.")
    return corpus


def _select_session_items(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    new_word_target: int,
    policy: StudyPlanPolicy,
    planned_at: datetime,
) -> SelectedStudyItems:
    due_items = select_due_items(
        learner=learner,
        corpus=corpus,
        planned_at=planned_at,
        limit=policy.max_items,
    )
    new_entries = select_new_entries(
        learner=learner,
        corpus=corpus,
        limit=min(new_word_target, policy.max_items - len(due_items)),
    )
    return SelectedStudyItems(due_items=due_items, new_entries=new_entries)


def _validate_item_state(
    *,
    item: StudySessionItem,
    state: LearnerWordState | None,
) -> None:
    if item.kind == StudySessionItem.Kind.NEW:
        if state is not None:
            raise StudyAnswerUnavailable(
                "The new-item scheduling state is no longer eligible."
            )
        return
    if state is None:
        raise StudyAnswerUnavailable("The due-item scheduling state is missing.")
    if (
        item.scheduler_version != state.scheduler_version
        or item.due_at_snapshot != state.next_due_at
        or item.scheduling_state_snapshot.get("scheduler_state")
        != state.scheduler_state
    ):
        raise StudyAnswerUnavailable(
            "The due-item scheduling snapshot no longer matches current state."
        )


def _existing_recall(
    *,
    learner: LearnerAccount,
    session: StudySession,
    item: StudySessionItem,
    request_id: UUID,
    rating: str,
) -> RecordedRecall | None:
    existing = get_answer_by_request_id(request_id=request_id)
    if existing is None:
        return None
    if (
        existing.item_id != item.pk
        or existing.item.session_id != session.pk
        or existing.item.session.learner_id != learner.pk
        or existing.rating != rating
    ):
        raise StudyAnswerConflict(
            "study_request_id_reused",
            "This answer request ID was already used for another operation.",
        )
    try:
        outcome = existing.outcome
    except RecallOutcome.DoesNotExist as exc:
        raise StudyAnswerUnavailable(
            "The accepted answer has no durable Recall Outcome."
        ) from exc
    return RecordedRecall(
        answer=existing,
        outcome=outcome,
        session=get_session(session_id=session.pk),
        created=False,
    )


@transaction.atomic
def record_recall_answer(
    *,
    learner: LearnerAccount,
    session_id: UUID,
    item_id: UUID,
    request_id: UUID,
    rating: str,
    occurred_at: datetime | None = None,
) -> RecordedRecall:
    """Accept one current-item self-grade and atomically schedule its Word."""
    if rating not in RecallAnswer.Rating.values:
        raise ValueError("rating must be remembered or forgot.")

    locked_learner = lock_learner(learner_id=learner.pk)
    session = lock_session(learner=locked_learner, session_id=session_id)
    if session is None:
        raise StudyAnswerNotFound("The Study Session item was not found.")
    item = lock_session_item(session=session, item_id=item_id)
    if item is None:
        raise StudyAnswerNotFound("The Study Session item was not found.")

    replay = _existing_recall(
        learner=locked_learner,
        session=session,
        item=item,
        request_id=request_id,
        rating=rating,
    )
    if replay is not None:
        return replay

    if session.status != StudySession.Status.ACTIVE:
        raise StudyAnswerConflict(
            "study_session_inactive",
            "Only an active Study Session can accept an answer.",
        )
    if get_item_answer(item=item) is not None:
        raise StudyAnswerConflict(
            "study_item_already_answered",
            "This Study Session item already has an accepted answer.",
        )

    current_item = lock_current_session_item(session=session)
    if current_item is None:
        raise StudyAnswerUnavailable(
            "The active Study Session has no unanswered current item."
        )
    if current_item.pk != item.pk:
        raise StudyAnswerConflict(
            "study_item_out_of_order",
            "Answers must follow the backend-planned item order.",
            current_item_id=current_item.pk,
        )

    state = lock_word_state(learner=locked_learner, item=item)
    _validate_item_state(item=item, state=state)
    occurred_at = occurred_at or timezone.now()
    try:
        transition = schedule_recall(
            word_id=item.corpus_entry.word_id,
            rating=rating,
            occurred_at=occurred_at,
            previous_state=state.scheduler_state if state is not None else None,
            previous_scheduler_version=(
                state.scheduler_version if state is not None else None
            ),
        )
    except SchedulingStateError as exc:
        raise StudyAnswerUnavailable(str(exc)) from exc

    answer, outcome, _ = create_recall_records(
        learner=locked_learner,
        item=item,
        state=state,
        rating=rating,
        request_id=request_id,
        occurred_at=occurred_at,
        transition=transition,
    )
    if lock_current_session_item(session=session) is None:
        complete_session(session=session, ended_at=occurred_at)

    return RecordedRecall(
        answer=answer,
        outcome=outcome,
        session=get_session(session_id=session.pk),
        created=True,
    )


@transaction.atomic
def plan_study_session(
    *,
    learner: LearnerAccount,
    new_word_target: int,
    policy: StudyPlanPolicy = StudyPlanPolicy(),
    planned_at: datetime | None = None,
) -> PlannedSession:
    """Resume an active session or atomically persist a deterministic new plan."""
    _validate_new_word_target(new_word_target, policy)
    planned_at = planned_at or timezone.now()
    locked_learner = lock_learner(learner_id=learner.pk)
    active = get_active_session(learner=locked_learner)
    if active is not None:
        return PlannedSession(session=active, created=False)

    corpus = _active_corpus()
    selection = _select_session_items(
        learner=locked_learner,
        corpus=corpus,
        new_word_target=new_word_target,
        policy=policy,
        planned_at=planned_at,
    )
    if not selection:
        raise StudyPlanningUnavailable(
            "No vocabulary items are eligible for a new Study Session."
        )

    session = create_session_plan(
        learner=locked_learner,
        corpus=corpus,
        new_word_target=new_word_target,
        due_items=selection.due_items,
        new_entries=selection.new_entries,
        planner_version=PLANNER_VERSION,
    )
    return PlannedSession(session=get_session(session_id=session.pk), created=True)
