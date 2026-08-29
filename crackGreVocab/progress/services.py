"""Application policy for composing an authoritative Learning Progress snapshot."""

from dataclasses import asdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from accounts.models import LearnerAccount
from django.utils.timezone import now as current_time

from .selectors import (
    count_corpus_progress,
    count_today_activity,
    get_active_corpus,
    learner_has_active_session,
    list_recent_recall_outcomes,
)

RECENT_OUTCOME_LIMIT = 5


class ProgressUnavailable(Exception):
    """Learning Progress cannot be formed from the current product state."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _local_day_window(
    *,
    observed_at: datetime,
    learner_timezone: ZoneInfo,
) -> tuple[datetime, datetime, str]:
    local_date = observed_at.astimezone(learner_timezone).date()
    local_start = datetime.combine(local_date, time.min, learner_timezone)
    local_end = datetime.combine(
        local_date + timedelta(days=1),
        time.min,
        learner_timezone,
    )
    return (
        local_start.astimezone(UTC),
        local_end.astimezone(UTC),
        local_date.isoformat(),
    )


def build_learning_progress_summary(
    *,
    learner: LearnerAccount,
    timezone_name: str,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """Build one refresh-safe Learning Progress response for a learner."""
    observed_at = observed_at or current_time()
    learner_timezone = ZoneInfo(timezone_name)
    day_start, day_end, local_date = _local_day_window(
        observed_at=observed_at,
        learner_timezone=learner_timezone,
    )
    corpus = get_active_corpus()
    if corpus is None:
        raise ProgressUnavailable(
            "progress_corpus_unavailable",
            "No active vocabulary corpus is available.",
        )

    corpus_counts = count_corpus_progress(
        learner=learner,
        corpus=corpus,
        observed_at=observed_at,
        local_day_ends_at=day_end,
    )
    today_counts = count_today_activity(
        learner=learner,
        local_day_starts_at=day_start,
        local_day_ends_at=day_end,
    )
    return {
        "corpus": {
            "version": corpus.version,
            "total": corpus_counts.total,
            "unseen": corpus_counts.unseen,
            "learning": corpus_counts.learning,
            "review": corpus_counts.review,
        },
        "actionable": {
            "due_now": corpus_counts.due_now,
            "due_today": corpus_counts.due_today,
            "has_active_session": learner_has_active_session(learner=learner),
        },
        "today": {
            "date": local_date,
            "timezone": timezone_name,
            **asdict(today_counts),
        },
        "recent_outcomes": [
            asdict(outcome)
            for outcome in list_recent_recall_outcomes(
                learner=learner,
                limit=RECENT_OUTCOME_LIMIT,
            )
        ],
    }
