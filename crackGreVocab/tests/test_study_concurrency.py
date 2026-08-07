"""AEQ-16 PostgreSQL concurrency and retry guarantees."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from accounts.models import LearnerAccount
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, skipUnlessDBFeature
from study.models import LearnerWordState, RecallAnswer, RecallOutcome, StudySession
from study.services import StudyAnswerConflict, plan_study_session, record_recall_answer

from .study_helpers import create_corpus, create_learner


@skipUnlessDBFeature("has_select_for_update")
class StudyConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("The production row-lock contract requires PostgreSQL.")
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(("abate", "lucid"))

    @staticmethod
    def _thread_call(barrier: Barrier, operation):
        close_old_connections()
        try:
            learner = LearnerAccount.objects.get(pk=operation["learner_id"])
            barrier.wait(timeout=5)
            return operation["call"](learner)
        finally:
            close_old_connections()

    def _concurrently(self, *operations):
        barrier = Barrier(len(operations))
        with ThreadPoolExecutor(max_workers=len(operations)) as executor:
            futures = [
                executor.submit(self._thread_call, barrier, operation)
                for operation in operations
            ]
        return [future.result() for future in futures]

    def test_simultaneous_creation_returns_one_active_session(self):
        def plan(learner):
            result = plan_study_session(learner=learner, new_word_target=2)
            return result.session.pk, result.created

        results = self._concurrently(
            {"call": plan, "learner_id": self.learner.pk},
            {"call": plan, "learner_id": self.learner.pk},
        )

        self.assertEqual({session_id for session_id, _ in results}, {results[0][0]})
        self.assertCountEqual([created for _, created in results], [True, False])
        self.assertEqual(StudySession.objects.count(), 1)

    def test_simultaneous_exact_answer_replays_one_durable_outcome(self):
        session = plan_study_session(
            learner=self.learner,
            new_word_target=1,
        ).session
        item = session.items.get()
        request_id = uuid.uuid4()

        def answer(learner):
            result = record_recall_answer(
                learner=learner,
                session_id=session.pk,
                item_id=item.pk,
                request_id=request_id,
                rating="remembered",
            )
            return result.answer.pk, result.outcome.pk, result.created

        results = self._concurrently(
            {"call": answer, "learner_id": self.learner.pk},
            {"call": answer, "learner_id": self.learner.pk},
        )

        self.assertEqual({answer_id for answer_id, _, _ in results}, {results[0][0]})
        self.assertEqual({outcome_id for _, outcome_id, _ in results}, {results[0][1]})
        self.assertCountEqual([created for _, _, created in results], [True, False])
        self.assertEqual(RecallAnswer.objects.count(), 1)
        self.assertEqual(RecallOutcome.objects.count(), 1)
        self.assertEqual(LearnerWordState.objects.get().review_count, 1)

    def test_simultaneous_distinct_answers_accepts_one_and_conflicts_one(self):
        session = plan_study_session(
            learner=self.learner,
            new_word_target=1,
        ).session
        item = session.items.get()

        def operation(request_id, rating):
            def answer(learner):
                try:
                    result = record_recall_answer(
                        learner=learner,
                        session_id=session.pk,
                        item_id=item.pk,
                        request_id=request_id,
                        rating=rating,
                    )
                    return "accepted", result.answer.rating
                except StudyAnswerConflict as error:
                    return "conflict", error.code

            return {"call": answer, "learner_id": self.learner.pk}

        results = self._concurrently(
            operation(uuid.uuid4(), "remembered"),
            operation(uuid.uuid4(), "forgot"),
        )

        self.assertEqual([status for status, _ in results].count("accepted"), 1)
        self.assertEqual([status for status, _ in results].count("conflict"), 1)
        conflict = next(value for status, value in results if status == "conflict")
        self.assertEqual(conflict, "study_session_inactive")
        self.assertEqual(RecallAnswer.objects.count(), 1)
        self.assertEqual(RecallOutcome.objects.count(), 1)
        self.assertEqual(LearnerWordState.objects.get().review_count, 1)
