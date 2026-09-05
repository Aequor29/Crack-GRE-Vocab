"""Authenticated Recall Answer API integration coverage."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from study.models import LearnerWordState, RecallAnswer, RecallOutcome
from study.services import StudyStateInvariantError, plan_study_session

from .study_helpers import create_corpus, create_learner


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CORS_ALLOWED_ORIGINS=("http://127.0.0.1:3000",),
    CSRF_TRUSTED_ORIGINS=("http://127.0.0.1:3000",),
)
class RecallAnswerApiTests(TestCase):
    origin = "http://127.0.0.1:3000"

    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(("abate", "lucid"))
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.learner)

    def csrf_token(self) -> str:
        response = self.client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN=self.origin,
        )
        return response.json()["csrf_token"]

    def post_answer(self, session, item, payload, *, csrf: bool = True):
        headers = {
            "HTTP_ORIGIN": self.origin,
        }
        if csrf:
            headers["HTTP_X_CSRFTOKEN"] = self.csrf_token()
        return self.client.post(
            reverse(
                "study:session-answer",
                kwargs={"session_id": session.pk, "item_id": item.pk},
            ),
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def test_session_completes_only_after_the_word_is_cleared_for_today(self):
        started_at = datetime(2026, 8, 30, 15, tzinfo=UTC)
        session = plan_study_session(
            learner=self.learner,
            new_word_target=1,
            timezone_name="America/Chicago",
            planned_at=started_at,
        ).session
        item = session.items.get()
        first_payload = {
            "client_request_id": str(uuid.uuid4()),
            "rating": "remembered",
        }

        with patch("study.services.timezone.now", return_value=started_at):
            first = self.post_answer(session, item, first_payload)
        next_due_at = LearnerWordState.objects.get().next_due_at
        with patch("study.services.timezone.now", return_value=next_due_at):
            resumed = self.client.get(reverse("study:active-session"))
            repeat_item_id = resumed.json()["current_item"]["id"]
            final_payload = {
                "client_request_id": str(uuid.uuid4()),
                "rating": "remembered",
            }
            created = self.post_answer(
                session,
                SimpleNamespace(pk=repeat_item_id),
                final_payload,
            )
            replayed = self.post_answer(
                session,
                SimpleNamespace(pk=repeat_item_id),
                final_payload,
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["session"]["status"], "active")
        self.assertEqual(first.json()["session"]["cleared_word_count"], 0)
        self.assertEqual(first.json()["session"]["remaining_word_count"], 1)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(replayed.status_code, 200)
        self.assertFalse(created.json()["replayed"])
        self.assertTrue(replayed.json()["replayed"])
        self.assertEqual(
            created.json()["answer"]["id"],
            replayed.json()["answer"]["id"],
        )
        self.assertEqual(created.json()["session"]["status"], "completed")
        self.assertEqual(created.json()["session"]["cleared_word_count"], 1)
        self.assertEqual(created.json()["session"]["remaining_word_count"], 0)
        self.assertIsNone(created.json()["session"]["current_item"])
        self.assertEqual(RecallAnswer.objects.count(), 2)
        self.assertEqual(RecallOutcome.objects.count(), 2)

    def test_new_words_finish_the_first_round_then_repeat_without_waiting(self):
        started_at = datetime(2026, 8, 30, 15, tzinfo=UTC)
        session = plan_study_session(
            learner=self.learner,
            new_word_target=2,
            timezone_name="America/Chicago",
            planned_at=started_at,
        ).session
        first_item, second_item = session.items.all()

        with patch("study.services.timezone.now", return_value=started_at):
            first = self.post_answer(
                session,
                first_item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "remembered",
                },
            )
        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=1),
        ):
            second = self.post_answer(
                session,
                second_item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "remembered",
                },
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(
            first.json()["session"]["current_item"]["term"],
            second_item.corpus_entry.term,
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["session"]["status"], "active")
        self.assertEqual(second.json()["session"]["queue_state"], "ready")
        self.assertEqual(
            second.json()["session"]["current_item"]["word_id"],
            str(first_item.corpus_entry.word_id),
        )
        self.assertEqual(second.json()["session"]["word_count"], 2)
        self.assertEqual(second.json()["session"]["cleared_word_count"], 0)
        self.assertEqual(second.json()["session"]["remaining_word_count"], 2)
        self.assertGreater(
            second.json()["outcome"]["next_due_at"], "2026-08-30T15:01:00Z"
        )

    def test_issued_card_remains_current_as_scheduling_timers_elapse(self):
        started_at = datetime(2026, 8, 30, 15, tzinfo=UTC)
        session = plan_study_session(
            learner=self.learner,
            new_word_target=2,
            timezone_name="America/Chicago",
            planned_at=started_at,
        ).session
        first_item, second_item = session.items.all()

        with patch("study.services.timezone.now", return_value=started_at):
            self.post_answer(
                session,
                first_item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "remembered",
                },
            )
        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=1),
        ):
            self.post_answer(
                session,
                second_item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "forgot",
                },
            )

        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=2),
        ):
            resumed = self.client.get(reverse("study:active-session"))
        issued_item_id = resumed.json()["current_item"]["id"]
        self.assertEqual(
            resumed.json()["current_item"]["term"], first_item.corpus_entry.term
        )

        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=10),
        ):
            accepted = self.post_answer(
                session,
                SimpleNamespace(pk=issued_item_id),
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "remembered",
                },
            )

        self.assertEqual(accepted.status_code, 201)

    def test_forgotten_words_rotate_behind_the_other_unfinished_words(self):
        started_at = datetime(2026, 8, 30, 15, tzinfo=UTC)
        session = plan_study_session(
            learner=self.learner,
            new_word_target=2,
            timezone_name="America/Chicago",
            planned_at=started_at,
        ).session
        first_item, second_item = session.items.all()

        with patch("study.services.timezone.now", return_value=started_at):
            self.post_answer(
                session,
                first_item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "remembered",
                },
            )
        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=1),
        ):
            self.post_answer(
                session,
                second_item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "forgot",
                },
            )
        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=2),
        ):
            resumed = self.client.get(reverse("study:active-session"))
            first_repeat_id = resumed.json()["current_item"]["id"]
            self.assertEqual(
                resumed.json()["current_item"]["word_id"],
                str(first_item.corpus_entry.word_id),
            )
            self.post_answer(
                session,
                SimpleNamespace(pk=first_repeat_id),
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "forgot",
                },
            )

        with patch(
            "study.services.timezone.now",
            return_value=started_at + timedelta(minutes=10),
        ):
            fair_next = self.client.get(reverse("study:active-session"))

        self.assertEqual(
            fair_next.json()["current_item"]["term"], second_item.corpus_entry.term
        )

    def test_twenty_word_session_can_finish_in_one_continuous_sitting(self):
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        create_corpus(
            tuple(f"word-{index:02d}" for index in range(20)),
            version="continuous-session",
        )
        started_at = datetime(2026, 8, 30, 15, tzinfo=UTC)
        session = plan_study_session(
            learner=self.learner,
            new_word_target=20,
            timezone_name="America/Chicago",
            planned_at=started_at,
        ).session
        current = session.current_item
        presented = []
        for index in range(40):
            presented.append(str(current.corpus_entry.word_id))
            with patch(
                "study.services.timezone.now",
                return_value=started_at + timedelta(seconds=index + 1),
            ):
                response = self.post_answer(
                    session,
                    current,
                    {"client_request_id": str(uuid.uuid4()), "rating": "remembered"},
                )
            self.assertEqual(response.status_code, 201)
            progress = response.json()["session"]
            self.assertEqual(progress["word_count"], 20)
            self.assertEqual(progress["cleared_word_count"], max(0, index - 19))
            if index < 39:
                self.assertEqual(progress["status"], "active")
                self.assertIsNotNone(progress["current_item"])
                current = session.items.get(pk=progress["current_item"]["id"])
        self.assertEqual(len(set(presented[:20])), 20)
        self.assertEqual(presented[:20], presented[20:])
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["remaining_word_count"], 0)
        self.assertIsNone(progress["current_item"])

    def test_validation_csrf_order_and_ownership_fail_safely(self):
        session = plan_study_session(
            learner=self.learner,
            new_word_target=2,
        ).session
        first_item, second_item = session.items.all()
        request_id = str(uuid.uuid4())

        invalid = self.post_answer(
            session,
            first_item,
            {"client_request_id": request_id, "rating": "easy"},
        )
        missing_csrf = self.post_answer(
            session,
            first_item,
            {"client_request_id": request_id, "rating": "remembered"},
            csrf=False,
        )
        out_of_order = self.post_answer(
            session,
            second_item,
            {"client_request_id": request_id, "rating": "remembered"},
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["code"], "validation_error")
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["code"], "csrf_failed")
        self.assertEqual(out_of_order.status_code, 409)
        self.assertEqual(out_of_order.json()["code"], "study_item_out_of_order")
        self.assertEqual(
            out_of_order.json()["current_item_id"],
            str(first_item.pk),
        )
        self.assertFalse(RecallAnswer.objects.exists())

        other = create_learner(email="other@example.com")
        self.client.force_login(other)
        foreign = self.post_answer(
            session,
            first_item,
            {"client_request_id": str(uuid.uuid4()), "rating": "forgot"},
        )
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.json()["code"], "study_item_not_found")

    def test_state_invariant_defect_is_not_reported_as_retryable(self):
        session = plan_study_session(
            learner=self.learner,
            new_word_target=1,
        ).session
        item = session.items.get()
        now = timezone.now()
        LearnerWordState.objects.create(
            learner=self.learner,
            word=item.corpus_entry.word,
            phase="learning",
            review_count=1,
            last_reviewed_at=now,
            next_due_at=now + timedelta(minutes=10),
            scheduler_version="test-scheduler",
            scheduler_state={"card_id": item.corpus_entry.word_id.int},
        )

        with self.assertRaises(StudyStateInvariantError):
            self.post_answer(
                session,
                item,
                {
                    "client_request_id": str(uuid.uuid4()),
                    "rating": "remembered",
                },
            )

        self.assertFalse(RecallAnswer.objects.exists())
        self.assertFalse(RecallOutcome.objects.exists())
