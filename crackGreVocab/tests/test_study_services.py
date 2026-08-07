"""AEQ-14 deterministic and atomic Study Session planning coverage."""

from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone
from study.models import LearnerWordState, SchedulingPhase, StudySession
from study.services import (
    StudyPlanningUnavailable,
    StudyPlanPolicy,
    plan_study_session,
)

from .study_helpers import create_corpus, create_learner


class StudySessionPlanningTests(TestCase):
    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(
            ("abate", "lucid", "opaque", "pragmatic", "zeal")
        )
        self.now = timezone.now()

    def create_state(self, entry_index: int, due_delta: timedelta) -> None:
        LearnerWordState.objects.create(
            learner=self.learner,
            word=self.entries[entry_index].word,
            phase=SchedulingPhase.REVIEW,
            review_count=2,
            last_reviewed_at=self.now - timedelta(days=1),
            next_due_at=self.now + due_delta,
            scheduler_version="fsrs-adapter-v1",
            scheduler_state={"source": "fixture"},
        )

    def test_due_items_precede_new_items_and_capacity_reduces_new_target(self):
        self.create_state(0, timedelta(minutes=-5))
        self.create_state(1, timedelta(minutes=-10))
        self.create_state(2, timedelta(days=1))

        planned = plan_study_session(
            learner=self.learner,
            new_word_target=2,
            policy=StudyPlanPolicy(max_items=3, max_new_words=2),
            planned_at=self.now,
        )

        self.assertTrue(planned.created)
        self.assertEqual(planned.session.item_count, 3)
        self.assertEqual(planned.session.planned_new_word_count, 1)
        self.assertEqual(
            [
                (item.kind, item.corpus_entry.term)
                for item in planned.session.items.all()
            ],
            [("due", "lucid"), ("due", "abate"), ("new", "pragmatic")],
        )
        first_due = planned.session.items.all()[0]
        self.assertEqual(first_due.scheduler_version, "fsrs-adapter-v1")
        self.assertEqual(first_due.scheduling_state_snapshot["review_count"], 2)

    def test_repeated_creation_resumes_the_same_persisted_session(self):
        first = plan_study_session(learner=self.learner, new_word_target=2)
        second = plan_study_session(learner=self.learner, new_word_target=5)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.session.pk, first.session.pk)
        self.assertEqual(second.session.new_word_target, 2)
        self.assertEqual(StudySession.objects.count(), 1)

    def test_missing_corpus_and_no_eligible_items_fail_explicitly(self):
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        with self.assertRaisesMessage(StudyPlanningUnavailable, "No active"):
            plan_study_session(learner=self.learner, new_word_target=1)

        self.corpus.is_active = True
        self.corpus.save(update_fields=("is_active",))
        for index in range(len(self.entries)):
            self.create_state(index, timedelta(days=1))
        with self.assertRaisesMessage(StudyPlanningUnavailable, "No vocabulary"):
            plan_study_session(learner=self.learner, new_word_target=1)

    def test_item_persistence_failure_rolls_back_the_session(self):
        with (
            patch(
                "study.services.StudySessionItem.objects.bulk_create",
                side_effect=DatabaseError("simulated write failure"),
            ),
            self.assertRaises(DatabaseError),
        ):
            plan_study_session(learner=self.learner, new_word_target=1)

        self.assertFalse(StudySession.objects.exists())
