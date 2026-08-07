"""JSON contracts for backend-planned Study Sessions."""

from rest_framework import serializers
from vocabulary.models import VocabularySense

from .models import StudySession, StudySessionItem


class CreateStudySessionSerializer(serializers.Serializer):
    new_word_target = serializers.IntegerField(min_value=0, max_value=20)


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
            "items",
        )


class StudyPlanningErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class StudyValidationErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False)
    new_word_target = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
