"""Atomic and idempotent PostgreSQL import of validated corpus artifacts."""

from dataclasses import asdict, dataclass
from pathlib import Path

from django.db import DatabaseError, transaction
from django.db.models import Q

from .artifacts import LoadedCorpus, load_corpus
from .exceptions import CorpusImportError
from .models import CorpusEntry, CorpusVersion, VocabularySense, VocabularyWord


@dataclass(frozen=True)
class ImportReport:
    version: str
    corpus_digest: str
    word_count: int
    sense_count: int
    created_corpus: bool
    created_words: int
    activated: bool

    def as_dict(self) -> dict[str, str | int | bool]:
        return asdict(self)


def _validate_existing_metadata(
    existing: CorpusVersion,
    artifact: LoadedCorpus,
) -> None:
    """Reject version reuse when immutable release metadata differs."""
    expected = {
        "corpus_digest": artifact.corpus_digest,
        "schema_version": artifact.schema_version,
        "sense_count": artifact.sense_count,
        "source_digest": artifact.source_digest,
        "word_count": len(artifact.words),
    }
    actual = {field: getattr(existing, field) for field in expected}
    if actual != expected:
        raise CorpusImportError(
            f"corpus version {artifact.version!r} already exists with different "
            "metadata"
        )


def _activate(corpus: CorpusVersion) -> bool:
    if corpus.is_active:
        return False
    CorpusVersion.objects.filter(is_active=True).update(is_active=False)
    corpus.is_active = True
    corpus.save(update_fields=("is_active",))
    return True


def _import_validated(artifact: LoadedCorpus, *, activate: bool) -> ImportReport:
    existing = CorpusVersion.objects.filter(version=artifact.version).first()
    if existing is not None:
        _validate_existing_metadata(existing, artifact)
        activated = _activate(existing) if activate else False
        return ImportReport(
            version=artifact.version,
            corpus_digest=artifact.corpus_digest,
            word_count=len(artifact.words),
            sense_count=artifact.sense_count,
            created_corpus=False,
            created_words=0,
            activated=activated,
        )
    digest_owner = CorpusVersion.objects.filter(
        corpus_digest=artifact.corpus_digest
    ).first()
    if digest_owner is not None:
        raise CorpusImportError(
            f"corpus digest is already owned by version {digest_owner.version!r}"
        )

    expected_by_id = {word.word_id: word for word in artifact.words}
    expected_by_term = {word.normalized_term: word for word in artifact.words}
    existing_words = list(
        VocabularyWord.objects.filter(
            Q(id__in=expected_by_id) | Q(normalized_term__in=expected_by_term)
        )
    )
    for existing_word in existing_words:
        expected = expected_by_id.get(existing_word.id)
        if (
            expected is None
            or expected.normalized_term != existing_word.normalized_term
        ):
            raise CorpusImportError(
                f"stable word ID conflict for {existing_word.normalized_term!r}"
            )

    existing_ids = {word.id for word in existing_words}
    new_words = [
        VocabularyWord(
            id=word.word_id,
            term=word.term,
            normalized_term=word.normalized_term,
        )
        for word in artifact.words
        if word.word_id not in existing_ids
    ]
    VocabularyWord.objects.bulk_create(new_words, batch_size=500)
    database_words = {
        word.id: word for word in (*existing_words, *new_words)
    }

    corpus = CorpusVersion.objects.create(
        version=artifact.version,
        schema_version=artifact.schema_version,
        source_digest=artifact.source_digest,
        corpus_digest=artifact.corpus_digest,
        word_count=len(artifact.words),
        sense_count=artifact.sense_count,
        is_active=False,
    )
    entries = [
        CorpusEntry(
            corpus=corpus,
            word=database_words[word.word_id],
            term=word.term,
            position=word.position,
            pronunciation=word.pronunciation,
        )
        for word in artifact.words
    ]
    CorpusEntry.objects.bulk_create(entries, batch_size=500)

    senses = [
        VocabularySense(
            entry=entry,
            position=sense.position,
            part_of_speech=sense.part_of_speech,
            definition=sense.definition,
            example=sense.example,
            provenance=sense.provenance,
        )
        for word, entry in zip(artifact.words, entries, strict=True)
        for sense in word.senses
    ]
    VocabularySense.objects.bulk_create(senses, batch_size=1000)
    if len(senses) != artifact.sense_count:
        raise CorpusImportError("imported sense count does not match the manifest")
    activated = _activate(corpus) if activate else False
    return ImportReport(
        version=artifact.version,
        corpus_digest=artifact.corpus_digest,
        word_count=len(artifact.words),
        sense_count=artifact.sense_count,
        created_corpus=True,
        created_words=len(new_words),
        activated=activated,
    )


def import_corpus(manifest_path: Path, *, activate: bool = True) -> ImportReport:
    """Validate before writes, then import all content in one database transaction."""
    artifact = load_corpus(manifest_path)
    try:
        with transaction.atomic():
            return _import_validated(artifact, activate=activate)
    except CorpusImportError:
        raise
    except DatabaseError as exc:
        raise CorpusImportError(
            f"database rejected corpus {artifact.version!r}: {exc.__class__.__name__}"
        ) from exc
