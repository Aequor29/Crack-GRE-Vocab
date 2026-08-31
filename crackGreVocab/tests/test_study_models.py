"""AEQ-13 Study domain relationship and invariant coverage."""

import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from study.models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    SchedulingPhase,
    StudySession,
    StudySessionItem,
    StudySessionWord,
)
from study.persistence import persist_study_session_plan

from .study_helpers import create_corpus, create_learner


class StudyDomainModelTests(TestCase):
    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(("abate", "lucid"))
        self.now = timezone.now()

    def create_session(self, **overrides) -> StudySession:
        values = {
            "corpus": self.corpus,
            "learner": self.learner,
            "new_word_target": 1,
            "planner_version": "test-planner-v1",
            "status": StudySession.Status.ACTIVE,
        }
        values.update(overrides)
        return StudySession.objects.create(**values)

    def test_schema_persists_only_current_study_behavior(self):
        session_fields = {field.name for field in StudySession._meta.get_fields()}
        item_fields = {field.name for field in StudySessionItem._meta.get_fields()}
        state_fields = {field.name for field in LearnerWordState._meta.get_fields()}

        self.assertFalse({"item_count", "planned_new_word_count"} & session_fields)
        self.assertFalse({"presented_at", "revealed_at"} & item_fields)
        self.assertFalse({"difficulty", "stability"} & state_fields)

    def test_representative_history_lifecycle_is_durable_and_linked(self):
        state = LearnerWordState.objects.create(
            learner=self.learner,
            word=self.entries[0].word,
            phase=SchedulingPhase.LEARNING,
            review_count=1,
            last_reviewed_at=self.now,
            next_due_at=self.now + timedelta(minutes=10),
            scheduler_version="fsrs-adapter-v1",
            scheduler_state={"step": 1},
        )
        session = self.create_session(
            new_word_target=0,
        )
        item = StudySessionItem.objects.create(
            session=session,
            session_word=StudySessionWord.objects.create(
                session=session,
                corpus_entry=self.entries[0],
                position=1,
                kind=StudySessionWord.Kind.DUE,
                ready_at=state.next_due_at,
            ),
            corpus_entry=self.entries[0],
            position=1,
            kind=StudySessionItem.Kind.DUE,
            due_at_snapshot=state.next_due_at,
            scheduler_version=state.scheduler_version,
            scheduling_state_snapshot=state.scheduler_state,
        )
        answer = RecallAnswer.objects.create(
            item=item,
            rating=RecallAnswer.Rating.REMEMBERED,
            client_request_id=uuid.uuid4(),
            submitted_at=self.now,
        )
        outcome = RecallOutcome.objects.create(
            answer=answer,
            review_number=2,
            scheduler_version="fsrs-adapter-v1",
            previous_phase=SchedulingPhase.LEARNING,
            next_phase=SchedulingPhase.REVIEW,
            previous_due_at=state.next_due_at,
            next_due_at=self.now + timedelta(days=1),
            previous_state={"step": 1},
            next_state={"stability": "1.0"},
            occurred_at=self.now,
        )

        self.assertEqual(outcome.answer.item.session.learner, self.learner)
        self.assertEqual(outcome.answer.item.corpus_entry.word, state.word)
        self.assertEqual(session.items.get(), item)

    def test_constraints_reject_duplicate_active_session_and_membership(self):
        session = self.create_session()
        StudySessionWord.objects.create(
            session=session,
            corpus_entry=self.entries[0],
            position=1,
            kind=StudySessionWord.Kind.NEW,
            ready_at=self.now,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_session()
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudySessionWord.objects.create(
                session=session,
                corpus_entry=self.entries[0],
                position=2,
                kind=StudySessionWord.Kind.NEW,
                ready_at=self.now,
            )

    def test_plan_write_rejects_cross_corpus_membership_before_persisting(self):
        other_corpus, other_entries = create_corpus(
            ("opaque",),
            version="study-test-v2",
            is_active=False,
        )
        self.assertNotEqual(other_corpus, self.corpus)

        with self.assertRaisesMessage(ValueError, "session corpus"):
            persist_study_session_plan(
                learner=self.learner,
                corpus=self.corpus,
                timezone_name="UTC",
                day_ends_at=self.now + timedelta(days=1),
                planned_at=self.now,
                new_word_target=1,
                max_active_words=30,
                due_items=(),
                new_entries=(other_entries[0],),
                planner_version="test-planner-v1",
            )
        self.assertFalse(StudySession.objects.exists())

    def test_failed_item_write_rolls_back_the_session(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            persist_study_session_plan(
                learner=self.learner,
                corpus=self.corpus,
                timezone_name="UTC",
                day_ends_at=self.now + timedelta(days=1),
                planned_at=self.now,
                new_word_target=2,
                max_active_words=30,
                due_items=(),
                new_entries=(self.entries[0], self.entries[0]),
                planner_version="test-planner-v1",
            )

        self.assertFalse(StudySession.objects.exists())

    def test_constraints_reject_malformed_state_and_outcome_history(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LearnerWordState.objects.create(
                learner=self.learner,
                word=self.entries[0].word,
                phase=SchedulingPhase.REVIEW,
                review_count=1,
                lapse_count=2,
                last_reviewed_at=self.now,
                next_due_at=self.now + timedelta(days=1),
                scheduler_version="fsrs-adapter-v1",
            )

        session = self.create_session()
        session_word = StudySessionWord.objects.create(
            session=session,
            corpus_entry=self.entries[0],
            position=1,
            kind=StudySessionWord.Kind.NEW,
            ready_at=self.now,
        )
        item = StudySessionItem.objects.create(
            session=session,
            session_word=session_word,
            corpus_entry=self.entries[0],
            position=1,
            kind=StudySessionItem.Kind.NEW,
        )
        answer = RecallAnswer.objects.create(
            item=item,
            rating=RecallAnswer.Rating.FORGOT,
            client_request_id=uuid.uuid4(),
            submitted_at=self.now,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RecallOutcome.objects.create(
                answer=answer,
                review_number=1,
                scheduler_version="fsrs-adapter-v1",
                previous_phase="",
                next_phase=SchedulingPhase.LEARNING,
                previous_due_at=None,
                next_due_at=self.now,
                previous_state={},
                next_state={},
                occurred_at=self.now,
            )

    def test_close_requires_an_active_session_and_records_end(self):
        session = self.create_session()
        session.close("abandoned", at=self.now)
        session.save(update_fields=("status", "ended_at", "updated_at"))

        session.refresh_from_db()
        self.assertEqual(session.status, StudySession.Status.ABANDONED)
        self.assertEqual(session.ended_at, self.now)
        with self.assertRaisesMessage(ValueError, "Only an active"):
            session.close("completed")
