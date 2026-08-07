"""Clean-rebuild learner account model."""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .managers import LearnerAccountManager


class LearnerAccount(AbstractBaseUser, PermissionsMixin):
    """A learner identified by email rather than a public username."""

    email = models.EmailField("email address", unique=True)
    display_name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = LearnerAccountManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        verbose_name = "learner account"
        verbose_name_plural = "learner accounts"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_learner_email_ci_unique",
            )
        ]

    def clean(self) -> None:
        """Normalize editable identity fields before validation."""
        super().clean()
        try:
            self.email = LearnerAccountManager.normalize_identity(self.email)
        except ValueError as exc:
            raise ValidationError({"email": str(exc)}) from exc
        self.display_name = self.display_name.strip()

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist one canonical email and a trimmed display name."""
        self.email = LearnerAccountManager.normalize_identity(self.email)
        self.display_name = self.display_name.strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email
