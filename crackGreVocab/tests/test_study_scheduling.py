"""Deterministic Milestone 1 FSRS adapter coverage."""

from datetime import UTC, datetime, timedelta
from unittest import TestCase
from uuid import UUID

from study.scheduling import (
    SCHEDULER_VERSION,
    SchedulingStateError,
    schedule_recall,
)


class StudySchedulingTests(TestCase):
    word_id = UUID("00000000-0000-0000-0000-000000000001")
    occurred_at = datetime(2026, 1, 1, tzinfo=UTC)

    def test_binary_new_word_ratings_use_exact_learning_boundaries(self):
        forgot = schedule_recall(
            word_id=self.word_id,
            rating="forgot",
            occurred_at=self.occurred_at,
            previous_state=None,
            previous_scheduler_version=None,
        )
        remembered = schedule_recall(
            word_id=self.word_id,
            rating="remembered",
            occurred_at=self.occurred_at,
            previous_state=None,
            previous_scheduler_version=None,
        )

        self.assertEqual(forgot.scheduler_version, SCHEDULER_VERSION)
        self.assertEqual(forgot.next_phase, "learning")
        self.assertEqual(forgot.next_due_at, self.occurred_at + timedelta(minutes=1))
        self.assertEqual(remembered.next_phase, "learning")
        self.assertEqual(
            remembered.next_due_at,
            self.occurred_at + timedelta(minutes=10),
        )
        self.assertEqual(remembered.next_state["card_id"], self.word_id.int)

    def test_review_failure_enters_the_exact_relearning_step(self):
        learning = schedule_recall(
            word_id=self.word_id,
            rating="remembered",
            occurred_at=self.occurred_at,
            previous_state=None,
            previous_scheduler_version=None,
        )
        review = schedule_recall(
            word_id=self.word_id,
            rating="remembered",
            occurred_at=learning.next_due_at,
            previous_state=learning.next_state,
            previous_scheduler_version=learning.scheduler_version,
        )
        relearning = schedule_recall(
            word_id=self.word_id,
            rating="forgot",
            occurred_at=review.next_due_at,
            previous_state=review.next_state,
            previous_scheduler_version=review.scheduler_version,
        )

        self.assertEqual(review.next_phase, "review")
        self.assertEqual(relearning.next_phase, "relearning")
        self.assertEqual(
            relearning.next_due_at,
            review.next_due_at + timedelta(minutes=10),
        )

    def test_malformed_or_wrong_version_state_fails_closed(self):
        with self.assertRaises(SchedulingStateError):
            schedule_recall(
                word_id=self.word_id,
                rating="remembered",
                occurred_at=self.occurred_at,
                previous_state={"card_id": self.word_id.int},
                previous_scheduler_version=SCHEDULER_VERSION,
            )
        with self.assertRaises(SchedulingStateError):
            schedule_recall(
                word_id=self.word_id,
                rating="remembered",
                occurred_at=self.occurred_at,
                previous_state={},
                previous_scheduler_version="unknown-scheduler",
            )
