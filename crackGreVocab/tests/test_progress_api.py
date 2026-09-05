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
    StudySessionWord,
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
                    "reviewing": 0,
                    "mastered": 0,
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

    def test_summary_separates_mastered_words_from_words_still_reviewing(self):
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))
        corpus, entries = create_corpus(
            ("ephemeral", "laconic", "mendacious", "obdurate"),
            version="mastery-test-v1",
        )
        observed_at = datetime(2026, 8, 29, 18, tzinfo=UTC)
        states = (
            ("review", 3, timedelta(days=30)),
            ("review", 2, timedelta(days=30)),
            ("review", 3, timedelta(days=29)),
            ("relearning", 3, timedelta(days=30)),
        )
        for entry, (phase, review_count, interval) in zip(
            entries,
            states,
            strict=True,
        ):
            last_reviewed_at = observed_at - timedelta(days=1)
            LearnerWordState.objects.create(
                learner=self.learner,
                word=entry.word,
                phase=phase,
                review_count=review_count,
                last_reviewed_at=last_reviewed_at,
                next_due_at=last_reviewed_at + interval,
                scheduler_version="test-scheduler",
                scheduler_state={"step": 1},
            )

        self.client.force_login(self.learner)
        with patch("progress.services.current_time", return_value=observed_at):
            response = self.client.get(
                reverse("progress:summary"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["corpus"],
            {
                "version": corpus.version,
                "total": 4,
                "unseen": 0,
                "learning": 1,
                "reviewing": 2,
                "mastered": 1,
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
            session_word = StudySessionWord.objects.create(
                session=session,
                corpus_entry=entry,
                position=position,
                kind=StudySessionWord.Kind.NEW,
                ready_at=occurred_at,
                cleared_at=occurred_at,
            )
            item = StudySessionItem.objects.create(
                session=session,
                session_word=session_word,
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
                "reviewing": 1,
                "mastered": 0,
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


@override_settings(SECURE_SSL_REDIRECT=False)
class LearningInsightsApiTests(TestCase):
    def setUp(self) -> None:
        self.learner = create_learner()
        self.corpus, self.entries = create_corpus(("abate", "lucid"))
        self.client = Client()
        self.client.force_login(self.learner)

    def create_outcome(
        self,
        *,
        occurred_at: datetime,
        rating: str,
        previous_phase: str,
        next_phase: str = "review",
        entry_index: int = 0,
        review_number: int | None = None,
        next_interval: timedelta = timedelta(days=1),
    ) -> None:
        is_initial_learning = previous_phase == ""
        session = StudySession.objects.create(
            learner=self.learner,
            corpus=self.corpus,
            status=StudySession.Status.COMPLETED,
            new_word_target=0,
            planner_version="test-planner",
            ended_at=occurred_at,
        )
        item_kind = (
            StudySessionItem.Kind.NEW
            if is_initial_learning
            else StudySessionItem.Kind.DUE
        )
        session_word = StudySessionWord.objects.create(
            session=session,
            corpus_entry=self.entries[entry_index],
            position=1,
            kind=item_kind,
            ready_at=occurred_at,
            cleared_at=occurred_at,
        )
        item = StudySessionItem.objects.create(
            session=session,
            session_word=session_word,
            corpus_entry=self.entries[entry_index],
            position=1,
            kind=item_kind,
            due_at_snapshot=(
                None if is_initial_learning else occurred_at - timedelta(days=1)
            ),
            scheduler_version="" if is_initial_learning else "test-scheduler",
            scheduling_state_snapshot={} if is_initial_learning else {"step": 1},
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
            review_number=review_number or (1 if is_initial_learning else 2),
            scheduler_version="test-scheduler",
            previous_phase=previous_phase,
            next_phase=next_phase,
            previous_due_at=(
                None if is_initial_learning else occurred_at - timedelta(days=1)
            ),
            next_due_at=occurred_at + next_interval,
            previous_state={} if is_initial_learning else {"step": 1},
            next_state={"step": 2},
            occurred_at=occurred_at,
        )

    def test_review_recall_compares_local_7_day_periods_and_excludes_learning(self):
        observed_at = datetime(2026, 8, 29, 18, tzinfo=UTC)
        for occurred_at, rating, previous_phase in (
            (
                datetime(2026, 8, 28, 18, tzinfo=UTC),
                "remembered",
                "review",
            ),
            (
                datetime(2026, 8, 25, 18, tzinfo=UTC),
                "forgot",
                "review",
            ),
            (
                datetime(2026, 8, 24, 18, tzinfo=UTC),
                "remembered",
                "learning",
            ),
            (
                datetime(2026, 8, 20, 18, tzinfo=UTC),
                "remembered",
                "review",
            ),
            (
                datetime(2026, 8, 18, 18, tzinfo=UTC),
                "forgot",
                "review",
            ),
        ):
            self.create_outcome(
                occurred_at=occurred_at,
                rating=rating,
                previous_phase=previous_phase,
            )

        with patch("progress.services.current_time", return_value=observed_at):
            response = self.client.get(
                reverse("progress:insights"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["review_recall"],
            {
                "current": {
                    "starts_on": "2026-08-23",
                    "ends_on": "2026-08-29",
                    "remembered": 1,
                    "answers": 2,
                    "rate_percent": 50,
                    "has_sufficient_data": False,
                },
                "previous": {
                    "starts_on": "2026-08-16",
                    "ends_on": "2026-08-22",
                    "remembered": 1,
                    "answers": 2,
                    "rate_percent": 50,
                    "has_sufficient_data": False,
                },
                "change_percentage_points": None,
            },
        )

    def test_review_recall_shows_a_bounded_period_comparison_with_enough_data(self):
        observed_at = datetime(2026, 8, 29, 18, tzinfo=UTC)
        for index in range(10):
            self.create_outcome(
                occurred_at=datetime(2026, 8, 26, 18, index, tzinfo=UTC),
                rating="remembered" if index < 8 else "forgot",
                previous_phase="review",
            )
            self.create_outcome(
                occurred_at=datetime(2026, 8, 20, 18, index, tzinfo=UTC),
                rating="remembered" if index < 6 else "forgot",
                previous_phase="review",
            )

        with (
            patch("progress.services.current_time", return_value=observed_at),
            CaptureQueriesContext(connection) as queries,
        ):
            response = self.client.get(
                reverse("progress:insights"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 10)
        recall = response.json()["review_recall"]
        self.assertEqual(recall["current"]["rate_percent"], 80)
        self.assertTrue(recall["current"]["has_sufficient_data"])
        self.assertEqual(recall["previous"]["rate_percent"], 60)
        self.assertTrue(recall["previous"]["has_sufficient_data"])
        self.assertEqual(recall["change_percentage_points"], 20)

    def test_study_days_and_current_streak_use_local_dates_across_dst(self):
        observed_at = datetime(2026, 11, 2, 18, tzinfo=UTC)
        for occurred_at in (
            datetime(2026, 11, 1, 4, 30, tzinfo=UTC),
            datetime(2026, 11, 1, 7, 30, tzinfo=UTC),
            datetime(2026, 11, 1, 8, 30, tzinfo=UTC),
        ):
            self.create_outcome(
                occurred_at=occurred_at,
                rating="remembered",
                previous_phase="review",
            )

        with patch("progress.services.current_time", return_value=observed_at):
            response = self.client.get(
                reverse("progress:insights"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["consistency"],
            {
                "calendar_starts_on": "2026-08-17",
                "calendar_ends_on": "2026-11-02",
                "current_streak_days": 2,
                "study_days": [
                    {
                        "date": "2026-10-31",
                        "answers": 1,
                        "words_practiced": 1,
                    },
                    {
                        "date": "2026-11-01",
                        "answers": 2,
                        "words_practiced": 1,
                    },
                ],
            },
        )

    def test_learning_curve_reports_weekly_corpus_phase_snapshots(self):
        observed_at = datetime(2026, 11, 2, 18, tzinfo=UTC)
        for (
            occurred_at,
            previous_phase,
            next_phase,
            entry_index,
            review_number,
            next_interval,
        ) in (
            (
                datetime(2026, 8, 18, 18, tzinfo=UTC),
                "",
                "learning",
                0,
                1,
                timedelta(minutes=10),
            ),
            (
                datetime(2026, 8, 24, 18, tzinfo=UTC),
                "learning",
                "review",
                0,
                2,
                timedelta(days=1),
            ),
            (
                datetime(2026, 10, 31, 17, tzinfo=UTC),
                "review",
                "review",
                0,
                3,
                timedelta(days=30),
            ),
            (
                datetime(2026, 10, 31, 18, tzinfo=UTC),
                "",
                "learning",
                1,
                1,
                timedelta(minutes=10),
            ),
        ):
            self.create_outcome(
                occurred_at=occurred_at,
                rating="remembered",
                previous_phase=previous_phase,
                next_phase=next_phase,
                entry_index=entry_index,
                review_number=review_number,
                next_interval=next_interval,
            )

        with patch("progress.services.current_time", return_value=observed_at):
            response = self.client.get(
                reverse("progress:insights"),
                {"timezone": "America/Chicago"},
            )

        self.assertEqual(response.status_code, 200)
        curve_by_week = {
            point["starts_on"]: point for point in response.json()["learning_curve"]
        }
        self.assertEqual(len(curve_by_week), 12)
        self.assertEqual(
            curve_by_week["2026-08-17"],
            {
                "starts_on": "2026-08-17",
                "ends_on": "2026-08-23",
                "unseen": 1,
                "learning": 1,
                "reviewing": 0,
                "mastered": 0,
            },
        )

        self.assertEqual(
            curve_by_week["2026-08-24"],
            {
                "starts_on": "2026-08-24",
                "ends_on": "2026-08-30",
                "unseen": 1,
                "learning": 0,
                "reviewing": 1,
                "mastered": 0,
            },
        )
        self.assertEqual(
            curve_by_week["2026-11-02"],
            {
                "starts_on": "2026-11-02",
                "ends_on": "2026-11-02",
                "unseen": 0,
                "learning": 1,
                "reviewing": 0,
                "mastered": 1,
            },
        )

    def test_insights_report_when_the_active_corpus_is_unavailable(self):
        self.corpus.is_active = False
        self.corpus.save(update_fields=("is_active",))

        response = self.client.get(
            reverse("progress:insights"),
            {"timezone": "America/Chicago"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "progress_corpus_unavailable")
