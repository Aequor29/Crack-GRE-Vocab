"""Product-owned, deterministic FSRS adapter for Recall Outcomes."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from fsrs import Card, Rating, Scheduler, State

SCHEDULER_VERSION = "m1-fsrs-6.3.1-binary-v1"

FSRS_PARAMETERS = (
    0.212,
    1.2931,
    2.3065,
    8.2956,
    6.4133,
    0.8334,
    3.0194,
    0.001,
    1.8722,
    0.1666,
    0.796,
    1.4835,
    0.0614,
    0.2629,
    1.6483,
    0.6014,
    1.8729,
    0.5425,
    0.0912,
    0.0658,
    0.1542,
)

_SCHEDULER = Scheduler(
    parameters=FSRS_PARAMETERS,
    desired_retention=0.9,
    learning_steps=(timedelta(minutes=1), timedelta(minutes=10)),
    relearning_steps=(timedelta(minutes=10),),
    maximum_interval=36_500,
    enable_fuzzing=False,
)

_RATINGS = {
    "forgot": Rating.Again,
    "remembered": Rating.Good,
}

_PHASES = {
    State.Learning: "learning",
    State.Review: "review",
    State.Relearning: "relearning",
}


class SchedulingStateError(ValueError):
    """Stored state cannot be safely consumed by the active scheduler."""


@dataclass(frozen=True)
class SchedulerTransition:
    """The deterministic scheduling state produced by one recall grade."""

    scheduler_version: str
    next_phase: str
    next_due_at: datetime
    next_state: dict[str, object]


def _require_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchedulingStateError("Scheduler instants must be timezone-aware.")
    return value.astimezone(UTC)


def _restore_fsrs_card(
    *,
    word_id: UUID,
    scheduler_version: str,
    state: Mapping[str, object],
) -> Card:
    if scheduler_version != SCHEDULER_VERSION:
        raise SchedulingStateError("The stored scheduler version is unsupported.")
    try:
        card = Card.from_dict(cast(Any, dict(state)))
    except (KeyError, TypeError, ValueError) as exc:
        raise SchedulingStateError("The stored scheduler state is malformed.") from exc
    if card.card_id != word_id.int:
        raise SchedulingStateError(
            "The stored scheduler state belongs to another Word."
        )
    return card


def schedule_recall(
    *,
    word_id: UUID,
    rating: str,
    occurred_at: datetime,
    previous_state: Mapping[str, object] | None,
    previous_scheduler_version: str | None,
) -> SchedulerTransition:
    """Calculate the next scheduling state for a recall grade."""
    try:
        fsrs_rating = _RATINGS[rating]
    except KeyError as exc:
        raise ValueError("rating must be remembered or forgot.") from exc

    occurred_at = _require_utc_datetime(occurred_at)
    if previous_state is None:
        card = Card(card_id=word_id.int, due=occurred_at)
    else:
        if previous_scheduler_version is None:
            raise SchedulingStateError("Stored scheduler state has no version.")
        card = _restore_fsrs_card(
            word_id=word_id,
            scheduler_version=previous_scheduler_version,
            state=previous_state,
        )

    next_card, _ = _SCHEDULER.review_card(
        card,
        fsrs_rating,
        review_datetime=occurred_at,
    )
    return SchedulerTransition(
        scheduler_version=SCHEDULER_VERSION,
        next_phase=_PHASES[next_card.state],
        next_due_at=next_card.due,
        next_state=dict(next_card.to_dict()),
    )
