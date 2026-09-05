"""Deterministic Study domain fixtures."""

import hashlib
from collections.abc import Mapping, Sequence

from django.contrib.auth import get_user_model
from vocabulary.models import (
    CorpusEntry,
    CorpusVersion,
    VocabularySense,
    VocabularyWord,
)

LearnerAccount = get_user_model()


def create_learner(*, email: str = "learner@example.com"):
    """Create a learner with password authentication."""
    return LearnerAccount.objects.create_user(
        email=email,
        display_name="Learner",
        password="durable-recall-river-927",
    )


def create_corpus(
    terms: Sequence[str],
    *,
    version: str = "study-test-v1",
    is_active: bool = True,
    words_by_term: Mapping[str, VocabularyWord] | None = None,
) -> tuple[CorpusVersion, list[CorpusEntry]]:
    """Create a corpus with one definition and example for each term."""
    digest = hashlib.sha256(version.encode()).hexdigest()
    corpus = CorpusVersion.objects.create(
        version=version,
        schema_version=1,
        source_digest=hashlib.sha256(f"source:{version}".encode()).hexdigest(),
        corpus_digest=digest,
        word_count=max(1, len(terms)),
        sense_count=max(1, len(terms)),
        is_active=is_active,
    )
    entries: list[CorpusEntry] = []
    for position, term in enumerate(terms, start=1):
        word = words_by_term.get(term) if words_by_term is not None else None
        if word is None:
            word = VocabularyWord.objects.create(
                term=term,
                normalized_term=term.casefold(),
            )
        entry = CorpusEntry.objects.create(
            corpus=corpus,
            word=word,
            term=term,
            position=position,
            pronunciation=f"/{term}/",
        )
        VocabularySense.objects.create(
            entry=entry,
            position=1,
            part_of_speech="adjective",
            definition=f"Definition for {term}.",
            example=f"An example using {term}.",
            provenance={"provider": "test"},
        )
        entries.append(entry)
    return corpus, entries
