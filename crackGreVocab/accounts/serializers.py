"""Typed request and response contracts for learner accounts."""

from typing import Any

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from .managers import EMAIL_MAX_LENGTH, LearnerAccountManager

LearnerAccount = get_user_model()


def normalize_email_identity(value: str) -> str:
    """Normalize an email without allowing case folding to exceed storage."""
    try:
        return LearnerAccountManager.normalize_identity(value)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc


class LearnerAccountSerializer(serializers.ModelSerializer):
    """Return the public portion of the current learner account."""

    class Meta:
        model = LearnerAccount
        fields = ("id", "email", "display_name")
        read_only_fields = fields


class SignUpSerializer(serializers.Serializer):
    """Validate and create a clean-rebuild learner account."""

    email = serializers.EmailField(max_length=EMAIL_MAX_LENGTH)
    display_name = serializers.CharField(max_length=80, trim_whitespace=True)
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_email(self, value: str) -> str:
        normalized = normalize_email_identity(value)
        if LearnerAccount.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        candidate = LearnerAccount(
            email=attrs["email"],
            display_name=attrs["display_name"],
        )
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data: dict[str, Any]):
        try:
            with transaction.atomic():
                return LearnerAccount.objects.create_user(**validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"email": ["An account with this email already exists."]}
            ) from exc


class SignInSerializer(serializers.Serializer):
    """Validate the credentials supplied for a new server session."""

    email = serializers.EmailField(max_length=EMAIL_MAX_LENGTH)
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_email(self, value: str) -> str:
        return normalize_email_identity(value)


class PasswordResetStartSerializer(serializers.Serializer):
    """Validate a non-enumerating password-recovery request."""

    email = serializers.EmailField(max_length=EMAIL_MAX_LENGTH)

    def validate_email(self, value: str) -> str:
        return normalize_email_identity(value)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validate the opaque identity, token, and replacement password shape."""

    uid = serializers.CharField(max_length=128, trim_whitespace=False)
    token = serializers.CharField(max_length=256, trim_whitespace=False)
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class CsrfTokenSerializer(serializers.Serializer):
    """Return a masked CSRF token for one unsafe request."""

    csrf_token = serializers.CharField()


class ApiMessageSerializer(serializers.Serializer):
    """Describe an API response carrying one human-readable message."""

    detail = serializers.CharField()


class AuthValidationErrorSerializer(serializers.Serializer):
    """Describe malformed JSON or field-level account input errors."""

    detail = serializers.CharField(required=False)
    email = serializers.ListField(child=serializers.CharField(), required=False)
    display_name = serializers.ListField(child=serializers.CharField(), required=False)
    password = serializers.ListField(child=serializers.CharField(), required=False)
    token = serializers.ListField(child=serializers.CharField(), required=False)
    uid = serializers.ListField(child=serializers.CharField(), required=False)
    non_field_errors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
