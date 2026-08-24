"""AEQ-14 deterministic and atomic Study Session planning coverage."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from study.models import LearnerWordState, SchedulingPhase, StudySession
from study.services import (
    StudyPlanningUnavailable,
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

    def test_due_items_precede_new_items(self):
        self.create_state(0, timedelta(minutes=-5))
        self.create_state(1, timedelta(minutes=-10))
        self.create_state(2, timedelta(days=1))

        planned = plan_study_session(
            learner=self.learner,
            new_word_target=2,
            planned_at=self.now,
        )

        self.assertTrue(planned.created)
        items = list(planned.session.items.all())
        self.assertEqual(len(items), 4)
        self.assertEqual(sum(item.kind == "new" for item in items), 2)
        self.assertEqual(
            [
                (item.kind, item.corpus_entry.term)
                for item in items
            ],
            [
                ("due", "lucid"),
                ("due", "abate"),
                ("new", "pragmatic"),
                ("new", "zeal"),
            ],
        )
        first_due = items[0]
        self.assertEqual(first_due.scheduler_version, "fsrs-adapter-v1")
        self.assertEqual(first_due.scheduling_state_snapshot, {"source": "fixture"})

    def test_due_work_consumes_session_capacity_before_new_material(self):
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        self.corpus, self.entries = create_corpus(
            tuple(f"word-{index:02d}" for index in range(32)),
            version="study-capacity-v1",
        )
        for index in range(29):
            self.create_state(index, timedelta(minutes=-(index + 1)))
        self.create_state(29, timedelta(days=1))

        planned = plan_study_session(
            learner=self.learner,
            new_word_target=2,
            planned_at=self.now,
        )

        items = list(planned.session.items.all())
        self.assertEqual(len(items), 30)
        self.assertEqual(sum(item.kind == "due" for item in items), 29)
        self.assertEqual(sum(item.kind == "new" for item in items), 1)

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

    def test_due_state_reuses_stable_word_identity_in_a_new_corpus_release(self):
        self.create_state(0, timedelta(minutes=-5))
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        next_corpus, next_entries = create_corpus(
            ("abate", "candid"),
            version="study-test-v2",
            words_by_term={"abate": self.entries[0].word},
        )

        planned = plan_study_session(
            learner=self.learner,
            new_word_target=1,
            planned_at=self.now,
        )

        due_item, new_item = planned.session.items.all()
        self.assertEqual(planned.session.corpus, next_corpus)
        self.assertEqual(due_item.corpus_entry, next_entries[0])
        self.assertEqual(due_item.corpus_entry.word, self.entries[0].word)
        self.assertEqual(new_item.corpus_entry, next_entries[1])

    def test_abandoned_unanswered_new_item_is_eligible_again(self):
        first = plan_study_session(
            learner=self.learner,
            new_word_target=1,
            planned_at=self.now,
        ).session
        first_item = first.items.get()
        first.close(StudySession.Status.ABANDONED, at=self.now)
        first.save(update_fields=("status", "ended_at", "updated_at"))

        resumed = plan_study_session(
            learner=self.learner,
            new_word_target=1,
            planned_at=self.now,
        ).session

        self.assertNotEqual(resumed.pk, first.pk)
        self.assertEqual(resumed.items.get().corpus_entry, first_item.corpus_entry)
        self.assertFalse(LearnerWordState.objects.exists())
