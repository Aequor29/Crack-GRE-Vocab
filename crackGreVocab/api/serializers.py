"""Public response contracts for the foundational API."""

from rest_framework import serializers


class ServiceIndexSerializer(serializers.Serializer):
    """Describe the database-independent service document."""

    service = serializers.CharField()


class ReadinessSerializer(serializers.Serializer):
    """Describe the stable ready or database-unavailable response shape."""

    status = serializers.ChoiceField(choices=("ready", "unavailable"))
    database = serializers.ChoiceField(choices=("available", "unavailable"))
