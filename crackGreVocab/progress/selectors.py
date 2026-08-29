"""Bounded ORM reads used to build Learning Progress."""

from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from uuid import UUID

from accounts.models import LearnerAccount
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
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
class ReviewRecallPeriodCounts:
    """Review-phase Recall Answers in the current and previous periods."""

    current_answers: int
    current_remembered: int
    previous_answers: int
    previous_remembered: int


@dataclass(frozen=True)
class StudyDayCounts:
    """Accepted recall activity for one learner-local Study Day."""

    date: date
    answers: int
    words_practiced: int


@dataclass(frozen=True)
class WordPhaseChange:
    """One Word's persisted scheduling phase transition."""

    word_id: UUID
    occurred_at: datetime
    next_phase: str


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


def count_review_recall_periods(
    *,
    learner: LearnerAccount,
    previous_starts_at: datetime,
    current_starts_at: datetime,
    current_ends_at: datetime,
) -> ReviewRecallPeriodCounts:
    """Count review-phase answers across two adjacent bounded periods."""
    outcomes = RecallAnswer.objects.filter(
        item__session__learner=learner,
        outcome__previous_phase=SchedulingPhase.REVIEW,
        outcome__occurred_at__gte=previous_starts_at,
        outcome__occurred_at__lt=current_ends_at,
    ).aggregate(
        current_answers=Count(
            "id",
            filter=Q(outcome__occurred_at__gte=current_starts_at),
        ),
        current_remembered=Count(
            "id",
            filter=Q(
                outcome__occurred_at__gte=current_starts_at,
                rating=RecallAnswer.Rating.REMEMBERED,
            ),
        ),
        previous_answers=Count(
            "id",
            filter=Q(outcome__occurred_at__lt=current_starts_at),
        ),
        previous_remembered=Count(
            "id",
            filter=Q(
                outcome__occurred_at__lt=current_starts_at,
                rating=RecallAnswer.Rating.REMEMBERED,
            ),
        ),
    )
    return ReviewRecallPeriodCounts(
        current_answers=outcomes["current_answers"] or 0,
        current_remembered=outcomes["current_remembered"] or 0,
        previous_answers=outcomes["previous_answers"] or 0,
        previous_remembered=outcomes["previous_remembered"] or 0,
    )


def list_study_day_activity(
    *,
    learner: LearnerAccount,
    starts_at: datetime,
    ends_at: datetime,
    learner_timezone: tzinfo,
) -> tuple[StudyDayCounts, ...]:
    """Return daily accepted Recall Outcome counts inside a bounded window."""
    rows = (
        RecallOutcome.objects.filter(
            answer__item__session__learner=learner,
            occurred_at__gte=starts_at,
            occurred_at__lt=ends_at,
        )
        .annotate(local_date=TruncDate("occurred_at", tzinfo=learner_timezone))
        .values("local_date")
        .annotate(
            answers=Count("id"),
            words_practiced=Count(
                "answer__item__corpus_entry__word_id",
                distinct=True,
            ),
        )
        .order_by("local_date")
    )
    return tuple(
        StudyDayCounts(
            date=row["local_date"],
            answers=row["answers"],
            words_practiced=row["words_practiced"],
        )
        for row in rows
    )


def list_study_dates(
    *,
    learner: LearnerAccount,
    ends_at: datetime,
    learner_timezone: tzinfo,
) -> tuple[date, ...]:
    """Return every Study Day through the current local-day boundary."""
    return tuple(
        RecallOutcome.objects.filter(
            answer__item__session__learner=learner,
            occurred_at__lt=ends_at,
        )
        .annotate(local_date=TruncDate("occurred_at", tzinfo=learner_timezone))
        .values_list("local_date", flat=True)
        .distinct()
        .order_by("-local_date")
    )


def list_latest_word_phases_before(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    before: datetime,
) -> tuple[tuple[UUID, str], ...]:
    """Return each encountered Word's last phase before a bounded curve window."""
    word_id = "answer__item__corpus_entry__word_id"
    return tuple(
        RecallOutcome.objects.filter(
            answer__item__session__learner=learner,
            answer__item__corpus_entry__word__corpus_entries__corpus=corpus,
            occurred_at__lt=before,
        )
        .order_by(word_id, "-occurred_at", "-id")
        .distinct(word_id)
        .values_list(word_id, "next_phase")
    )


def list_word_phase_changes(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    starts_at: datetime,
    ends_at: datetime,
) -> tuple[WordPhaseChange, ...]:
    """Return ordered phase transitions inside a bounded curve window."""
    rows = RecallOutcome.objects.filter(
        answer__item__session__learner=learner,
        answer__item__corpus_entry__word__corpus_entries__corpus=corpus,
        occurred_at__gte=starts_at,
        occurred_at__lt=ends_at,
    ).order_by("occurred_at", "id")
    return tuple(
        WordPhaseChange(
            word_id=word_id,
            occurred_at=occurred_at,
            next_phase=next_phase,
        )
        for word_id, occurred_at, next_phase in rows.values_list(
            "answer__item__corpus_entry__word_id",
            "occurred_at",
            "next_phase",
        )
    )
