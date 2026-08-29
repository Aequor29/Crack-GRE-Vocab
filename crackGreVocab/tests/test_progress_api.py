"""Authenticated Learning Progress API behavior."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.db import OperationalError, connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from study.models import (
    LearnerWordState,
    RecallAnswer,
    RecallOutcome,
    StudySession,
    StudySessionItem,
)

from .study_helpers import create_corpus, create_learner


@override_settings(SECURE_SSL_REDIRECT=False)
class LearningProgressApiTests(TestCase):
    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, _ = create_corpus(("abate", "lucid", "pragmatic"))
        self.client = Client()

    def test_new_learner_sees_the_active_corpus_as_unseen(self):
        self.client.force_login(self.learner)
        observed_at = datetime(
            2026,
            8,
            29,
            4,
            30,
            tzinfo=UTC,
        )

        with patch("progress.services.current_time", return_value=observed_at):
            response = self.client.get(
                reverse("progress:summary"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "corpus": {
                    "version": self.corpus.version,
                    "total": 3,
                    "unseen": 3,
                    "learning": 0,
                    "review": 0,
                },
                "actionable": {
                    "due_now": 0,
                    "due_today": 0,
                    "has_active_session": False,
                },
                "today": {
                    "date": "2026-08-28",
                    "timezone": "America/Chicago",
                    "sessions_started": 0,
                    "sessions_completed": 0,
                    "answers": 0,
                    "remembered": 0,
                    "forgot": 0,
                },
            },
        )

    def test_summary_uses_the_learners_dst_day_and_ignores_other_learners(self):
        self.client.force_login(self.learner)
        observed_at = datetime(
            2026,
            11,
            1,
            18,
            tzinfo=UTC,
        )
        entries = list(self.corpus.entries.select_related("word"))
        due_times = (
            observed_at - timedelta(hours=1),
            datetime(2026, 11, 2, 5, 30, tzinfo=UTC),
            datetime(2026, 11, 2, 6, 30, tzinfo=UTC),
        )
        for entry, phase, due_at in zip(
            entries,
            ("learning", "relearning", "review"),
            due_times,
            strict=True,
        ):
            LearnerWordState.objects.create(
                learner=self.learner,
                word=entry.word,
                phase=phase,
                review_count=1,
                last_reviewed_at=observed_at - timedelta(days=2),
                next_due_at=due_at,
                scheduler_version="test-scheduler",
                scheduler_state={"step": 1},
            )

        other_learner = create_learner(email="other@example.com")
        LearnerWordState.objects.create(
            learner=other_learner,
            word=entries[0].word,
            phase="review",
            review_count=1,
            last_reviewed_at=observed_at - timedelta(days=2),
            next_due_at=observed_at - timedelta(hours=2),
            scheduler_version="test-scheduler",
            scheduler_state={"step": 1},
        )

        session = StudySession.objects.create(
            learner=self.learner,
            corpus=self.corpus,
            status=StudySession.Status.COMPLETED,
            new_word_target=2,
            planner_version="test-planner",
            ended_at=observed_at - timedelta(hours=1),
        )
        StudySession.objects.filter(pk=session.pk).update(
            created_at=observed_at - timedelta(hours=2)
        )
        StudySession.objects.create(
            learner=self.learner,
            corpus=self.corpus,
            status=StudySession.Status.ACTIVE,
            new_word_target=1,
            planner_version="test-planner",
        )
        for position, (entry, rating) in enumerate(
            zip(entries[:2], ("remembered", "forgot"), strict=True),
            start=1,
        ):
            occurred_at = observed_at - timedelta(minutes=position)
            item = StudySessionItem.objects.create(
                session=session,
                corpus_entry=entry,
                position=position,
                kind=StudySessionItem.Kind.NEW,
            )
            answer = RecallAnswer.objects.create(
                item=item,
                rating=rating,
                client_request_id=uuid.uuid4(),
                submitted_at=datetime.now(UTC),
            )
            RecallAnswer.objects.filter(pk=answer.pk).update(
                submitted_at=occurred_at,
                accepted_at=occurred_at,
            )
            RecallOutcome.objects.create(
                answer=answer,
                review_number=1,
                scheduler_version="test-scheduler",
                previous_phase="",
                next_phase="learning",
                previous_due_at=None,
                next_due_at=occurred_at + timedelta(minutes=10),
                previous_state={},
                next_state={"step": 1},
                occurred_at=occurred_at,
            )

        self.client.force_login(self.learner)
        with (
            patch("progress.services.current_time", return_value=observed_at),
            CaptureQueriesContext(connection) as queries,
        ):
            response = self.client.get(
                reverse("progress:summary"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 10)
        payload = response.json()
        self.assertEqual(
            payload["corpus"],
            {
                "version": self.corpus.version,
                "total": 3,
                "unseen": 0,
                "learning": 2,
                "review": 1,
            },
        )
        self.assertEqual(
            payload["actionable"],
            {"due_now": 1, "due_today": 2, "has_active_session": True},
        )
        self.assertEqual(
            payload["today"],
            {
                "date": "2026-11-01",
                "timezone": "America/Chicago",
                "sessions_started": 1,
                "sessions_completed": 1,
                "answers": 2,
                "remembered": 1,
                "forgot": 1,
            },
        )
        self.assertNotIn("recent_outcomes", payload)

    def test_auth_timezone_corpus_and_transient_failures_have_stable_codes(self):
        anonymous = self.client.get(
            reverse("progress:summary"),
            {"timezone": "America/Chicago"},
        )
        self.assertEqual(anonymous.status_code, 403)
        self.assertEqual(anonymous.json()["code"], "authentication_required")

        self.client.force_login(self.learner)
        missing_timezone = self.client.get(reverse("progress:summary"))
        invalid_timezone = self.client.get(
            reverse("progress:summary"),
            {"timezone": "Chicago-ish"},
        )
        self.assertEqual(missing_timezone.status_code, 400)
        self.assertEqual(missing_timezone.json()["code"], "validation_error")
        self.assertEqual(invalid_timezone.status_code, 400)
        self.assertEqual(invalid_timezone.json()["code"], "validation_error")

        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        unavailable_corpus = self.client.get(
            reverse("progress:summary"),
            {"timezone": "America/Chicago"},
        )
        self.assertEqual(unavailable_corpus.status_code, 409)
        self.assertEqual(
            unavailable_corpus.json()["code"],
            "progress_corpus_unavailable",
        )

        with patch(
            "progress.views.build_learning_progress_summary",
            side_effect=OperationalError("connection interrupted"),
        ):
            transient = self.client.get(
                reverse("progress:summary"),
                {"timezone": "America/Chicago"},
            )
        self.assertEqual(transient.status_code, 503)
        self.assertEqual(
            transient.json(),
            {
                "code": "progress_temporarily_unavailable",
                "detail": "Learning Progress could not be loaded.",
                "retryable": True,
            },
        )
