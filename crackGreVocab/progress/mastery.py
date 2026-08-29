"""Canonical Learning Progress classification for durable Word mastery."""

from datetime import datetime, timedelta

from django.db.models import F, Q
from study.models import SchedulingPhase

MASTERY_MINIMUM_REVIEW_COUNT = 3
MASTERY_MINIMUM_INTERVAL = timedelta(days=30)


def mastered_word_condition() -> Q:
    """Return the ORM condition for Words that satisfy the mastery policy."""
    return Q(
        phase=SchedulingPhase.REVIEW,
        review_count__gte=MASTERY_MINIMUM_REVIEW_COUNT,
        next_due_at__gte=F("last_reviewed_at") + MASTERY_MINIMUM_INTERVAL,
    )


def is_mastered_word(
    *,
    phase: str,
    review_count: int,
    last_reviewed_at: datetime,
    next_due_at: datetime,
) -> bool:
    """Return whether one scheduling snapshot satisfies the mastery policy."""
    return (
        phase == SchedulingPhase.REVIEW
        and review_count >= MASTERY_MINIMUM_REVIEW_COUNT
        and next_due_at - last_reviewed_at >= MASTERY_MINIMUM_INTERVAL
    )
