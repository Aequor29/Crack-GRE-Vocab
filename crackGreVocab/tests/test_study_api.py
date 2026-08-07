"""Authenticated Study Session creation and resume API coverage."""

import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .study_helpers import create_corpus, create_learner


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CORS_ALLOWED_ORIGINS=("http://127.0.0.1:3000",),
    CSRF_TRUSTED_ORIGINS=("http://127.0.0.1:3000",),
)
class StudySessionApiTests(TestCase):
    origin = "http://127.0.0.1:3000"

    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(("abate", "lucid"))
        self.client = Client(enforce_csrf_checks=True)

    def csrf_token(self) -> str:
        response = self.client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN=self.origin,
        )
        return response.json()["csrf_token"]

    def post_session(self, target: int):
        return self.client.post(
            reverse("study:session-list"),
            data=json.dumps({"new_word_target": target}),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def test_authenticated_creation_and_later_reads_return_stable_plan(self):
        self.client.force_login(self.learner)

        created = self.post_session(2)
        resumed = self.post_session(1)
        active = self.client.get(reverse("study:active-session"))

        self.assertEqual(created.status_code, 201)
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(active.status_code, 200)
        self.assertEqual(created.json(), resumed.json())
        self.assertEqual(created.json(), active.json())
        self.assertEqual(created.json()["corpus_version"], self.corpus.version)
        self.assertEqual(
            [item["term"] for item in created.json()["items"]],
            ["abate", "lucid"],
        )
        self.assertEqual(
            created.json()["items"][0]["senses"][0]["definition"],
            "Definition for abate.",
        )

    def test_auth_csrf_validation_and_empty_plan_fail_safely(self):
        anonymous = self.post_session(1)
        self.assertEqual(anonymous.status_code, 403)

        self.client.force_login(self.learner)
        missing_csrf = self.client.post(
            reverse("study:session-list"),
            data=json.dumps({"new_word_target": 1}),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
        )
        invalid_target = self.post_session(21)
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(invalid_target.status_code, 400)

        self.assertEqual(
            self.client.get(reverse("study:active-session")).status_code,
            404,
        )
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        unavailable = self.post_session(1)
        self.assertEqual(unavailable.status_code, 409)
        self.assertEqual(
            unavailable.json(),
            {"detail": "No active vocabulary corpus is available."},
        )
