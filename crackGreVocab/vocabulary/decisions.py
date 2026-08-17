"""Reviewed provider selections and local editorial learning content."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import CorpusBuildError
from .files import FileSnapshot
from .normalization import canonical_prose, canonical_term, collapse_whitespace

DECISION_SCHEMA_VERSION = 4
EDITORIAL_PARTS_OF_SPEECH = frozenset(
    {
        "adjective",
        "adverb",
        "conjunction",
        "determiner",
        "interjection",
        "noun",
        "preposition",
        "pronoun",
        "verb",
    }
)


@dataclass(frozen=True)
class SenseSelection:
    """A reviewed reference to one exact provider definition/example pair."""

    provider: str
    provider_sense_id: str
    provider_synset_id: str
    definition_index: int
    example_index: int
    candidate_sha256: str

    @property
    def candidate_key(self) -> tuple[str, str, str, int]:
        """Return the provider-local identity used to find the pinned candidate."""
        return (
            self.provider,
            self.provider_sense_id,
            self.provider_synset_id,
            self.definition_index,
        )


@dataclass(frozen=True)
class ProviderWordDecision:
    """Reviewed provider senses plus an optional exceptional editorial note."""

    senses: tuple[SenseSelection, ...]
    review_note: str = ""


@dataclass(frozen=True)
class EditorialSense:
    """One locally written definition/example pair."""

    editorial_id: str
    part_of_speech: str
    definition: str
    example: str


@dataclass(frozen=True)
class EditorialWord:
    """Reviewed local learning content for one source word."""

    pronunciation: str
    senses: tuple[EditorialSense, ...]
    review_note: str = ""


def _load_document(snapshot: FileSnapshot, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(snapshot.content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusBuildError(
            f"cannot read {label} at {snapshot.path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise CorpusBuildError(f"{label} must be a JSON object")
    return value


def _review_note(value: object, *, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CorpusBuildError(f"{label} review note must be a string")
    try:
        note = canonical_prose(value, field="review note", maximum=1000)
    except (TypeError, ValueError) as exc:
        raise CorpusBuildError(f"invalid {label} review note: {exc}") from exc
    if note != value:
        raise CorpusBuildError(f"{label} review note must be canonical")
    return note


def load_sense_decisions_snapshot(
    snapshot: FileSnapshot,
    *,
    source_digest: str,
) -> dict[str, ProviderWordDecision]:
    """Load provider selections from exact bytes bound to the source digest."""
    document = _load_document(snapshot, label="sense decisions")
    if set(document) != {"schema_version", "selections", "source_sha256"}:
        raise CorpusBuildError("sense decisions have invalid top-level fields")
    if document.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise CorpusBuildError(
            f"sense decisions must use schema_version {DECISION_SCHEMA_VERSION}"
        )
    if document.get("source_sha256") != source_digest:
        raise CorpusBuildError("sense decisions do not match the current source digest")
    raw_selections = document.get("selections")
    if not isinstance(raw_selections, dict):
        raise CorpusBuildError("sense decisions must contain a selections object")

    selections: dict[str, ProviderWordDecision] = {}
    for normalized_term, raw_word in raw_selections.items():
        if not isinstance(normalized_term, str) or not isinstance(raw_word, dict):
            raise CorpusBuildError("sense selection keys and entries are invalid")
        try:
            term, identity = canonical_term(normalized_term)
        except ValueError as exc:
            raise CorpusBuildError(f"invalid sense decision term: {exc}") from exc
        if term != normalized_term or identity != normalized_term:
            raise CorpusBuildError(
                f"sense decision key {normalized_term!r} is not normalized"
            )
        if not set(raw_word) <= {"review_note", "senses"} or "senses" not in raw_word:
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} has invalid fields"
            )
        raw_items = raw_word["senses"]
        if not isinstance(raw_items, list) or not raw_items:
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} must select senses"
            )

        parsed: list[SenseSelection] = []
        for item in raw_items:
            if not isinstance(item, dict) or set(item) != {
                "candidate_sha256",
                "definition_index",
                "example_index",
                "provider",
                "provider_sense_id",
                "provider_synset_id",
            }:
                raise CorpusBuildError(
                    f"sense decision for {normalized_term!r} has invalid fields"
                )
            if not all(
                isinstance(item[field], str)
                for field in (
                    "candidate_sha256",
                    "provider",
                    "provider_sense_id",
                    "provider_synset_id",
                )
            ) or not all(
                isinstance(item[field], int)
                and not isinstance(item[field], bool)
                and item[field] >= 0
                for field in ("definition_index", "example_index")
            ):
                raise CorpusBuildError(
                    f"sense decision for {normalized_term!r} has invalid values"
                )
            parsed.append(
                SenseSelection(
                    provider=item["provider"],
                    provider_sense_id=item["provider_sense_id"],
                    provider_synset_id=item["provider_synset_id"],
                    definition_index=item["definition_index"],
                    example_index=item["example_index"],
                    candidate_sha256=item["candidate_sha256"],
                )
            )
        if len({selection.candidate_key for selection in parsed}) != len(parsed):
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} selects a sense twice"
            )
        selections[normalized_term] = ProviderWordDecision(
            senses=tuple(parsed),
            review_note=_review_note(
                raw_word.get("review_note"),
                label=f"sense decision for {normalized_term!r}",
            ),
        )
    return selections


def load_sense_decisions(
    path: Path,
    *,
    source_digest: str,
) -> dict[str, ProviderWordDecision]:
    """Load reviewed provider selections bound to the current source digest."""
    try:
        snapshot = FileSnapshot.read(path)
    except OSError as exc:
        raise CorpusBuildError(f"cannot read sense decisions at {path}: {exc}") from exc
    return load_sense_decisions_snapshot(snapshot, source_digest=source_digest)


def load_editorial_overrides_snapshot(
    snapshot: FileSnapshot,
    *,
    source_digest: str,
) -> dict[str, EditorialWord]:
    """Load checked local learning content from exact already-read bytes."""
    document = _load_document(snapshot, label="editorial overrides")
    if set(document) != {"schema_version", "source_sha256", "words"}:
        raise CorpusBuildError("editorial overrides have invalid top-level fields")
    if document.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise CorpusBuildError(
            f"editorial overrides must use schema_version {DECISION_SCHEMA_VERSION}"
        )
    if document.get("source_sha256") != source_digest:
        raise CorpusBuildError("editorial overrides do not match the source digest")
    raw_words = document.get("words")
    if not isinstance(raw_words, dict):
        raise CorpusBuildError("editorial overrides must contain a words object")

    overrides: dict[str, EditorialWord] = {}
    editorial_ids: set[str] = set()
    for normalized_term, raw_word in raw_words.items():
        if not isinstance(normalized_term, str) or not isinstance(raw_word, dict):
            raise CorpusBuildError("editorial override entries must be objects")
        try:
            term, identity = canonical_term(normalized_term)
        except ValueError as exc:
            raise CorpusBuildError(f"invalid editorial override term: {exc}") from exc
        if term != normalized_term or identity != normalized_term:
            raise CorpusBuildError(
                f"editorial override key {normalized_term!r} is not normalized"
            )
        if (
            not set(raw_word) <= {"pronunciation", "review_note", "senses"}
            or not {"pronunciation", "senses"} <= set(raw_word)
        ):
            raise CorpusBuildError(
                f"editorial override for {normalized_term!r} has invalid fields"
            )
        pronunciation = raw_word["pronunciation"]
        if not isinstance(pronunciation, str):
            raise CorpusBuildError(
                f"editorial pronunciation for {normalized_term!r} must be a string"
            )
        pronunciation = collapse_whitespace(pronunciation)
        if len(pronunciation) > 255:
            raise CorpusBuildError(
                f"editorial pronunciation for {normalized_term!r} is too long"
            )
        raw_senses = raw_word["senses"]
        if not isinstance(raw_senses, list) or not raw_senses:
            raise CorpusBuildError(
                f"editorial override for {normalized_term!r} needs senses"
            )

        senses: list[EditorialSense] = []
        for raw_sense in raw_senses:
            if not isinstance(raw_sense, dict) or set(raw_sense) != {
                "definition",
                "editorial_id",
                "example",
                "part_of_speech",
            }:
                raise CorpusBuildError(
                    f"editorial sense for {normalized_term!r} has invalid fields"
                )
            editorial_id = raw_sense["editorial_id"]
            part_of_speech = raw_sense["part_of_speech"]
            if not isinstance(editorial_id, str) or not editorial_id:
                raise CorpusBuildError("editorial_id must be a non-empty string")
            if editorial_id in editorial_ids:
                raise CorpusBuildError(f"duplicate editorial_id {editorial_id!r}")
            editorial_ids.add(editorial_id)
            if not isinstance(part_of_speech, str):
                raise CorpusBuildError("editorial part_of_speech must be a string")
            canonical_part_of_speech = collapse_whitespace(part_of_speech)
            if (
                canonical_part_of_speech != part_of_speech
                or part_of_speech not in EDITORIAL_PARTS_OF_SPEECH
            ):
                raise CorpusBuildError(
                    "editorial part_of_speech must be a canonical supported value"
                )
            try:
                definition = canonical_prose(
                    raw_sense["definition"], field="definition", maximum=1000
                )
                example = canonical_prose(
                    raw_sense["example"], field="example", maximum=1000
                )
            except (TypeError, ValueError) as exc:
                raise CorpusBuildError(
                    f"invalid editorial sense for {normalized_term!r}: {exc}"
                ) from exc
            senses.append(
                EditorialSense(
                    editorial_id=editorial_id,
                    part_of_speech=part_of_speech,
                    definition=definition,
                    example=example,
                )
            )
        overrides[normalized_term] = EditorialWord(
            pronunciation=pronunciation,
            senses=tuple(senses),
            review_note=_review_note(
                raw_word.get("review_note"),
                label=f"editorial override for {normalized_term!r}",
            ),
        )
    return overrides


def load_editorial_overrides(
    path: Path,
    *,
    source_digest: str,
) -> dict[str, EditorialWord]:
    """Load checked local definition/example pairs for unresolved words."""
    try:
        snapshot = FileSnapshot.read(path)
    except OSError as exc:
        raise CorpusBuildError(
            f"cannot read editorial overrides at {path}: {exc}"
        ) from exc
    return load_editorial_overrides_snapshot(snapshot, source_digest=source_digest)
