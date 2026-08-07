"""Read-only ORM queries for the Study domain."""

from datetime import datetime
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Prefetch
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import LearnerWordState, RecallAnswer, StudySession, StudySessionItem

type DueItem = tuple[LearnerWordState, CorpusEntry]


def session_queryset():
    """Load the stable response representation without per-item queries."""
    items = StudySessionItem.objects.select_related(
        "corpus_entry__word",
        "answer__outcome",
    ).prefetch_related("corpus_entry__senses")
    return StudySession.objects.select_related("corpus").prefetch_related(
        Prefetch("items", queryset=items),
    )


def get_session(*, session_id) -> StudySession:
    return session_queryset().get(pk=session_id)


def get_active_session(*, learner: LearnerAccount) -> StudySession | None:
    return (
        session_queryset()
        .filter(learner=learner, status=StudySession.Status.ACTIVE)
        .first()
    )


def get_active_corpus() -> CorpusVersion | None:
    return CorpusVersion.objects.filter(is_active=True).first()


def get_answer_by_request_id(*, request_id: UUID) -> RecallAnswer | None:
    return (
        RecallAnswer.objects.select_related("item__session", "outcome")
        .filter(client_request_id=request_id)
        .first()
    )


def get_item_answer(*, item: StudySessionItem) -> RecallAnswer | None:
    return RecallAnswer.objects.select_related("outcome").filter(item=item).first()


def select_due_items(
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


def select_new_entries(
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
