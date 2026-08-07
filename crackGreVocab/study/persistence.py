"""ORM locking and writes for backend-planned Study Sessions."""

from collections.abc import Sequence
from decimal import Decimal

from accounts.models import LearnerAccount
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import LearnerWordState, StudySession, StudySessionItem
from .selectors import DueItem


def lock_learner(*, learner_id: int) -> LearnerAccount:
    return LearnerAccount.objects.select_for_update().get(pk=learner_id)


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
