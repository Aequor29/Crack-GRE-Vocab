"""Stable learner deck behavior through Study selection and planning."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from django.test import SimpleTestCase, TestCase
from study.models import StudySession
from study.new_words import select_new_word_ids
from study.selectors import select_unseen_corpus_entries
from study.services import plan_study_session, record_recall_answer
from vocabulary.models import VocabularyWord

from .study_helpers import create_corpus, create_learner


class StableLearnerDeckTests(TestCase):
    def setUp(self):
        self.learner = create_learner()
        self.other = create_learner(email="other@example.com")
        terms = tuple(f"word-{index:02d}" for index in range(1, 17))
        words = {
            term: VocabularyWord.objects.create(
                id=UUID(int=index), term=term, normalized_term=term
            )
            for index, term in enumerate(terms, start=1)
        }
        self.corpus, self.entries = create_corpus(terms, words_by_term=words)

    def selected_ids(self, learner, limit):
        return tuple(
            entry.word_id
            for entry in select_unseen_corpus_entries(
                learner=learner, corpus=self.corpus, limit=limit
            )
        )

    def test_learners_get_distinct_stable_decks_independent_of_corpus_position(self):
        deck = self.selected_ids(self.learner, 16)
        self.assertNotEqual(deck, tuple(entry.word_id for entry in self.entries))
        self.assertNotEqual(deck, self.selected_ids(self.other, 16))
        self.assertEqual(deck, self.selected_ids(self.learner, 16))
        self.assertEqual(deck[:5], self.selected_ids(self.learner, 5))
        session = plan_study_session(learner=self.learner, new_word_target=5).session
        self.assertEqual(session.current_item.corpus_entry.word_id, deck[0])
        self.assertEqual(
            tuple(word.corpus_entry.word_id for word in session.session_words.all()),
            deck[:5],
        )

    def test_answers_remove_only_seen_words_and_abandon_keeps_the_remaining_order(self):
        deck = self.selected_ids(self.learner, 16)
        now = datetime(2026, 9, 1, 12, tzinfo=UTC)
        session = plan_study_session(
            learner=self.learner, new_word_target=5, planned_at=now
        ).session
        answered = record_recall_answer(
            learner=self.learner,
            session_id=session.pk,
            item_id=session.current_item_id,
            request_id=uuid4(),
            rating="remembered",
            occurred_at=now,
        )
        self.assertEqual(answered.session.current_item.corpus_entry.word_id, deck[1])
        session.close(StudySession.Status.ABANDONED, at=now)
        session.save(update_fields=("status", "ended_at", "updated_at"))
        self.assertEqual(self.selected_ids(self.learner, 16), deck[1:])
        later = plan_study_session(
            learner=self.learner,
            new_word_target=3,
            planned_at=now + timedelta(minutes=1),
        ).session
        self.assertEqual(
            tuple(
                w.corpus_entry.word_id for w in later.session_words.filter(kind="new")
            ),
            deck[1:4],
        )

    def test_existing_session_keeps_its_policy_and_positions_on_resume(self):
        session = plan_study_session(learner=self.learner, new_word_target=5).session
        # Model a queue persisted by a previous planner, with its own order.
        session.planner_version = "m1-daily-queue-v1"
        session.save(update_fields=("planner_version",))
        before = tuple(session.session_words.values_list("corpus_entry_id", flat=True))
        current = session.current_item_id
        resumed = plan_study_session(learner=self.learner, new_word_target=20)
        self.assertFalse(resumed.created)
        self.assertEqual(resumed.session.pk, session.pk)
        self.assertEqual(resumed.session.planner_version, "m1-daily-queue-v1")
        self.assertEqual(resumed.session.current_item_id, current)
        self.assertEqual(
            tuple(
                resumed.session.session_words.values_list("corpus_entry_id", flat=True)
            ),
            before,
        )

    def test_selection_respects_zero_target_scarcity_and_corpus_membership(self):
        self.assertEqual(self.selected_ids(self.learner, 0), ())
        self.assertEqual(len(self.selected_ids(self.learner, 20)), 16)
        other_corpus, _ = create_corpus(("other",), version="other", is_active=False)
        selected = select_unseen_corpus_entries(
            learner=self.learner, corpus=other_corpus, limit=20
        )
        self.assertEqual([entry.term for entry in selected], ["other"])


class NewWordRankingTests(SimpleTestCase):
    def select(
        self,
        word_ids,
        *,
        corpus_version="m1-v2",
        planner_version="m1-daily-queue-stable-deck-v2",
        limit=5,
    ):
        return select_new_word_ids(
            word_ids,
            learner_id=42,
            corpus_version=corpus_version,
            planner_version=planner_version,
            limit=limit,
        )

    def test_ranking_is_input_order_independent_and_scoped_to_policy_and_corpus(self):
        words = tuple(UUID(int=index) for index in range(1, 17))
        deck = self.select(iter(words))
        self.assertEqual(deck, self.select(reversed(words)))
        self.assertNotEqual(deck, self.select(words, corpus_version="m1-v3"))
        self.assertNotEqual(deck, self.select(words, planner_version="future-policy"))
        self.assertEqual(self.select(words, limit=0), ())
        self.assertEqual(self.select(()), ())
        self.assertEqual(self.select(words, limit=1), deck[:1])

    def test_ranking_is_stable_across_process_hash_seeds(self):
        script = (
            "from uuid import UUID; from study.new_words import select_new_word_ids; "
            "print([w.int for w in select_new_word_ids("
            "(UUID(int=i) for i in range(1,17)), learner_id=42, "
            "corpus_version='m1-v2', planner_version='m1-daily-queue-stable-deck-v2', "
            "limit=5)])"
        )
        results = [
            subprocess.check_output(
                [sys.executable, "-c", script],
                env={**os.environ, "PYTHONHASHSEED": seed},
                text=True,
                timeout=10,
            )
            for seed in ("1", "98765")
        ]
        self.assertEqual(results[0], results[1])
