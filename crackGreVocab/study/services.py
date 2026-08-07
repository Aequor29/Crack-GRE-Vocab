"""Transactional, backend-authoritative Study Session planning."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from accounts.models import LearnerAccount
from django.db import transaction
from django.utils import timezone
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import LearnerWordState, StudySession, StudySessionItem

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


type DueItem = tuple[LearnerWordState, CorpusEntry]


@dataclass(frozen=True)
class SelectedStudyItems:
    due_items: tuple[DueItem, ...]
    new_entries: tuple[CorpusEntry, ...]

    def __bool__(self) -> bool:
        return bool(self.due_items or self.new_entries)


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


def session_queryset():
    """Load the stable response representation without per-item queries."""
    return StudySession.objects.select_related("corpus").prefetch_related(
        "items__corpus_entry__word",
        "items__corpus_entry__senses",
    )


def get_active_session(*, learner: LearnerAccount) -> StudySession | None:
    return (
        session_queryset()
        .filter(learner=learner, status=StudySession.Status.ACTIVE)
        .first()
    )


def _validate_new_word_target(
    new_word_target: int,
    policy: StudyPlanPolicy,
) -> None:
    if not 0 <= new_word_target <= policy.max_new_words:
        raise ValueError(
            f"new_word_target must be between 0 and {policy.max_new_words}."
        )


def _active_corpus() -> CorpusVersion:
    corpus = CorpusVersion.objects.filter(is_active=True).first()
    if corpus is None:
        raise StudyPlanningUnavailable("No active vocabulary corpus is available.")
    return corpus


def _select_due_items(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    planned_at: datetime,
    limit: int,
) -> tuple[DueItem, ...]:
    states = list(
        LearnerWordState.objects.filter(
            learner=learner,
            next_due_at__lte=planned_at,
            word__corpus_entries__corpus=corpus,
        )
        .select_related("word")
        .order_by("next_due_at", "word__normalized_term", "id")[:limit]
    )
    entries_by_word = {
        entry.word_id: entry
        for entry in CorpusEntry.objects.filter(
            corpus=corpus,
            word_id__in=[state.word_id for state in states],
        ).select_related("word")
    }
    return tuple((state, entries_by_word[state.word_id]) for state in states)


def _select_new_entries(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    limit: int,
) -> tuple[CorpusEntry, ...]:
    return tuple(
        CorpusEntry.objects.filter(corpus=corpus)
        .exclude(word__learner_states__learner=learner)
        .select_related("word")
        .order_by("position", "id")[:limit]
    )


def _create_session(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    new_word_target: int,
    selection: SelectedStudyItems,
) -> StudySession:
    return StudySession.objects.create(
        learner=learner,
        corpus=corpus,
        status=StudySession.Status.ACTIVE,
        new_word_target=new_word_target,
        planned_new_word_count=len(selection.new_entries),
        item_count=len(selection.due_items) + len(selection.new_entries),
        planner_version=PLANNER_VERSION,
    )


def _session_items(
    *,
    session: StudySession,
    selection: SelectedStudyItems,
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
        for position, (state, entry) in enumerate(selection.due_items, start=1)
    ]
    items.extend(
        StudySessionItem(
            session=session,
            corpus_entry=entry,
            position=position,
            kind=StudySessionItem.Kind.NEW,
        )
        for position, entry in enumerate(
            selection.new_entries,
            start=len(items) + 1,
        )
    )
    return items


def _select_session_items(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    new_word_target: int,
    policy: StudyPlanPolicy,
    planned_at: datetime,
) -> SelectedStudyItems:
    due_items = _select_due_items(
        learner=learner,
        corpus=corpus,
        planned_at=planned_at,
        limit=policy.max_items,
    )
    new_entries = _select_new_entries(
        learner=learner,
        corpus=corpus,
        limit=min(new_word_target, policy.max_items - len(due_items)),
    )
    return SelectedStudyItems(due_items=due_items, new_entries=new_entries)


def _persist_session_plan(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    new_word_target: int,
    selection: SelectedStudyItems,
) -> StudySession:
    session = _create_session(
        learner=learner,
        corpus=corpus,
        new_word_target=new_word_target,
        selection=selection,
    )
    StudySessionItem.objects.bulk_create(
        _session_items(session=session, selection=selection)
    )
    return session_queryset().get(pk=session.pk)


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
    locked_learner = LearnerAccount.objects.select_for_update().get(pk=learner.pk)
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

    session = _persist_session_plan(
        learner=locked_learner,
        corpus=corpus,
        new_word_target=new_word_target,
        selection=selection,
    )
    return PlannedSession(session=session, created=True)
