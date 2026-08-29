"""OpenAPI-visible Learning Progress request and response contracts."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers


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
    reviewing = serializers.IntegerField(min_value=0)
    mastered = serializers.IntegerField(min_value=0)


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


class LearningProgressSummarySerializer(serializers.Serializer):
    corpus = CorpusProgressSerializer()
    actionable = ActionableProgressSerializer()
    today = TodayProgressSerializer()


class ReviewRecallPeriodSerializer(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    remembered = serializers.IntegerField(min_value=0)
    answers = serializers.IntegerField(min_value=0)
    rate_percent = serializers.IntegerField(
        min_value=0,
        max_value=100,
        allow_null=True,
    )
    has_sufficient_data = serializers.BooleanField()


class ReviewRecallSerializer(serializers.Serializer):
    current = ReviewRecallPeriodSerializer()
    previous = ReviewRecallPeriodSerializer()
    change_percentage_points = serializers.IntegerField(allow_null=True)


class StudyDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    answers = serializers.IntegerField(min_value=1)
    words_practiced = serializers.IntegerField(min_value=1)


class StudyConsistencySerializer(serializers.Serializer):
    calendar_starts_on = serializers.DateField()
    calendar_ends_on = serializers.DateField()
    current_streak_days = serializers.IntegerField(min_value=0)
    study_days = StudyDaySerializer(many=True)


class WeeklyLearningCurvePointSerializer(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    unseen = serializers.IntegerField(min_value=0)
    learning = serializers.IntegerField(min_value=0)
    reviewing = serializers.IntegerField(min_value=0)
    mastered = serializers.IntegerField(min_value=0)


class LearningInsightsSerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    timezone = serializers.CharField()
    review_recall = ReviewRecallSerializer()
    consistency = StudyConsistencySerializer()
    learning_curve = WeeklyLearningCurvePointSerializer(
        many=True,
        min_length=12,
        max_length=12,
    )


class ProgressErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    retryable = serializers.BooleanField(required=False)
