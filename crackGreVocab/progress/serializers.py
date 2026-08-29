"""OpenAPI-visible Learning Progress request and response contracts."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers
from study.models import RecallAnswer, SchedulingPhase


class ProgressTimezoneQuerySerializer(serializers.Serializer):
    timezone = serializers.CharField(max_length=64)

    def validate_timezone(self, value: str) -> str:
        """Require a valid IANA timezone name."""
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise serializers.ValidationError(
                "Enter a valid IANA timezone name."
            ) from exc
        return value


class CorpusProgressSerializer(serializers.Serializer):
    version = serializers.CharField()
    total = serializers.IntegerField(min_value=0)
    unseen = serializers.IntegerField(min_value=0)
    learning = serializers.IntegerField(min_value=0)
    review = serializers.IntegerField(min_value=0)


class ActionableProgressSerializer(serializers.Serializer):
    due_now = serializers.IntegerField(min_value=0)
    due_today = serializers.IntegerField(min_value=0)
    has_active_session = serializers.BooleanField()


class TodayProgressSerializer(serializers.Serializer):
    date = serializers.DateField()
    timezone = serializers.CharField()
    sessions_started = serializers.IntegerField(min_value=0)
    sessions_completed = serializers.IntegerField(min_value=0)
    answers = serializers.IntegerField(min_value=0)
    remembered = serializers.IntegerField(min_value=0)
    forgot = serializers.IntegerField(min_value=0)


class RecentRecallOutcomeSerializer(serializers.Serializer):
    word_id = serializers.UUIDField()
    term = serializers.CharField()
    rating = serializers.ChoiceField(choices=RecallAnswer.Rating.choices)
    phase = serializers.ChoiceField(choices=SchedulingPhase.choices)
    next_due_at = serializers.DateTimeField()
    occurred_at = serializers.DateTimeField()


class LearningProgressSummarySerializer(serializers.Serializer):
    corpus = CorpusProgressSerializer()
    actionable = ActionableProgressSerializer()
    today = TodayProgressSerializer()
    recent_outcomes = RecentRecallOutcomeSerializer(many=True)


class ProgressErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    retryable = serializers.BooleanField(required=False)
