"""JSON contracts for backend-planned Study Sessions."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from vocabulary.models import VocabularySense

from .models import RecallAnswer, RecallOutcome, StudySession, StudySessionItem


class CreateStudySessionSerializer(serializers.Serializer):
    new_word_target = serializers.IntegerField(min_value=0, max_value=20)


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
    items = StudySessionItemSerializer(many=True, read_only=True)
    answered_count = serializers.SerializerMethodField()
    remaining_count = serializers.SerializerMethodField()
    current_item = serializers.SerializerMethodField()

    @staticmethod
    def _unanswered_items(session: StudySession) -> list[StudySessionItem]:
        return [item for item in session.items.all() if not hasattr(item, "answer")]

    def get_answered_count(self, session: StudySession) -> int:
        return session.item_count - len(self._unanswered_items(session))

    def get_remaining_count(self, session: StudySession) -> int:
        return len(self._unanswered_items(session))

    @extend_schema_field(StudySessionItemSerializer(allow_null=True))
    def get_current_item(self, session: StudySession) -> dict[str, object] | None:
        unanswered = self._unanswered_items(session)
        if not unanswered:
            return None
        return StudySessionItemSerializer(unanswered[0]).data

    class Meta:
        model = StudySession
        fields = (
            "id",
            "status",
            "corpus_version",
            "new_word_target",
            "planned_new_word_count",
            "item_count",
            "planner_version",
            "created_at",
            "ended_at",
            "answered_count",
            "remaining_count",
            "current_item",
            "items",
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
    code = serializers.CharField(required=False)
    detail = serializers.CharField()
    current_item_id = serializers.UUIDField(required=False)
    retryable = serializers.BooleanField(required=False)


class StudyValidationErrorSerializer(serializers.Serializer):
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
