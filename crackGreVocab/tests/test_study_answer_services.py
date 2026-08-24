"""AEQ-15 transactional Recall Answer and Outcome coverage."""

import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from study.models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    StudySession,
)
from study.persistence import persist_recall_answer_transition
from study.scheduling import SchedulerTransition, schedule_recall
from study.services import (
    StudyAnswerConflict,
    StudyAnswerNotFound,
    plan_study_session,
    record_recall_answer,
)

from .study_helpers import create_corpus, create_learner


class RecallAnswerServiceTests(TestCase):
    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(("abate", "lucid"))
        self.now = timezone.now()

    def plan(self, target: int = 2):
        return plan_study_session(
            learner=self.learner,
            new_word_target=target,
            planned_at=self.now,
        ).session

    def test_new_answer_persists_one_auditable_transition_and_next_item(self):
        session = self.plan()
        first_item = session.items.all()[0]

        recorded = record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=first_item.pk,
            request_id=uuid.uuid4(),
            rating="remembered",
            occurred_at=self.now,
        )

        state = LearnerWordState.objects.get(
            learner=self.learner,
            word=first_item.corpus_entry.word,
        )
        self.assertTrue(recorded.created)
        self.assertEqual(recorded.outcome.previous_phase, "")
        self.assertEqual(recorded.outcome.previous_state, {})
        self.assertEqual(recorded.outcome.review_number, 1)
        self.assertEqual(state.review_count, 1)
        self.assertEqual(state.last_reviewed_at, self.now)
        self.assertEqual(state.next_due_at, self.now + timedelta(minutes=10))
        self.assertEqual(recorded.session.status, StudySession.Status.ACTIVE)
        self.assertEqual(recorded.session.items.all()[1].position, 2)
        self.assertEqual(RecallAnswer.objects.count(), 1)
        self.assertEqual(RecallOutcome.objects.count(), 1)

    def test_final_answer_completes_and_exact_retry_replays_without_rescheduling(self):
        session = self.plan(target=1)
        item = session.items.get()
        request_id = uuid.uuid4()

        created = record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=item.pk,
            request_id=request_id,
            rating="forgot",
            occurred_at=self.now,
        )
        replayed = record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=item.pk,
            request_id=request_id,
            rating="forgot",
            occurred_at=self.now + timedelta(hours=1),
        )

        self.assertTrue(created.created)
        self.assertFalse(replayed.created)
        self.assertEqual(replayed.answer.pk, created.answer.pk)
        self.assertEqual(replayed.outcome.pk, created.outcome.pk)
        self.assertEqual(replayed.session.status, StudySession.Status.COMPLETED)
        self.assertEqual(replayed.session.ended_at, self.now)
        self.assertEqual(RecallAnswer.objects.count(), 1)
        self.assertEqual(RecallOutcome.objects.count(), 1)
        self.assertEqual(LearnerWordState.objects.get().review_count, 1)

    def test_reused_key_answered_item_and_future_item_conflict_without_writes(self):
        session = self.plan()
        first_item, second_item = session.items.all()
        request_id = uuid.uuid4()
        record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=first_item.pk,
            request_id=request_id,
            rating="remembered",
            occurred_at=self.now,
        )

        with self.assertRaises(StudyAnswerConflict) as reused:
            record_recall_answer(
                learner=self.learner,
                session_id=session.pk,
                item_id=first_item.pk,
                request_id=request_id,
                rating="forgot",
            )
        with self.assertRaises(StudyAnswerConflict) as answered:
            record_recall_answer(
                learner=self.learner,
                session_id=session.pk,
                item_id=first_item.pk,
                request_id=uuid.uuid4(),
                rating="remembered",
            )

        self.assertEqual(reused.exception.code, "study_request_id_reused")
        self.assertEqual(answered.exception.code, "study_item_already_answered")
        self.assertEqual(RecallAnswer.objects.count(), 1)
        self.assertEqual(RecallOutcome.objects.count(), 1)

        other_session = StudySession.objects.create(
            learner=create_learner(email="other-session@example.com"),
            corpus=self.corpus,
            status=StudySession.Status.ACTIVE,
            new_word_target=1,
            planner_version="test",
        )
        with self.assertRaises(StudyAnswerNotFound):
            record_recall_answer(
                learner=self.learner,
                session_id=other_session.pk,
                item_id=second_item.pk,
                request_id=uuid.uuid4(),
                rating="remembered",
            )

    def test_future_item_conflict_leaves_durable_state_unchanged(self):
        session = self.plan()
        first_item, second_item = session.items.all()

        with self.assertRaises(StudyAnswerConflict) as out_of_order:
            record_recall_answer(
                learner=self.learner,
                session_id=session.pk,
                item_id=second_item.pk,
                request_id=uuid.uuid4(),
                rating="remembered",
            )
        self.assertEqual(out_of_order.exception.code, "study_item_out_of_order")
        self.assertEqual(out_of_order.exception.current_item_id, first_item.pk)

        session.refresh_from_db()
        self.assertEqual(session.status, StudySession.Status.ACTIVE)
        self.assertFalse(RecallAnswer.objects.exists())
        self.assertFalse(RecallOutcome.objects.exists())
        self.assertFalse(LearnerWordState.objects.exists())

    def test_failed_outcome_write_rolls_back_the_partial_transition(self):
        session = self.plan(target=1)
        item = session.items.get()
        invalid_transition = SchedulerTransition(
            scheduler_version="test-scheduler",
            next_phase="learning",
            next_due_at=self.now + timedelta(minutes=10),
            next_state={},
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            persist_recall_answer_transition(
                learner=self.learner,
                item=item,
                state=None,
                rating="remembered",
                request_id=uuid.uuid4(),
                occurred_at=self.now,
                transition=invalid_transition,
            )

        session.refresh_from_db()
        self.assertEqual(session.status, StudySession.Status.ACTIVE)
        self.assertFalse(RecallAnswer.objects.exists())
        self.assertFalse(RecallOutcome.objects.exists())
        self.assertFalse(LearnerWordState.objects.exists())

    def test_new_and_learning_failures_do_not_increment_lapses(self):
        initial_at = self.now - timedelta(minutes=2)
        session = self.plan(target=1)
        item = session.items.get()
        record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=item.pk,
            request_id=uuid.uuid4(),
            rating="forgot",
            occurred_at=initial_at,
        )
        state = LearnerWordState.objects.get()
        self.assertEqual(state.phase, "learning")
        self.assertEqual(state.lapse_count, 0)

        learning_session = plan_study_session(
            learner=self.learner,
            new_word_target=0,
            planned_at=state.next_due_at,
        ).session
        record_recall_answer(
            learner=self.learner,
            session_id=learning_session.pk,
            item_id=learning_session.items.get().pk,
            request_id=uuid.uuid4(),
            rating="forgot",
            occurred_at=state.next_due_at,
        )

        state.refresh_from_db()
        self.assertEqual(state.phase, "learning")
        self.assertEqual(state.lapse_count, 0)

    def test_due_review_failure_snapshots_state_and_increments_lapse(self):
        first_review_at = self.now - timedelta(days=2, minutes=10)
        first = schedule_recall(
            word_id=self.entries[0].word_id,
            rating="remembered",
            occurred_at=first_review_at,
            previous_state=None,
            previous_scheduler_version=None,
        )
        review = schedule_recall(
            word_id=self.entries[0].word_id,
            rating="remembered",
            occurred_at=first.next_due_at,
            previous_state=first.next_state,
            previous_scheduler_version=first.scheduler_version,
        )
        state = LearnerWordState.objects.create(
            learner=self.learner,
            word=self.entries[0].word,
            phase=review.next_phase,
            review_count=2,
            last_reviewed_at=first.next_due_at,
            next_due_at=review.next_due_at,
            scheduler_version=review.scheduler_version,
            scheduler_state=review.next_state,
        )
        session = plan_study_session(
            learner=self.learner,
            new_word_target=0,
            planned_at=review.next_due_at,
        ).session
        item = session.items.get()

        recorded = record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=item.pk,
            request_id=uuid.uuid4(),
            rating="forgot",
            occurred_at=review.next_due_at,
        )

        state.refresh_from_db()
        self.assertEqual(recorded.outcome.previous_phase, "review")
        self.assertEqual(recorded.outcome.previous_state, review.next_state)
        self.assertEqual(recorded.outcome.review_number, 3)
        self.assertEqual(state.phase, "relearning")
        self.assertEqual(state.lapse_count, 1)
        self.assertEqual(
            state.next_due_at,
            review.next_due_at + timedelta(minutes=10),
        )
