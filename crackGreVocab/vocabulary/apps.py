"""Django application configuration for vocabulary content."""

from django.apps import AppConfig


class VocabularyConfig(AppConfig):
    """Register the repository-owned vocabulary corpus domain."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "vocabulary"
    verbose_name = "Vocabulary Corpus"
