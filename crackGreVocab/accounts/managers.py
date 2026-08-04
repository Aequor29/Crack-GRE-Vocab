"""Account manager with one canonical email identity."""

from typing import Any

from django.contrib.auth.base_user import BaseUserManager

EMAIL_MAX_LENGTH = 254


class LearnerAccountManager(BaseUserManager):
    """Create learners whose normalized email is their sign-in identity."""

    use_in_migrations = True

    @classmethod
    def normalize_identity(cls, email: str) -> str:
        """Return the stored canonical form of an email identity."""
        if not email or not email.strip():
            raise ValueError("An email address is required.")
        normalized = cls.normalize_email(email.strip()).casefold()
        if len(normalized) > EMAIL_MAX_LENGTH:
            raise ValueError(
                f"An email address must be at most {EMAIL_MAX_LENGTH} characters "
                "after normalization."
            )
        return normalized

    def _create_user(
        self,
        email: str,
        password: str | None,
        *,
        display_name: str,
        **extra_fields: Any,
    ):
        normalized_name = display_name.strip()
        if not normalized_name:
            raise ValueError("A display name is required.")

        account = self.model(
            email=self.normalize_identity(email),
            display_name=normalized_name,
            **extra_fields,
        )
        account.set_password(password)
        account.save(using=self._db)
        return account

    def create_user(
        self,
        email: str,
        password: str | None = None,
        *,
        display_name: str,
        **extra_fields: Any,
    ):
        """Create a regular learner account."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(
            email,
            password,
            display_name=display_name,
            **extra_fields,
        )

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        *,
        display_name: str,
        **extra_fields: Any,
    ):
        """Create an administrative account with the same email contract."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self._create_user(
            email,
            password,
            display_name=display_name,
            **extra_fields,
        )
