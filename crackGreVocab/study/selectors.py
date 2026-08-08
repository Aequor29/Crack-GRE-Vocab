"""Read-only ORM queries for the Study domain."""

from datetime import datetime
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Prefetch, QuerySet
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import LearnerWordState, RecallAnswer, StudySession, StudySessionItem

type DueItem = tuple[LearnerWordState, CorpusEntry]


def study_session_queryset() -> QuerySet[StudySession]:
    """Load the stable response representation without per-item queries."""
    items = StudySessionItem.objects.select_related(
        "corpus_entry__word",
        "answer__outcome",
    ).prefetch_related("corpus_entry__senses")
    return StudySession.objects.select_related("corpus").prefetch_related(
        Prefetch("items", queryset=items),
    )


def get_study_session(*, session_id: UUID) -> StudySession:
    """Return one Study Session with its complete response representation."""
    return study_session_queryset().get(pk=session_id)


def get_active_study_session(*, learner: LearnerAccount) -> StudySession | None:
    """Return the learner's active Study Session, if one exists."""
    return (
        study_session_queryset()
        .filter(learner=learner, status=StudySession.Status.ACTIVE)
        .first()
    )


def get_active_corpus_version() -> CorpusVersion | None:
    """Return the vocabulary corpus currently available for study planning."""
    return CorpusVersion.objects.filter(is_active=True).first()


def get_recall_answer_by_request_id(*, request_id: UUID) -> RecallAnswer | None:
    """Return an accepted Recall Answer for an idempotency request ID."""
    return (
        RecallAnswer.objects.select_related("item__session", "outcome")
        .filter(client_request_id=request_id)
        .first()
    )


def get_recall_answer_for_item(*, item: StudySessionItem) -> RecallAnswer | None:
    """Return the accepted Recall Answer for a planned item, if present."""
    return RecallAnswer.objects.select_related("outcome").filter(item=item).first()


def select_due_study_items(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    planned_at: datetime,
    limit: int,
) -> tuple[DueItem, ...]:
    """Select the learner's oldest due words from the active corpus."""
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


def select_unseen_corpus_entries(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    limit: int,
) -> tuple[CorpusEntry, ...]:
    """Select ordered corpus entries the learner has never studied."""
    return tuple(
        CorpusEntry.objects.filter(corpus=corpus)
        .exclude(word__learner_states__learner=learner)
        .select_related("word")
        .order_by("position", "id")[:limit]
    )
