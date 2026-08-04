"""Django application configuration for the foundational API."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Register the version-independent API foundation."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "Crack GRE Vocab API"
