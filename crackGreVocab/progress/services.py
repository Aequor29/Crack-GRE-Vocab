"""Application policy for composing an authoritative Learning Progress snapshot."""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from accounts.models import LearnerAccount
from django.utils.timezone import now as current_time
from vocabulary.models import CorpusVersion

from .selectors import (
    WordPhaseChange,
    count_corpus_progress,
    count_review_recall_periods,
    count_today_activity,
    get_active_corpus,
    learner_has_active_session,
    list_latest_word_phases_before,
    list_study_dates,
    list_study_day_activity,
    list_word_phase_changes,
)

REVIEW_RECALL_PERIOD_DAYS = 7
REVIEW_RECALL_MINIMUM_ANSWERS = 10
INSIGHTS_CALENDAR_WEEKS = 12


@dataclass(frozen=True)
class LearningInsightsWindow:
    """Learner-local boundaries shared by every historical insight."""

    local_today: date
    current_starts_on: date
    previous_starts_on: date
    previous_ends_on: date
    calendar_starts_on: date
    curve_starts_at: datetime
    current_ends_at: datetime


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


def _local_date_start(*, local_date: date, learner_timezone: ZoneInfo) -> datetime:
    return datetime.combine(local_date, time.min, learner_timezone).astimezone(UTC)


def _review_recall_period(
    *,
    starts_on: date,
    ends_on: date,
    remembered: int,
    answers: int,
) -> dict[str, object]:
    return {
        "starts_on": starts_on.isoformat(),
        "ends_on": ends_on.isoformat(),
        "remembered": remembered,
        "answers": answers,
        "rate_percent": round(remembered * 100 / answers) if answers else None,
        "has_sufficient_data": answers >= REVIEW_RECALL_MINIMUM_ANSWERS,
    }


def _current_study_streak(*, local_today: date, study_dates: tuple[date, ...]) -> int:
    dates = set(study_dates)
    expected_date = local_today
    if expected_date not in dates:
        expected_date -= timedelta(days=1)
    streak = 0
    while expected_date in dates:
        streak += 1
        expected_date -= timedelta(days=1)
    return streak


def _learning_insights_window(
    *,
    observed_at: datetime,
    learner_timezone: ZoneInfo,
) -> LearningInsightsWindow:
    local_today = observed_at.astimezone(learner_timezone).date()
    current_starts_on = local_today - timedelta(days=REVIEW_RECALL_PERIOD_DAYS - 1)
    previous_ends_on = current_starts_on - timedelta(days=1)
    current_week_starts_on = local_today - timedelta(days=local_today.weekday())
    calendar_starts_on = current_week_starts_on - timedelta(
        weeks=INSIGHTS_CALENDAR_WEEKS - 1
    )
    return LearningInsightsWindow(
        local_today=local_today,
        current_starts_on=current_starts_on,
        previous_starts_on=current_starts_on
        - timedelta(days=REVIEW_RECALL_PERIOD_DAYS),
        previous_ends_on=previous_ends_on,
        calendar_starts_on=calendar_starts_on,
        curve_starts_at=_local_date_start(
            local_date=calendar_starts_on,
            learner_timezone=learner_timezone,
        ),
        current_ends_at=_local_date_start(
            local_date=local_today + timedelta(days=1),
            learner_timezone=learner_timezone,
        ),
    )


def _build_review_recall(
    *,
    learner: LearnerAccount,
    window: LearningInsightsWindow,
    learner_timezone: ZoneInfo,
) -> dict[str, object]:
    counts = count_review_recall_periods(
        learner=learner,
        previous_starts_at=_local_date_start(
            local_date=window.previous_starts_on,
            learner_timezone=learner_timezone,
        ),
        current_starts_at=_local_date_start(
            local_date=window.current_starts_on,
            learner_timezone=learner_timezone,
        ),
        current_ends_at=window.current_ends_at,
    )
    current = _review_recall_period(
        starts_on=window.current_starts_on,
        ends_on=window.local_today,
        remembered=counts.current_remembered,
        answers=counts.current_answers,
    )
    previous = _review_recall_period(
        starts_on=window.previous_starts_on,
        ends_on=window.previous_ends_on,
        remembered=counts.previous_remembered,
        answers=counts.previous_answers,
    )
    change = None
    if (
        counts.current_answers >= REVIEW_RECALL_MINIMUM_ANSWERS
        and counts.previous_answers >= REVIEW_RECALL_MINIMUM_ANSWERS
    ):
        current_rate = round(counts.current_remembered * 100 / counts.current_answers)
        previous_rate = round(
            counts.previous_remembered * 100 / counts.previous_answers
        )
        change = current_rate - previous_rate
    return {
        "current": current,
        "previous": previous,
        "change_percentage_points": change,
    }


def _build_study_consistency(
    *,
    learner: LearnerAccount,
    window: LearningInsightsWindow,
    learner_timezone: ZoneInfo,
) -> dict[str, object]:
    study_days = list_study_day_activity(
        learner=learner,
        starts_at=window.curve_starts_at,
        ends_at=window.current_ends_at,
        learner_timezone=learner_timezone,
    )
    study_dates = list_study_dates(
        learner=learner,
        ends_at=window.current_ends_at,
        learner_timezone=learner_timezone,
    )
    return {
        "calendar_starts_on": window.calendar_starts_on.isoformat(),
        "calendar_ends_on": window.local_today.isoformat(),
        "current_streak_days": _current_study_streak(
            local_today=window.local_today,
            study_dates=study_dates,
        ),
        "study_days": [asdict(day) for day in study_days],
    }


def _weekly_learning_curve(
    *,
    local_today: date,
    calendar_starts_on: date,
    learner_timezone: ZoneInfo,
    corpus_total: int,
    starting_phases: tuple[tuple[UUID, str], ...],
    phase_changes: tuple[WordPhaseChange, ...],
) -> list[dict[str, object]]:
    phases = dict(starting_phases)
    change_index = 0
    curve: list[dict[str, object]] = []
    for week_index in range(INSIGHTS_CALENDAR_WEEKS):
        starts_on = calendar_starts_on + timedelta(weeks=week_index)
        ends_on = min(starts_on + timedelta(days=6), local_today)
        snapshot_ends_at = _local_date_start(
            local_date=ends_on + timedelta(days=1),
            learner_timezone=learner_timezone,
        )
        while (
            change_index < len(phase_changes)
            and phase_changes[change_index].occurred_at < snapshot_ends_at
        ):
            change = phase_changes[change_index]
            phases[change.word_id] = change.next_phase
            change_index += 1
        review = sum(phase == "review" for phase in phases.values())
        learning = sum(phase in {"learning", "relearning"} for phase in phases.values())
        curve.append(
            {
                "starts_on": starts_on.isoformat(),
                "ends_on": ends_on.isoformat(),
                "unseen": max(0, corpus_total - len(phases)),
                "learning": learning,
                "review": review,
            }
        )
    return curve


def _build_weekly_learning_curve(
    *,
    learner: LearnerAccount,
    corpus: CorpusVersion,
    window: LearningInsightsWindow,
    learner_timezone: ZoneInfo,
) -> list[dict[str, object]]:
    starting_phases = list_latest_word_phases_before(
        learner=learner,
        corpus=corpus,
        before=window.curve_starts_at,
    )
    phase_changes = list_word_phase_changes(
        learner=learner,
        corpus=corpus,
        starts_at=window.curve_starts_at,
        ends_at=window.current_ends_at,
    )
    return _weekly_learning_curve(
        local_today=window.local_today,
        calendar_starts_on=window.calendar_starts_on,
        learner_timezone=learner_timezone,
        corpus_total=corpus.entries.count(),
        starting_phases=starting_phases,
        phase_changes=phase_changes,
    )


def build_learning_insights(
    *,
    learner: LearnerAccount,
    timezone_name: str,
    observed_at: datetime | None = None,
) -> dict[str, object]:
    """Build bounded historical Learning Progress insights for one learner."""
    observed_at = observed_at or current_time()
    learner_timezone = ZoneInfo(timezone_name)
    corpus = get_active_corpus()
    if corpus is None:
        raise ProgressUnavailable(
            "progress_corpus_unavailable",
            "No active vocabulary corpus is available.",
        )
    window = _learning_insights_window(
        observed_at=observed_at,
        learner_timezone=learner_timezone,
    )
    return {
        "as_of_date": window.local_today.isoformat(),
        "timezone": timezone_name,
        "review_recall": _build_review_recall(
            learner=learner,
            window=window,
            learner_timezone=learner_timezone,
        ),
        "consistency": _build_study_consistency(
            learner=learner,
            window=window,
            learner_timezone=learner_timezone,
        ),
        "learning_curve": _build_weekly_learning_curve(
            learner=learner,
            corpus=corpus,
            window=window,
            learner_timezone=learner_timezone,
        ),
    }


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
    }
