"""Read-only ORM queries for the Study domain."""

from datetime import datetime
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Count, F, Min, Q, QuerySet
from vocabulary.models import CorpusEntry, CorpusVersion

from .models import LearnerWordState, RecallAnswer, StudySession, StudySessionItem
from .new_words import select_new_word_ids
from .policy import PLANNER_VERSION

type DueItem = tuple[LearnerWordState, CorpusEntry]


def study_session_queryset() -> QuerySet[StudySession]:
    """Load the stable response representation without per-item queries."""
    return (
        StudySession.objects.select_related(
            "corpus",
            "current_item__corpus_entry__word",
        )
        .prefetch_related("current_item__corpus_entry__senses")
        .annotate(
            planned_new_word_count_value=Count(
                "session_words",
                filter=Q(session_words__kind="new"),
            ),
            word_count_value=Count("session_words"),
            cleared_word_count_value=Count(
                "session_words",
                filter=Q(session_words__cleared_at__isnull=False),
            ),
            next_ready_at_value=Min(
                "session_words__ready_at",
                filter=Q(session_words__cleared_at__isnull=True),
            ),
        )
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


def has_uncleared_session_words(*, session: StudySession) -> bool:
    """Return whether the daily session still contains unfinished Words."""
    return session.session_words.filter(cleared_at__isnull=True).exists()


def select_ready_session_item(
    *,
    session: StudySession,
    observed_at: datetime,
) -> StudySessionItem | None:
    """Return the fairest ready presentation attempt for an idle session."""
    return (
        StudySessionItem.objects.select_related("corpus_entry__word", "session_word")
        .filter(
            session=session,
            session_word__is_in_active_window=True,
            answer__isnull=True,
            ready_at__lte=observed_at,
        )
        .order_by(
            F("session_word__last_presented_position").asc(nulls_first=True),
            "session_word__position",
            "position",
        )
        .first()
    )


def select_due_study_items(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    due_before: datetime,
) -> tuple[DueItem, ...]:
    """Select the learner's scheduled Words due before the daily cutoff."""
    states = list(
        LearnerWordState.objects.filter(
            learner=learner,
            next_due_at__lt=due_before,
            word__corpus_entries__corpus=corpus,
        )
        .select_related("word")
        .order_by("next_due_at", "word__normalized_term", "id")
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
    """Select unseen entries in stable learner-deck order, loading only winners."""
    if limit <= 0:
        return ()
    candidates = (
        CorpusEntry.objects.filter(corpus=corpus)
        .exclude(word__learner_states__learner=learner)
        .order_by()
        .values_list("word_id", flat=True)
        .iterator(chunk_size=512)
    )
    selected = select_new_word_ids(
        candidates,
        learner_id=learner.pk,
        corpus_version=corpus.version,
        planner_version=PLANNER_VERSION,
        limit=limit,
    )
    entries = {
        entry.word_id: entry
        for entry in CorpusEntry.objects.filter(
            corpus=corpus, word_id__in=selected
        ).select_related("word")
    }
    return tuple(entries[word_id] for word_id in selected)
