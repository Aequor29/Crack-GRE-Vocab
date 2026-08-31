"""JSON contracts for backend-planned Study Sessions."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from vocabulary.models import VocabularySense

from .models import RecallAnswer, RecallOutcome, StudySession, StudySessionItem
from .policy import MAX_NEW_WORDS_PER_SESSION


class CreateStudySessionSerializer(serializers.Serializer):
    new_word_target = serializers.IntegerField(
        min_value=0,
        max_value=MAX_NEW_WORDS_PER_SESSION,
    )
    timezone = serializers.CharField(max_length=64)

    def validate_timezone(self, value: str) -> str:
        """Require a valid IANA timezone for the session's daily cutoff."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise serializers.ValidationError(
                "Enter a valid IANA timezone name."
            ) from exc
        return value


class RecordRecallAnswerSerializer(serializers.Serializer):
    client_request_id = serializers.UUIDField()
    rating = serializers.ChoiceField(choices=RecallAnswer.Rating.choices)


class StudySenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = VocabularySense
        fields = ("position", "part_of_speech", "definition", "example")


class StudySessionItemSerializer(serializers.ModelSerializer):
    word_id = serializers.UUIDField(source="corpus_entry.word_id", read_only=True)
    term = serializers.CharField(source="corpus_entry.term", read_only=True)
    pronunciation = serializers.CharField(
        source="corpus_entry.pronunciation",
        read_only=True,
    )
    senses = StudySenseSerializer(
        source="corpus_entry.senses",
        many=True,
        read_only=True,
    )

    class Meta:
        model = StudySessionItem
        fields = (
            "id",
            "position",
            "kind",
            "word_id",
            "term",
            "pronunciation",
            "senses",
        )


class StudySessionSerializer(serializers.ModelSerializer):
    corpus_version = serializers.CharField(source="corpus.version", read_only=True)
    timezone = serializers.CharField(source="timezone_name", read_only=True)
    day_ends_at = serializers.DateTimeField(read_only=True)
    planned_new_word_count = serializers.SerializerMethodField()
    word_count = serializers.SerializerMethodField()
    cleared_word_count = serializers.SerializerMethodField()
    remaining_word_count = serializers.SerializerMethodField()
    queue_state = serializers.SerializerMethodField()
    next_ready_at = serializers.SerializerMethodField()
    current_item = serializers.SerializerMethodField()

    def get_planned_new_word_count(self, session: StudySession) -> int:
        """Return how many assigned session Words introduce new material."""
        return session.planned_new_word_count_value

    def get_word_count(self, session: StudySession) -> int:
        """Return how many unique Words belong to the daily session."""
        return session.word_count_value

    def get_cleared_word_count(self, session: StudySession) -> int:
        """Return Words whose accepted outcome schedules them beyond today."""
        return session.cleared_word_count_value

    def get_remaining_word_count(self, session: StudySession) -> int:
        """Return unique session Words that are not yet cleared for today."""
        return self.get_word_count(session) - self.get_cleared_word_count(session)

    @extend_schema_field(
        serializers.ChoiceField(choices=("ready", "waiting", "completed", "abandoned"))
    )
    def get_queue_state(self, session: StudySession) -> str:
        """Return the learner-visible availability state of the session queue."""
        if session.status != StudySession.Status.ACTIVE:
            return session.status
        return "ready" if session.current_item_id is not None else "waiting"

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_next_ready_at(self, session: StudySession) -> datetime | None:
        """Return the next unfinished Word readiness time while waiting."""
        if self.get_queue_state(session) != "waiting":
            return None
        return session.next_ready_at_value

    @extend_schema_field(StudySessionItemSerializer(allow_null=True))
    def get_current_item(self, session: StudySession) -> dict[str, object] | None:
        """Serialize the durable presentation attempt issued by the backend."""
        if session.current_item is None:
            return None
        return StudySessionItemSerializer(session.current_item).data

    class Meta:
        model = StudySession
        fields = (
            "id",
            "status",
            "queue_state",
            "corpus_version",
            "timezone",
            "day_ends_at",
            "new_word_target",
            "planned_new_word_count",
            "word_count",
            "planner_version",
            "created_at",
            "ended_at",
            "cleared_word_count",
            "remaining_word_count",
            "next_ready_at",
            "current_item",
        )


class RecallAnswerSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = RecallAnswer
        fields = (
            "id",
            "item_id",
            "client_request_id",
            "rating",
            "submitted_at",
            "accepted_at",
        )


class RecallOutcomeSerializer(serializers.ModelSerializer):
    previous_phase = serializers.CharField(allow_blank=True, read_only=True)
    next_phase = serializers.CharField(read_only=True)

    class Meta:
        model = RecallOutcome
        fields = (
            "id",
            "review_number",
            "scheduler_version",
            "previous_phase",
            "next_phase",
            "previous_due_at",
            "next_due_at",
            "occurred_at",
        )


class StudyAnswerResponseSerializer(serializers.Serializer):
    answer = RecallAnswerSerializer()
    outcome = RecallOutcomeSerializer()
    session = StudySessionSerializer()
    replayed = serializers.BooleanField()


class StudyPlanningErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    current_item_id = serializers.UUIDField(required=False)
    retryable = serializers.BooleanField(required=False)


class StudyValidationErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField(required=False)
    client_request_id = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    new_word_target = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    rating = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    timezone = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
