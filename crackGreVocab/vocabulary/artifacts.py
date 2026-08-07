"""Canonical corpus artifact serialization and strict offline validation."""

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .example_matching import EXAMPLE_MATCH_POLICY_VERSION, match_example_text
from .exceptions import CorpusImportError
from .normalization import (
    canonical_json_bytes,
    canonical_prose,
    canonical_term,
    canonical_version,
    collapse_whitespace,
    sha256_bytes,
    stable_word_id,
)

CORPUS_SCHEMA_VERSION = 1
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class CanonicalSense:
    position: int
    part_of_speech: str
    definition: str
    example: str
    provenance: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition,
            "example": self.example,
            "part_of_speech": self.part_of_speech,
            "position": self.position,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class CanonicalWord:
    position: int
    word_id: uuid.UUID
    term: str
    normalized_term: str
    pronunciation: str
    senses: tuple[CanonicalSense, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "normalized_term": self.normalized_term,
            "position": self.position,
            "pronunciation": self.pronunciation,
            "senses": [sense.as_dict() for sense in self.senses],
            "term": self.term,
            "word_id": str(self.word_id),
        }


@dataclass(frozen=True)
class LoadedCorpus:
    manifest_path: Path
    version: str
    schema_version: int
    source_digest: str
    corpus_digest: str
    words: tuple[CanonicalWord, ...]
    sense_count: int


def corpus_jsonl_bytes(words: tuple[CanonicalWord, ...]) -> bytes:
    return b"".join(canonical_json_bytes(word.as_dict()) for word in words)


def _required_object(
    value: Any,
    *,
    label: str,
    keys: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CorpusImportError(f"{label} must be an object")
    if set(value) != keys:
        raise CorpusImportError(
            f"{label} fields must be exactly {sorted(keys)}, got {sorted(value)}"
        )
    return value


def _digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise CorpusImportError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _positive_int(value: Any, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CorpusImportError(f"{label} must be a positive integer")
    return value


def _load_sense(
    value: Any,
    *,
    word: str,
    normalized_term: str,
    expected_position: int,
) -> CanonicalSense:
    document = _required_object(
        value,
        label=f"sense {expected_position} for {word!r}",
        keys={"definition", "example", "part_of_speech", "position", "provenance"},
    )
    if document["position"] != expected_position:
        raise CorpusImportError(f"senses for {word!r} must have contiguous positions")
    if not isinstance(document["part_of_speech"], str):
        raise CorpusImportError(f"part_of_speech for {word!r} must be a string")
    part_of_speech = collapse_whitespace(document["part_of_speech"])
    if len(part_of_speech) > 32:
        raise CorpusImportError(f"part_of_speech for {word!r} is too long")
    try:
        definition = canonical_prose(
            document["definition"],
            field="definition",
            maximum=1000,
        )
        example = canonical_prose(
            document["example"],
            field="example",
            maximum=1000,
        )
    except (TypeError, ValueError) as exc:
        raise CorpusImportError(f"invalid sense for {word!r}: {exc}") from exc
    if definition != document["definition"] or example != document["example"]:
        raise CorpusImportError(f"sense text for {word!r} is not canonical")
    provenance = document["provenance"]
    if not isinstance(provenance, dict) or not isinstance(
        provenance.get("provider"), str
    ):
        raise CorpusImportError(f"sense for {word!r} needs provider provenance")
    matched = match_example_text(normalized_term, part_of_speech, example)
    if matched is None:
        raise CorpusImportError(
            f"example for {word!r} does not contain the exact headword"
        )
    expected_match = {
        "form": matched.form,
        "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
        "surface": matched.surface,
    }
    if provenance.get("example_headword_match") != expected_match:
        raise CorpusImportError(
            f"example headword provenance for {word!r} does not match its text"
        )
    return CanonicalSense(
        position=expected_position,
        part_of_speech=part_of_speech,
        definition=definition,
        example=example,
        provenance=provenance,
    )


def _load_word(value: Any, *, expected_position: int) -> CanonicalWord:
    document = _required_object(
        value,
        label=f"corpus word {expected_position}",
        keys={
            "normalized_term",
            "position",
            "pronunciation",
            "senses",
            "term",
            "word_id",
        },
    )
    if document["position"] != expected_position:
        raise CorpusImportError("corpus words must have contiguous positions")
    if not isinstance(document["term"], str) or not isinstance(
        document["normalized_term"], str
    ):
        raise CorpusImportError("word terms must be strings")
    try:
        term, normalized_term = canonical_term(document["term"])
    except ValueError as exc:
        raise CorpusImportError(f"invalid corpus word: {exc}") from exc
    if term != document["term"] or normalized_term != document["normalized_term"]:
        raise CorpusImportError(
            f"word {document['term']!r} is not canonically normalized"
        )
    try:
        word_id = uuid.UUID(str(document["word_id"]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CorpusImportError(f"word {term!r} has an invalid UUID") from exc
    if word_id != stable_word_id(normalized_term):
        raise CorpusImportError(
            f"word {term!r} does not use its deterministic stable identity"
        )
    if not isinstance(document["pronunciation"], str):
        raise CorpusImportError(f"pronunciation for {term!r} must be a string")
    pronunciation = collapse_whitespace(document["pronunciation"])
    if pronunciation != document["pronunciation"] or len(pronunciation) > 255:
        raise CorpusImportError(f"pronunciation for {term!r} is not canonical")
    raw_senses = document["senses"]
    if not isinstance(raw_senses, list) or not raw_senses:
        raise CorpusImportError(f"word {term!r} must have at least one sense")
    senses = tuple(
        _load_sense(
            raw_sense,
            word=term,
            normalized_term=normalized_term,
            expected_position=position,
        )
        for position, raw_sense in enumerate(raw_senses, start=1)
    )
    return CanonicalWord(
        position=expected_position,
        word_id=word_id,
        term=term,
        normalized_term=normalized_term,
        pronunciation=pronunciation,
        senses=senses,
    )


def load_corpus(manifest_path: Path) -> LoadedCorpus:
    """Validate a manifest and its corpus bytes before any database write."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusImportError(
            f"cannot read corpus manifest {manifest_path}: {exc}"
        ) from exc
    manifest = _required_object(
        manifest,
        label="corpus manifest",
        keys={"corpus", "corpus_version", "inputs", "schema_version", "source"},
    )
    if manifest["schema_version"] != CORPUS_SCHEMA_VERSION:
        raise CorpusImportError(
            f"unsupported corpus schema version {manifest['schema_version']!r}"
        )
    try:
        version = canonical_version(manifest["corpus_version"])
    except (TypeError, ValueError) as exc:
        raise CorpusImportError(str(exc)) from exc
    source = _required_object(
        manifest["source"],
        label="manifest source",
        keys={"canonical_word_count", "row_count", "sha256"},
    )
    source_digest = _digest(source["sha256"], label="source sha256")
    source_row_count = _positive_int(source["row_count"], label="source row_count")
    source_word_count = _positive_int(
        source["canonical_word_count"],
        label="source canonical_word_count",
    )
    if source_row_count < source_word_count:
        raise CorpusImportError(
            "manifest source row_count cannot be smaller than "
            "canonical_word_count"
        )
    inputs = manifest["inputs"]
    if not isinstance(inputs, dict) or not inputs:
        raise CorpusImportError("manifest inputs must be a non-empty object")
    for label, value in inputs.items():
        _digest(value, label=f"input digest {label}")
    corpus = _required_object(
        manifest["corpus"],
        label="manifest corpus",
        keys={"file", "sense_count", "sha256", "word_count"},
    )
    corpus_digest = _digest(corpus["sha256"], label="corpus sha256")
    expected_words = _positive_int(corpus["word_count"], label="corpus word_count")
    expected_senses = _positive_int(corpus["sense_count"], label="corpus sense_count")
    if source_word_count != expected_words:
        raise CorpusImportError(
            "manifest source and corpus canonical word counts do not match"
        )
    corpus_file = corpus["file"]
    if not isinstance(corpus_file, str) or not corpus_file:
        raise CorpusImportError("manifest corpus file must be a relative path")
    if Path(corpus_file).is_absolute():
        raise CorpusImportError("manifest corpus file must be a relative path")
    try:
        manifest_directory = manifest_path.resolve().parent
        corpus_path = (manifest_directory / corpus_file).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise CorpusImportError(
            f"invalid manifest corpus file path {corpus_file!r}: {exc}"
        ) from exc
    if not corpus_path.is_relative_to(manifest_directory):
        raise CorpusImportError("manifest corpus file escapes its artifact directory")
    try:
        corpus_content = corpus_path.read_bytes()
    except (OSError, ValueError) as exc:
        raise CorpusImportError(
            f"cannot read corpus artifact {corpus_path}: {exc}"
        ) from exc
    if sha256_bytes(corpus_content) != corpus_digest:
        raise CorpusImportError("corpus artifact digest does not match the manifest")
    if not corpus_content.endswith(b"\n"):
        raise CorpusImportError("corpus JSONL must end with a line feed")

    words: list[CanonicalWord] = []
    for line_number, line in enumerate(corpus_content.splitlines(), start=1):
        try:
            value = json.loads(line)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise CorpusImportError(
                f"corpus line {line_number} is not valid UTF-8 JSON: {exc}"
            ) from exc
        words.append(_load_word(value, expected_position=line_number))
    if len(words) != expected_words:
        raise CorpusImportError(
            f"manifest declares {expected_words} words but artifact has {len(words)}"
        )
    normalized_terms = [word.normalized_term for word in words]
    if normalized_terms != sorted(normalized_terms):
        raise CorpusImportError("corpus words must be sorted by normalized_term")
    if len(set(normalized_terms)) != len(normalized_terms):
        raise CorpusImportError("corpus contains duplicate normalized terms")
    word_ids = [word.word_id for word in words]
    if len(set(word_ids)) != len(word_ids):
        raise CorpusImportError("corpus contains duplicate word IDs")
    actual_senses = sum(len(word.senses) for word in words)
    if actual_senses != expected_senses:
        raise CorpusImportError(
            f"manifest declares {expected_senses} senses but artifact has "
            f"{actual_senses}"
        )
    canonical_content = corpus_jsonl_bytes(tuple(words))
    if corpus_content != canonical_content:
        raise CorpusImportError("corpus JSONL bytes are not canonical")
    return LoadedCorpus(
        manifest_path=manifest_path,
        version=version,
        schema_version=CORPUS_SCHEMA_VERSION,
        source_digest=source_digest,
        corpus_digest=corpus_digest,
        words=tuple(words),
        sense_count=actual_senses,
    )
