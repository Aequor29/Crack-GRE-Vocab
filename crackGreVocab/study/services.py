"""Transactional business orchestration for backend-planned Study Sessions."""

from dataclasses import dataclass
from datetime import datetime

from accounts.models import LearnerAccount
from django.db import transaction
from django.utils import timezone
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import StudySession
from .persistence import create_session_plan, lock_learner
from .selectors import (
    DueItem,
    get_active_corpus,
    get_active_session,
    get_session,
    select_due_items,
    select_new_entries,
)

PLANNER_VERSION = "m1-due-first-v1"


class StudyPlanningUnavailable(Exception):
    """The backend cannot form a useful Study Session from current state."""


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
