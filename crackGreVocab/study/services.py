"""Transactional, backend-authoritative Study Session planning."""

from dataclasses import dataclass
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


@transaction.atomic
def plan_study_session(
    *,
    learner: LearnerAccount,
    new_word_target: int,
    policy: StudyPlanPolicy = StudyPlanPolicy(),
    planned_at=None,
) -> PlannedSession:
    """Resume an active session or atomically persist a deterministic new plan."""
    if not 0 <= new_word_target <= policy.max_new_words:
        raise ValueError(
            f"new_word_target must be between 0 and {policy.max_new_words}."
        )

    planned_at = planned_at or timezone.now()
    locked_learner = LearnerAccount.objects.select_for_update().get(pk=learner.pk)
    active = get_active_session(learner=locked_learner)
    if active is not None:
        return PlannedSession(session=active, created=False)

    corpus = CorpusVersion.objects.filter(is_active=True).first()
    if corpus is None:
        raise StudyPlanningUnavailable("No active vocabulary corpus is available.")

    due_states = list(
        LearnerWordState.objects.filter(
            learner=locked_learner,
            next_due_at__lte=planned_at,
            word__corpus_entries__corpus=corpus,
        )
        .select_related("word")
        .order_by("next_due_at", "word__normalized_term", "id")[: policy.max_items]
    )
    entries_by_word = {
        entry.word_id: entry
        for entry in CorpusEntry.objects.filter(
            corpus=corpus,
            word_id__in=[state.word_id for state in due_states],
        ).select_related("word")
    }

    remaining_slots = policy.max_items - len(due_states)
    requested_new_count = min(new_word_target, remaining_slots)
    new_entries = list(
        CorpusEntry.objects.filter(corpus=corpus)
        .exclude(word__learner_states__learner=locked_learner)
        .select_related("word")
        .order_by("position", "id")[:requested_new_count]
    )

    if not due_states and not new_entries:
        raise StudyPlanningUnavailable(
            "No vocabulary items are eligible for a new Study Session."
        )

    session = StudySession.objects.create(
        learner=locked_learner,
        corpus=corpus,
        status=StudySession.Status.ACTIVE,
        new_word_target=new_word_target,
        planned_new_word_count=len(new_entries),
        item_count=len(due_states) + len(new_entries),
        planner_version=PLANNER_VERSION,
    )

    items: list[StudySessionItem] = []
    for position, state in enumerate(due_states, start=1):
        items.append(
            StudySessionItem(
                session=session,
                corpus_entry=entries_by_word[state.word_id],
                position=position,
                kind=StudySessionItem.Kind.DUE,
                due_at_snapshot=state.next_due_at,
                scheduler_version=state.scheduler_version,
                scheduling_state_snapshot=_state_snapshot(state),
            )
        )
    for position, entry in enumerate(new_entries, start=len(items) + 1):
        items.append(
            StudySessionItem(
                session=session,
                corpus_entry=entry,
                position=position,
                kind=StudySessionItem.Kind.NEW,
            )
        )
    StudySessionItem.objects.bulk_create(items)

    persisted = session_queryset().get(pk=session.pk)
    return PlannedSession(session=persisted, created=True)
