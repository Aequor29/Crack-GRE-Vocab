"""Authenticated Study Session creation and resume API coverage."""

import json
from datetime import UTC, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.db import IntegrityError, OperationalError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from study.models import LearnerWordState, SchedulingPhase

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

    def post_session(self, target: int, *, timezone_name: str = "America/Chicago"):
        return self.client.post(
            reverse("study:session-list"),
            data=json.dumps(
                {
                    "new_word_target": target,
                    "timezone": timezone_name,
                }
            ),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def test_creation_reports_fixed_daily_word_progress(self):
        self.client.force_login(self.learner)

        created = self.post_session(2)

        self.assertEqual(created.status_code, 201)
        document = created.json()
        cutoff = datetime.fromisoformat(document["day_ends_at"])
        local_cutoff = cutoff.astimezone(ZoneInfo("America/Chicago"))
        self.assertEqual(document["timezone"], "America/Chicago")
        self.assertEqual((local_cutoff.hour, local_cutoff.minute), (0, 0))
        self.assertGreater(cutoff, datetime.fromisoformat(document["created_at"]))
        self.assertEqual(document["queue_state"], "ready")
        self.assertEqual(document["word_count"], 2)
        self.assertEqual(document["cleared_word_count"], 0)
        self.assertEqual(document["remaining_word_count"], 2)
        self.assertIsNotNone(document["current_item"])
        self.assertNotIn("items", document)

    def test_creation_includes_review_work_due_later_today(self):
        self.client.force_login(self.learner)
        now = timezone.now()
        utc_day_end = datetime.combine(
            now.astimezone(UTC).date() + timedelta(days=1),
            time.min,
            UTC,
        )
        due_later_today = now + (utc_day_end - now) / 2
        LearnerWordState.objects.create(
            learner=self.learner,
            word=self.entries[0].word,
            phase=SchedulingPhase.REVIEW,
            review_count=2,
            last_reviewed_at=now - timedelta(days=1),
            next_due_at=due_later_today,
            scheduler_version="test-scheduler-v1",
            scheduler_state={"source": "daily-queue-test"},
        )

        created = self.post_session(0, timezone_name="UTC")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["word_count"], 1)
        self.assertEqual(created.json()["current_item"]["term"], "abate")
        self.assertEqual(created.json()["current_item"]["kind"], "due")

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
        term = created.json()["current_item"]["term"]
        self.assertIn(term, ("abate", "lucid"))
        self.assertEqual(
            created.json()["current_item"]["senses"][0]["definition"],
            f"Definition for {term}.",
        )

    def test_auth_csrf_validation_and_empty_plan_fail_safely(self):
        anonymous = self.post_session(1)
        self.assertEqual(anonymous.status_code, 403)
        self.assertEqual(anonymous.json()["code"], "authentication_required")

        self.client.force_login(self.learner)
        missing_csrf = self.client.post(
            reverse("study:session-list"),
            data=json.dumps({"new_word_target": 1}),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
        )
        invalid_target = self.post_session(21)
        invalid_timezone = self.post_session(1, timezone_name="Mars/Olympus")
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["code"], "csrf_failed")
        self.assertEqual(invalid_target.status_code, 400)
        self.assertEqual(invalid_target.json()["code"], "validation_error")
        self.assertEqual(invalid_timezone.status_code, 400)
        self.assertEqual(invalid_timezone.json()["code"], "validation_error")
        self.assertIn("timezone", invalid_timezone.json())

        missing_session = self.client.get(reverse("study:active-session"))
        self.assertEqual(missing_session.status_code, 404)
        self.assertEqual(missing_session.json()["code"], "study_session_not_found")
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        unavailable = self.post_session(1)
        self.assertEqual(unavailable.status_code, 409)
        self.assertEqual(
            unavailable.json(),
            {
                "code": "study_corpus_unavailable",
                "detail": "No active vocabulary corpus is available.",
            },
        )

    def test_only_transient_database_failures_are_retryable(self):
        self.client.force_login(self.learner)
        with patch(
            "study.views.plan_study_session",
            side_effect=OperationalError("connection interrupted"),
        ):
            retryable = self.post_session(1)

        self.assertEqual(retryable.status_code, 503)
        self.assertEqual(
            retryable.json(),
            {
                "code": "study_temporarily_unavailable",
                "detail": "The Study Session could not be persisted.",
                "retryable": True,
            },
        )

        with patch(
            "study.views.resume_active_study_session",
            side_effect=OperationalError("connection interrupted"),
        ):
            restore_retryable = self.client.get(reverse("study:active-session"))
        self.assertEqual(restore_retryable.status_code, 503)
        self.assertEqual(
            restore_retryable.json(),
            {
                "code": "study_temporarily_unavailable",
                "detail": "The Study Session could not be loaded.",
                "retryable": True,
            },
        )

        with (
            patch(
                "study.views.plan_study_session",
                side_effect=IntegrityError("unexpected invariant failure"),
            ),
            self.assertRaises(IntegrityError),
        ):
            self.post_session(1)
