"""Durable learner scheduling, Study Session, and Recall Outcome models."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from vocabulary.models import CorpusEntry, CorpusVersion, VocabularyWord


class SchedulingPhase(models.TextChoices):
    LEARNING = "learning", "Learning"
    REVIEW = "review", "Review"
    RELEARNING = "relearning", "Relearning"


class LearnerWordState(models.Model):
    """The current backend-owned scheduling state for one learner and Word."""

    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="word_states",
    )
    word = models.ForeignKey(
        VocabularyWord,
        on_delete=models.PROTECT,
        related_name="learner_states",
    )
    phase = models.CharField(max_length=16, choices=SchedulingPhase.choices)
    review_count = models.PositiveIntegerField()
    lapse_count = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField()
    next_due_at = models.DateTimeField()
    scheduler_version = models.CharField(max_length=64)
    scheduler_state = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("next_due_at", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("learner", "word"),
                name="study_unique_learner_word_state",
            ),
            models.CheckConstraint(
                condition=Q(review_count__gte=1),
                name="study_word_state_review_count_positive",
            ),
            models.CheckConstraint(
                condition=Q(lapse_count__lte=F("review_count")),
                name="study_word_state_lapses_not_above_reviews",
            ),
            models.CheckConstraint(
                condition=Q(next_due_at__gt=F("last_reviewed_at")),
                name="study_word_state_due_after_review",
            ),
            models.CheckConstraint(
                condition=~Q(scheduler_version=""),
                name="study_word_state_scheduler_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(phase__in=SchedulingPhase.values),
                name="study_word_state_phase_valid",
            ),
        )
        indexes = (
            models.Index(
                fields=("learner", "next_due_at"),
                name="study_state_learner_due_idx",
            ),
            models.Index(
                fields=("learner", "phase"),
                name="study_state_learner_phase_idx",
            ),
        )

    def __str__(self) -> str:
        return f"{self.learner_id}: {self.word.term} ({self.phase})"


class StudySession(models.Model):
    """One bounded, resumable, backend-planned study sitting."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_sessions",
    )
    corpus = models.ForeignKey(
        CorpusVersion,
        on_delete=models.PROTECT,
        related_name="study_sessions",
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    new_word_target = models.PositiveSmallIntegerField()
    planner_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("learner",),
                condition=Q(status="active"),
                name="study_one_active_session_per_learner",
            ),
            models.CheckConstraint(
                condition=~Q(planner_version=""),
                name="study_session_planner_not_empty",
            ),
            models.CheckConstraint(
                condition=(Q(status="active") & Q(ended_at__isnull=True))
                | (
                    Q(status__in=("completed", "abandoned")) & Q(ended_at__isnull=False)
                ),
                name="study_session_status_end_consistent",
            ),
        )
        indexes = (
            models.Index(
                fields=("learner", "status", "-created_at"),
                name="study_session_status_idx",
            ),
        )

    def __str__(self) -> str:
        return f"{self.learner_id}: {self.id} ({self.status})"

    def close(self, status: str, *, at=None) -> None:
        """Close an active session without discarding accepted history."""
        if status not in {self.Status.COMPLETED, self.Status.ABANDONED}:
            raise ValueError(
                "A Study Session can only close as completed or abandoned."
            )
        if self.status != self.Status.ACTIVE:
            raise ValueError("Only an active Study Session can be closed.")
        self.status = status
        self.ended_at = at or timezone.now()


class StudySessionItem(models.Model):
    """One server-ordered question selected for a Study Session."""

    class Kind(models.TextChoices):
        DUE = "due", "Due review"
        NEW = "new", "New Word"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        StudySession,
        on_delete=models.CASCADE,
        related_name="items",
    )
    corpus_entry = models.ForeignKey(
        CorpusEntry,
        on_delete=models.PROTECT,
        related_name="study_items",
    )
    position = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=Kind.choices)
    due_at_snapshot = models.DateTimeField(null=True, blank=True)
    scheduler_version = models.CharField(max_length=64, blank=True)
    scheduling_state_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("position",)
        constraints = (
            models.UniqueConstraint(
                fields=("session", "position"),
                name="study_unique_session_item_position",
            ),
            models.UniqueConstraint(
                fields=("session", "corpus_entry"),
                name="study_unique_session_corpus_entry",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="study_session_item_position_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind="due")
                    & Q(due_at_snapshot__isnull=False)
                    & ~Q(scheduler_version="")
                )
                | (
                    Q(kind="new")
                    & Q(due_at_snapshot__isnull=True)
                    & Q(scheduler_version="")
                ),
                name="study_session_item_kind_snapshot_valid",
            ),
        )

    def __str__(self) -> str:
        return f"{self.session_id} item {self.position}: {self.corpus_entry.term}"


class RecallAnswer(models.Model):
    """The learner's accepted self-grade for one session item."""

    class Rating(models.TextChoices):
        REMEMBERED = "remembered", "Remembered"
        FORGOT = "forgot", "Forgot"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.OneToOneField(
        StudySessionItem,
        on_delete=models.CASCADE,
        related_name="answer",
    )
    rating = models.CharField(max_length=16, choices=Rating.choices)
    client_request_id = models.UUIDField(unique=True)
    submitted_at = models.DateTimeField()
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("accepted_at",)
        constraints = (
            models.CheckConstraint(
                condition=Q(rating__in=("remembered", "forgot")),
                name="study_answer_rating_valid",
            ),
            models.CheckConstraint(
                condition=Q(accepted_at__gte=F("submitted_at")),
                name="study_answer_acceptance_order_valid",
            ),
        )

    def __str__(self) -> str:
        return f"{self.item_id}: {self.rating}"


class RecallOutcome(models.Model):
    """One immutable scheduler transition resulting from an accepted answer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer = models.OneToOneField(
        RecallAnswer,
        on_delete=models.CASCADE,
        related_name="outcome",
    )
    review_number = models.PositiveIntegerField()
    scheduler_version = models.CharField(max_length=64)
    previous_phase = models.CharField(
        max_length=16,
        choices=SchedulingPhase.choices,
        blank=True,
    )
    next_phase = models.CharField(max_length=16, choices=SchedulingPhase.choices)
    previous_due_at = models.DateTimeField(null=True, blank=True)
    next_due_at = models.DateTimeField()
    previous_state = models.JSONField(default=dict)
    next_state = models.JSONField()
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")
        constraints = (
            models.CheckConstraint(
                condition=Q(review_number__gte=1),
                name="study_outcome_review_number_positive",
            ),
            models.CheckConstraint(
                condition=~Q(scheduler_version=""),
                name="study_outcome_scheduler_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(previous_phase="")
                | Q(previous_phase__in=SchedulingPhase.values),
                name="study_outcome_previous_phase_valid",
            ),
            models.CheckConstraint(
                condition=Q(next_phase__in=SchedulingPhase.values),
                name="study_outcome_next_phase_valid",
            ),
            models.CheckConstraint(
                condition=(Q(previous_phase="") & Q(previous_due_at__isnull=True))
                | (~Q(previous_phase="") & Q(previous_due_at__isnull=False)),
                name="study_outcome_previous_state_consistent",
            ),
            models.CheckConstraint(
                condition=~Q(next_state={}),
                name="study_outcome_next_state_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(next_due_at__gt=F("occurred_at")),
                name="study_outcome_next_due_after_occurrence",
            ),
        )
        indexes = (
            models.Index(
                fields=("occurred_at",),
                name="study_outcome_occurred_idx",
            ),
        )

    def __str__(self) -> str:
        return f"{self.answer_id}: review {self.review_number}"
