"""Authenticated Recall Answer API integration coverage."""

import json
import uuid

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from study.models import RecallAnswer, RecallOutcome
from study.services import plan_study_session

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

    def test_first_acceptance_and_final_exact_replay_return_canonical_state(self):
        session = plan_study_session(
            learner=self.learner,
            new_word_target=1,
        ).session
        item = session.items.get()
        payload = {
            "client_request_id": str(uuid.uuid4()),
            "rating": "remembered",
        }

        created = self.post_answer(session, item, payload)
        replayed = self.post_answer(session, item, payload)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(replayed.status_code, 200)
        self.assertFalse(created.json()["replayed"])
        self.assertTrue(replayed.json()["replayed"])
        self.assertEqual(
            created.json()["answer"]["id"],
            replayed.json()["answer"]["id"],
        )
        self.assertEqual(created.json()["session"]["status"], "completed")
        self.assertEqual(created.json()["session"]["answered_count"], 1)
        self.assertEqual(created.json()["session"]["remaining_count"], 0)
        self.assertIsNone(created.json()["session"]["current_item"])
        self.assertEqual(RecallAnswer.objects.count(), 1)
        self.assertEqual(RecallOutcome.objects.count(), 1)

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
        self.assertEqual(missing_csrf.status_code, 403)
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
