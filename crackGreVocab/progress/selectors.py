"""Bounded ORM reads used to build Learning Progress."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Count, Q
from study.models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    SchedulingPhase,
    StudySession,
)
from vocabulary.models import CorpusVersion


@dataclass(frozen=True)
class CorpusProgressCounts:
    """Current scheduling counts for the active Vocabulary Corpus."""

    total: int
    unseen: int
    learning: int
    review: int
    due_now: int
    due_today: int


@dataclass(frozen=True)
class TodayActivityCounts:
    """Accepted learner activity within one local-day window."""

    sessions_started: int
    sessions_completed: int
    answers: int
    remembered: int
    forgot: int


@dataclass(frozen=True)
class RecentRecallOutcome:
    """One recent learner-visible scheduling result."""

    word_id: UUID
    term: str
    rating: str
    phase: str
    next_due_at: datetime
    occurred_at: datetime


def get_active_corpus() -> CorpusVersion | None:
    """Return the Vocabulary Corpus used for the current progress snapshot."""
    return CorpusVersion.objects.filter(is_active=True).first()


def count_corpus_progress(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    observed_at: datetime,
    local_day_ends_at: datetime,
) -> CorpusProgressCounts:
    """Count mutually intelligible coverage and actionable due states."""
    total = corpus.entries.count()
    aggregates = LearnerWordState.objects.filter(
        learner=learner,
        word__corpus_entries__corpus=corpus,
    ).aggregate(
        seen=Count("id"),
        learning=Count(
            "id",
            filter=Q(
                phase__in=(
                    SchedulingPhase.LEARNING,
                    SchedulingPhase.RELEARNING,
                )
            ),
        ),
        review=Count("id", filter=Q(phase=SchedulingPhase.REVIEW)),
        due_now=Count("id", filter=Q(next_due_at__lte=observed_at)),
        due_today=Count("id", filter=Q(next_due_at__lt=local_day_ends_at)),
    )
    seen = aggregates["seen"] or 0
    return CorpusProgressCounts(
        total=total,
        unseen=max(0, total - seen),
        learning=aggregates["learning"] or 0,
        review=aggregates["review"] or 0,
        due_now=aggregates["due_now"] or 0,
        due_today=aggregates["due_today"] or 0,
    )


def learner_has_active_session(*, learner: LearnerAccount) -> bool:
    """Return whether the learner has a resumable Study Session."""
    return StudySession.objects.filter(
        learner=learner,
        status=StudySession.Status.ACTIVE,
    ).exists()


def count_today_activity(
    *,
    learner: LearnerAccount,
    local_day_starts_at: datetime,
    local_day_ends_at: datetime,
) -> TodayActivityCounts:
    """Count Study Sessions and Recall Answers inside a local-day window."""
    sessions = StudySession.objects.filter(learner=learner)
    sessions_started = sessions.filter(
        created_at__gte=local_day_starts_at,
        created_at__lt=local_day_ends_at,
    ).count()
    sessions_completed = sessions.filter(
        status=StudySession.Status.COMPLETED,
        ended_at__gte=local_day_starts_at,
        ended_at__lt=local_day_ends_at,
    ).count()
    answers = RecallAnswer.objects.filter(
        item__session__learner=learner,
        accepted_at__gte=local_day_starts_at,
        accepted_at__lt=local_day_ends_at,
    ).aggregate(
        answers=Count("id"),
        remembered=Count(
            "id",
            filter=Q(rating=RecallAnswer.Rating.REMEMBERED),
        ),
        forgot=Count("id", filter=Q(rating=RecallAnswer.Rating.FORGOT)),
    )
    return TodayActivityCounts(
        sessions_started=sessions_started,
        sessions_completed=sessions_completed,
        answers=answers["answers"] or 0,
        remembered=answers["remembered"] or 0,
        forgot=answers["forgot"] or 0,
    )


def list_recent_recall_outcomes(
    *,
    learner: LearnerAccount,
    limit: int,
) -> tuple[RecentRecallOutcome, ...]:
    """Return a bounded newest-first Recall Outcome summary for one learner."""
    outcomes = (
        RecallOutcome.objects.filter(answer__item__session__learner=learner)
        .select_related("answer__item__corpus_entry")
        .order_by("-occurred_at", "-id")[:limit]
    )
    return tuple(
        RecentRecallOutcome(
            word_id=outcome.answer.item.corpus_entry.word_id,
            term=outcome.answer.item.corpus_entry.term,
            rating=outcome.answer.rating,
            phase=outcome.next_phase,
            next_due_at=outcome.next_due_at,
            occurred_at=outcome.occurred_at,
        )
        for outcome in outcomes
    )
