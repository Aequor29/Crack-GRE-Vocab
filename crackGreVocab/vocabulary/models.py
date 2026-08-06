"""Persistent, versioned vocabulary corpus models."""

import uuid

from django.db import models
from django.db.models import Q


class CorpusVersion(models.Model):
    """An immutable imported corpus release."""

    version = models.CharField(max_length=64, unique=True)
    schema_version = models.PositiveSmallIntegerField()
    source_digest = models.CharField(max_length=64)
    corpus_digest = models.CharField(max_length=64, unique=True)
    word_count = models.PositiveIntegerField()
    sense_count = models.PositiveIntegerField()
    is_active = models.BooleanField(default=False)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-imported_at",)
        constraints = (
            models.CheckConstraint(
                condition=Q(schema_version__gte=1),
                name="vocabulary_corpus_schema_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(word_count__gte=1),
                name="vocabulary_corpus_word_count_positive",
            ),
            models.CheckConstraint(
                condition=Q(sense_count__gte=1),
                name="vocabulary_corpus_sense_count_positive",
            ),
            models.UniqueConstraint(
                fields=("is_active",),
                condition=Q(is_active=True),
                name="vocabulary_one_active_corpus",
            ),
        )

    def __str__(self) -> str:
        return self.version


class VocabularyWord(models.Model):
    """A stable word identity shared by corpus versions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    term = models.CharField(max_length=128)
    normalized_term = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("normalized_term",)
        constraints = (
            models.CheckConstraint(
                condition=~Q(term=""),
                name="vocabulary_word_term_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(normalized_term=""),
                name="vocabulary_word_normalized_term_not_empty",
            ),
        )

    def __str__(self) -> str:
        return self.term


class CorpusEntry(models.Model):
    """A word's ordered membership and release-specific presentation data."""

    corpus = models.ForeignKey(
        CorpusVersion,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    word = models.ForeignKey(
        VocabularyWord,
        on_delete=models.PROTECT,
        related_name="corpus_entries",
    )
    term = models.CharField(max_length=128)
    position = models.PositiveIntegerField()
    pronunciation = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("position",)
        constraints = (
            models.CheckConstraint(
                condition=~Q(term=""),
                name="vocabulary_entry_term_not_empty",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="vocabulary_entry_position_positive",
            ),
            models.UniqueConstraint(
                fields=("corpus", "word"),
                name="vocabulary_entry_unique_word",
            ),
            models.UniqueConstraint(
                fields=("corpus", "position"),
                name="vocabulary_entry_unique_position",
            ),
        )

    def __str__(self) -> str:
        return f"{self.corpus.version}: {self.term}"


class VocabularySense(models.Model):
    """One ordered definition paired with exactly one usage example."""

    entry = models.ForeignKey(
        CorpusEntry,
        on_delete=models.CASCADE,
        related_name="senses",
    )
    position = models.PositiveSmallIntegerField()
    part_of_speech = models.CharField(max_length=32, blank=True)
    definition = models.TextField()
    example = models.TextField()
    provenance = models.JSONField()

    class Meta:
        ordering = ("position",)
        constraints = (
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="vocabulary_sense_position_positive",
            ),
            models.CheckConstraint(
                condition=~Q(definition=""),
                name="vocabulary_sense_definition_not_empty",
            ),
            models.CheckConstraint(
                condition=~Q(example=""),
                name="vocabulary_sense_example_not_empty",
            ),
            models.UniqueConstraint(
                fields=("entry", "position"),
                name="vocabulary_sense_unique_position",
            ),
        )

    def __str__(self) -> str:
        return f"{self.entry.word.term} sense {self.position}"
