"""Django application configuration for learner accounts."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Register the learner account application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Learner accounts"

    def ready(self) -> None:
        """Register the OpenAPI extension for strict session authentication."""
        from . import schema  # noqa: F401
