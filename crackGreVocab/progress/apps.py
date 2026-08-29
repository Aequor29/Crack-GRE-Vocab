from django.apps import AppConfig


class ProgressConfig(AppConfig):
    """Configure the read-only Learning Progress domain."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "progress"
