"""Pinned offline provider snapshots and sense-preserving parsers."""

import json
import math
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .exceptions import SnapshotError
from .normalization import (
    canonical_json_bytes,
    canonical_prose,
    canonical_term,
    collapse_whitespace,
    sha256_bytes,
    sha256_file,
)

PROVIDER_SCHEMA_VERSION = 1
EXPECTED_PROVIDER_CONTRACTS = {
    "dictionaryapi-dev-v2": ("http-json", 1, 3),
    "freedictionaryapi-v1": ("http-json", 1, 2),
    "oewn-2025": ("bulk-zip", 1, 1),
}
HTTP_CACHE_FIELDS = {
    "http_status",
    "normalized_term",
    "payload",
    "payload_sha256",
    "provider",
    "request_url",
    "status",
}


@dataclass(frozen=True)
class ProviderConfig:
    """One checked provider contract."""

    id: str
    kind: str
    priority: int
    parser_version: int
    version: str = ""
    archive_url: str = ""
    archive_sha256: str = ""
    base_url: str = ""
    rate_limit_per_hour: int | None = None
    minimum_interval_seconds: float = 0.0


def _metadata_text(value: Any, *, field: str, maximum: int) -> str:
    """Normalize bounded provider metadata accepted by the artifact schema."""
    if not isinstance(value, str):
        raise SnapshotError(f"provider {field} must be a string")
    text = collapse_whitespace(value)
    if len(text) > maximum:
        raise SnapshotError(f"provider {field} must be at most {maximum} characters")
    return text


def _provider_prose(value: Any, *, field: str, maximum: int) -> str:
    """Translate malformed public provider text into a snapshot domain error."""
    try:
        return canonical_prose(value, field=field, maximum=maximum)
    except (TypeError, ValueError) as exc:
        raise SnapshotError(f"provider {field} is invalid: {exc}") from exc


def _response_normalized_term(record: dict[str, Any], *, provider: str) -> str:
    normalized_term = record.get("normalized_term")
    if not isinstance(normalized_term, str):
        raise SnapshotError(
            f"{provider} response record must contain a normalized term"
        )
    try:
        term, identity = canonical_term(normalized_term)
    except ValueError as exc:
        raise SnapshotError(
            f"{provider} response record has an invalid normalized term"
        ) from exc
    if term != normalized_term or identity != normalized_term:
        raise SnapshotError(
            f"{provider} response record term is not canonically normalized"
        )
    return normalized_term


def _validate_response_headword(
    value: Any,
    normalized_term: str,
    *,
    field: str,
) -> None:
    if not isinstance(value, str):
        raise SnapshotError(f"{field} must be a string")
    try:
        _term, identity = canonical_term(value)
    except ValueError as exc:
        raise SnapshotError(f"{field} is invalid") from exc
    if identity != normalized_term:
        raise SnapshotError(
            f"{field} does not match normalized term {normalized_term!r}"
        )


@dataclass(frozen=True)
class ProviderExample:
    """One same-sense usage example and its source attribution."""

    text: str
    provenance: dict[str, Any]

    def as_review_dict(self) -> dict[str, Any]:
        return {"provenance": self.provenance, "text": self.text}


@dataclass(frozen=True)
class SenseCandidate:
    """A definition and its same-sense examples from one provider."""

    provider: str
    provider_sense_id: str
    provider_synset_id: str
    definition_index: int
    part_of_speech: str
    definition: str
    examples: tuple[ProviderExample, ...]
    members: tuple[str, ...]
    pronunciation: str
    provenance: dict[str, Any]

    @property
    def selection_key(self) -> tuple[str, str, str, int]:
        return (
            self.provider,
            self.provider_sense_id,
            self.provider_synset_id,
            self.definition_index,
        )

    def as_review_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition,
            "definition_index": self.definition_index,
            "examples": [example.as_review_dict() for example in self.examples],
            "members": list(self.members),
            "part_of_speech": self.part_of_speech,
            "provider": self.provider,
            "provider_sense_id": self.provider_sense_id,
            "provider_synset_id": self.provider_synset_id,
            "provenance": self.provenance,
        }

    @property
    def content_digest(self) -> str:
        """Bind reviewed selections to the exact provider candidate content."""
        return sha256_bytes(canonical_json_bytes(self.as_review_dict()))


def load_provider_registry(path: Path) -> dict[str, ProviderConfig]:
    """Load the checked provider versions, URLs, checksums, and parser versions."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot read provider registry at {path}: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise SnapshotError("provider registry must use schema_version 1")
    providers = document.get("providers")
    if not isinstance(providers, list) or not providers:
        raise SnapshotError("provider registry must contain providers")

    result: dict[str, ProviderConfig] = {}
    for item in providers:
        if not isinstance(item, dict):
            raise SnapshotError("each provider registry item must be an object")
        try:
            config = ProviderConfig(
                id=str(item["id"]),
                kind=str(item["kind"]),
                priority=int(item["priority"]),
                parser_version=int(item["parser_version"]),
                version=str(item.get("version", "")),
                archive_url=str(item.get("archive_url", "")),
                archive_sha256=str(item.get("archive_sha256", "")),
                base_url=str(item.get("base_url", "")),
                rate_limit_per_hour=(
                    int(item["rate_limit_per_hour"])
                    if "rate_limit_per_hour" in item
                    else None
                ),
                minimum_interval_seconds=float(
                    item.get("minimum_interval_seconds", 0.0)
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SnapshotError(f"invalid provider registry item: {item!r}") from exc
        if config.id in result:
            raise SnapshotError(f"duplicate provider id {config.id!r}")
        if config.priority < 1:
            raise SnapshotError(f"provider {config.id!r} priority must be positive")
        if not math.isfinite(config.minimum_interval_seconds):
            raise SnapshotError(
                f"provider {config.id!r} request interval must be finite"
            )
        if config.rate_limit_per_hour is not None and config.rate_limit_per_hour < 1:
            raise SnapshotError(
                f"provider {config.id!r} hourly rate limit must be positive"
            )
        expected_contract = EXPECTED_PROVIDER_CONTRACTS.get(config.id)
        actual_contract = (config.kind, config.parser_version, config.priority)
        if expected_contract != actual_contract:
            raise SnapshotError(
                f"unsupported provider contract {config.id}: {actual_contract}"
            )
        if config.kind == "bulk-zip" and (
            not config.archive_url or len(config.archive_sha256) != 64
        ):
            raise SnapshotError(f"bulk provider {config.id!r} is not fully pinned")
        if config.kind == "http-json" and not config.base_url:
            raise SnapshotError(f"HTTP provider {config.id!r} has no base URL")
        if config.kind == "http-json" and config.minimum_interval_seconds <= 0:
            raise SnapshotError(
                f"HTTP provider {config.id!r} needs a positive request interval"
            )
        if (
            config.rate_limit_per_hour is not None
            and config.minimum_interval_seconds < 3600 / config.rate_limit_per_hour
        ):
            raise SnapshotError(
                f"HTTP provider {config.id!r} request interval exceeds its rate limit"
            )
        result[config.id] = config
    return result


def _json_object(content: bytes, *, label: str) -> dict[str, Any]:
    try:
        document = json.loads(content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise SnapshotError(f"{label} must contain a JSON object")
    return document


def load_oewn_candidates(
    archive_path: Path,
    config: ProviderConfig,
    normalized_terms: set[str],
) -> dict[str, tuple[SenseCandidate, ...]]:
    """Read only requested lemmas from a checksum-pinned OEWN JSON archive."""
    if config.id != "oewn-2025" or config.kind != "bulk-zip":
        raise SnapshotError("OEWN parser received the wrong provider configuration")
    try:
        actual_digest = sha256_file(archive_path)
    except OSError as exc:
        raise SnapshotError(f"cannot read OEWN archive {archive_path}: {exc}") from exc
    if actual_digest != config.archive_sha256:
        raise SnapshotError(
            f"OEWN archive checksum mismatch: expected {config.archive_sha256}, "
            f"got {actual_digest}"
        )

    selected_entries: list[tuple[str, str, dict[str, Any]]] = []
    referenced_synsets: set[str] = set()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entry_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("entries-") and name.endswith(".json")
            )
            if not entry_names:
                raise SnapshotError("OEWN archive has no entries-*.json files")
            for name in entry_names:
                entries = _json_object(archive.read(name), label=f"OEWN {name}")
                for lemma, entry in entries.items():
                    if not isinstance(lemma, str) or not isinstance(entry, dict):
                        raise SnapshotError(f"OEWN {name} contains an invalid entry")
                    try:
                        _term, normalized_term = canonical_term(lemma)
                    except ValueError:
                        continue
                    if normalized_term not in normalized_terms:
                        continue
                    selected_entries.append((normalized_term, lemma, entry))
                    for part in entry.values():
                        if not isinstance(part, dict):
                            continue
                        senses = part.get("sense", [])
                        if not isinstance(senses, list):
                            raise SnapshotError(
                                f"OEWN entry {lemma!r} has invalid senses"
                            )
                        for sense in senses:
                            if isinstance(sense, dict) and isinstance(
                                sense.get("synset"), str
                            ):
                                referenced_synsets.add(sense["synset"])

            synsets: dict[str, dict[str, Any]] = {}
            synset_names = sorted(
                name
                for name in archive.namelist()
                if name.endswith(".json")
                and name.startswith(("adj.", "adv.", "noun.", "verb."))
            )
            for name in synset_names:
                document = _json_object(archive.read(name), label=f"OEWN {name}")
                for synset_id in referenced_synsets & document.keys():
                    value = document[synset_id]
                    if not isinstance(value, dict):
                        raise SnapshotError(f"OEWN synset {synset_id!r} is invalid")
                    synsets[synset_id] = value
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise SnapshotError(f"cannot read OEWN archive {archive_path}: {exc}") from exc

    missing_synsets = sorted(referenced_synsets - synsets.keys())
    if missing_synsets:
        raise SnapshotError(
            f"OEWN archive is missing referenced synsets: {missing_synsets[:10]}"
        )

    candidates: dict[str, list[SenseCandidate]] = defaultdict(list)
    seen: set[tuple[str, str, str, int]] = set()
    for normalized_term, lemma, entry in selected_entries:
        for entry_pos, part in sorted(entry.items()):
            if not isinstance(part, dict):
                continue
            pronunciations = part.get("pronunciation", [])
            if not isinstance(pronunciations, list):
                raise SnapshotError(f"OEWN entry {lemma!r} has bad pronunciations")
            pronunciation = _metadata_text(
                next(
                    (
                        item["value"]
                        for item in pronunciations
                        if isinstance(item, dict) and item.get("value")
                    ),
                    "",
                ),
                field="pronunciation",
                maximum=255,
            )
            senses = part.get("sense", [])
            if not isinstance(senses, list):
                raise SnapshotError(f"OEWN entry {lemma!r} has invalid senses")
            for sense in senses:
                if not isinstance(sense, dict):
                    raise SnapshotError(f"OEWN entry {lemma!r} has an invalid sense")
                provider_sense_id = sense.get("id")
                provider_synset_id = sense.get("synset")
                if not isinstance(provider_sense_id, str) or not isinstance(
                    provider_synset_id, str
                ):
                    raise SnapshotError(
                        f"OEWN entry {lemma!r} has a sense without stable identifiers"
                    )
                synset = synsets[provider_synset_id]
                raw_definitions = synset.get("definition", [])
                raw_examples = synset.get("example", [])
                raw_members = synset.get("members", [])
                if not isinstance(raw_definitions, list) or not all(
                    isinstance(value, str) for value in raw_definitions
                ):
                    raise SnapshotError(
                        f"OEWN synset {provider_synset_id!r} has bad definitions"
                    )
                if not isinstance(raw_examples, list) or not all(
                    isinstance(value, (str, dict)) for value in raw_examples
                ):
                    raise SnapshotError(
                        f"OEWN synset {provider_synset_id!r} has bad examples"
                    )
                if not isinstance(raw_members, list) or not all(
                    isinstance(value, str) for value in raw_members
                ):
                    raise SnapshotError(
                        f"OEWN synset {provider_synset_id!r} has bad members"
                    )
                parsed_examples: list[ProviderExample] = []
                for example_index, raw_example in enumerate(raw_examples):
                    if isinstance(raw_example, str):
                        example_text = raw_example
                        example_source = ""
                    else:
                        example_text = raw_example.get("text")
                        example_source = raw_example.get("source", "")
                        if not isinstance(example_text, str) or not isinstance(
                            example_source, str
                        ):
                            raise SnapshotError(
                                f"OEWN synset {provider_synset_id!r} has a malformed "
                                "example object"
                            )
                    parsed_examples.append(
                        ProviderExample(
                            text=_provider_prose(
                                example_text,
                                field="example",
                                maximum=1000,
                            ),
                            provenance={
                                "example_index": example_index,
                                "kind": "example",
                                **(
                                    {"source": example_source} if example_source else {}
                                ),
                            },
                        )
                    )
                examples = tuple(parsed_examples)
                for definition_index, value in enumerate(raw_definitions):
                    key = (
                        config.id,
                        provider_sense_id,
                        provider_synset_id,
                        definition_index,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates[normalized_term].append(
                        SenseCandidate(
                            provider=config.id,
                            provider_sense_id=provider_sense_id,
                            provider_synset_id=provider_synset_id,
                            definition_index=definition_index,
                            part_of_speech=_metadata_text(
                                synset.get("partOfSpeech", entry_pos),
                                field="part_of_speech",
                                maximum=32,
                            ),
                            definition=_provider_prose(
                                value,
                                field="definition",
                                maximum=1000,
                            ),
                            examples=examples,
                            members=tuple(
                                collapse_whitespace(member) for member in raw_members
                            ),
                            pronunciation=pronunciation,
                            provenance={
                                "archive_sha256": config.archive_sha256,
                                "archive_url": config.archive_url,
                                "definition_index": definition_index,
                                "lemma": lemma,
                                "parser_version": config.parser_version,
                                "provider": config.id,
                                "provider_sense_id": provider_sense_id,
                                "provider_synset_id": provider_synset_id,
                                "version": config.version,
                            },
                        )
                    )

    return {
        term: tuple(
            sorted(
                values,
                key=lambda candidate: (
                    candidate.provider_sense_id,
                    candidate.provider_synset_id,
                    candidate.definition_index,
                ),
            )
        )
        for term, values in candidates.items()
    }


def load_http_cache(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load deterministic, resumable raw HTTP response snapshots."""
    if not path.exists():
        return {}
    records: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        with path.open("r", encoding="utf-8") as cache:
            for line_number, line in enumerate(cache, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise SnapshotError(f"cache line {line_number} must be an object")
                if set(value) != HTTP_CACHE_FIELDS:
                    raise SnapshotError(
                        f"cache line {line_number} fields must be exactly "
                        f"{sorted(HTTP_CACHE_FIELDS)}"
                    )
                provider = value.get("provider")
                normalized_term = value.get("normalized_term")
                payload = value.get("payload")
                payload_sha256 = value.get("payload_sha256")
                request_url = value.get("request_url")
                http_status = value.get("http_status")
                status = value.get("status")
                if (
                    not isinstance(provider, str)
                    or not provider
                    or not isinstance(normalized_term, str)
                    or not isinstance(payload, (dict, list))
                    or not isinstance(payload_sha256, str)
                    or not isinstance(request_url, str)
                    or not isinstance(http_status, int)
                    or isinstance(http_status, bool)
                    or status not in {"ok", "not-found"}
                ):
                    raise SnapshotError(f"cache line {line_number} is malformed")
                try:
                    term, identity = canonical_term(normalized_term)
                except ValueError as exc:
                    raise SnapshotError(
                        f"cache line {line_number} has an invalid normalized term"
                    ) from exc
                if term != normalized_term or identity != normalized_term:
                    raise SnapshotError(
                        f"cache line {line_number} term is not canonically normalized"
                    )
                parsed_url = urlsplit(request_url)
                if parsed_url.scheme != "https" or not parsed_url.netloc:
                    raise SnapshotError(
                        f"cache line {line_number} has an invalid request URL"
                    )
                expected_status = {200: "ok", 404: "not-found"}.get(http_status)
                if expected_status != status:
                    raise SnapshotError(
                        f"cache line {line_number} HTTP status does not match status"
                    )
                if sha256_bytes(canonical_json_bytes(payload)) != payload_sha256:
                    raise SnapshotError(
                        f"cache line {line_number} payload checksum does not match"
                    )
                key = (provider, normalized_term)
                if key in records:
                    raise SnapshotError(
                        f"cache has duplicate response for {provider}:{normalized_term}"
                    )
                records[key] = value
    except SnapshotError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot read HTTP cache {path}: {exc}") from exc
    return records


def _walk_free_dictionary_senses(
    senses: list[Any],
    *,
    path: tuple[int, ...] = (),
) -> Iterator[tuple[tuple[int, ...], dict[str, Any]]]:
    for index, value in enumerate(senses):
        if not isinstance(value, dict):
            raise SnapshotError("FreeDictionaryAPI response contains an invalid sense")
        sense_path = (*path, index)
        yield sense_path, value
        subsenses = value.get("subsenses", [])
        if subsenses is None:
            continue
        if not isinstance(subsenses, list):
            raise SnapshotError("FreeDictionaryAPI subsenses must be a list")
        yield from _walk_free_dictionary_senses(subsenses, path=sense_path)


def parse_free_dictionary_api(
    record: dict[str, Any],
    config: ProviderConfig,
) -> tuple[SenseCandidate, ...]:
    """Preserve definition/example pairing from FreeDictionaryAPI sense objects."""
    normalized_term = _response_normalized_term(
        record,
        provider="FreeDictionaryAPI",
    )
    payload = record["payload"]
    if not isinstance(payload, dict):
        raise SnapshotError("FreeDictionaryAPI payload must be an object")
    _validate_response_headword(
        payload.get("word"),
        normalized_term,
        field="FreeDictionaryAPI payload headword",
    )
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise SnapshotError("FreeDictionaryAPI payload must contain entries")
    source = payload.get("source")
    source_url = source.get("url", "") if isinstance(source, dict) else ""
    result: list[SenseCandidate] = []
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SnapshotError("FreeDictionaryAPI entry must be an object")
        part_of_speech = _metadata_text(
            entry.get("partOfSpeech", ""),
            field="part_of_speech",
            maximum=32,
        )
        pronunciations = entry.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            raise SnapshotError("FreeDictionaryAPI pronunciations must be a list")
        pronunciation = _metadata_text(
            next(
                (
                    item["text"]
                    for item in pronunciations
                    if isinstance(item, dict) and item.get("text")
                ),
                "",
            ),
            field="pronunciation",
            maximum=255,
        )
        senses = entry.get("senses", [])
        if not isinstance(senses, list):
            raise SnapshotError("FreeDictionaryAPI senses must be a list")
        for sense_path, sense in _walk_free_dictionary_senses(senses):
            definition = sense.get("definition")
            examples = sense.get("examples", [])
            quotes = sense.get("quotes", [])
            synonyms = sense.get("synonyms", [])
            if not isinstance(definition, str):
                continue
            if not isinstance(examples, list) or not all(
                isinstance(example, str) for example in examples
            ):
                raise SnapshotError("FreeDictionaryAPI examples must be strings")
            if not isinstance(quotes, list) or not all(
                isinstance(quote, dict) for quote in quotes
            ):
                raise SnapshotError("FreeDictionaryAPI quotes must be objects")
            if not isinstance(synonyms, list) or not all(
                isinstance(synonym, str) for synonym in synonyms
            ):
                raise SnapshotError("FreeDictionaryAPI synonyms must be strings")
            path_text = ".".join(str(index) for index in sense_path)
            sense_id = f"entry-{entry_index}-sense-{path_text}"
            parsed_examples = [
                ProviderExample(
                    text=_provider_prose(example, field="example", maximum=1000),
                    provenance={
                        "example_index": example_index,
                        "kind": "example",
                    },
                )
                for example_index, example in enumerate(examples)
            ]
            for quote_index, quote in enumerate(quotes):
                text = quote.get("text")
                reference = quote.get("reference", "")
                if not isinstance(text, str) or not isinstance(reference, str):
                    raise SnapshotError(
                        "FreeDictionaryAPI quote text and reference must be strings"
                    )
                if text.strip():
                    parsed_examples.append(
                        ProviderExample(
                            text=_provider_prose(
                                text,
                                field="example",
                                maximum=1000,
                            ),
                            provenance={
                                "kind": "sourced-quote",
                                "quote_index": quote_index,
                                **({"reference": reference} if reference else {}),
                            },
                        )
                    )
            result.append(
                SenseCandidate(
                    provider=config.id,
                    provider_sense_id=sense_id,
                    provider_synset_id="",
                    definition_index=0,
                    part_of_speech=part_of_speech,
                    definition=_provider_prose(
                        definition,
                        field="definition",
                        maximum=1000,
                    ),
                    examples=tuple(parsed_examples),
                    members=tuple(collapse_whitespace(value) for value in synonyms),
                    pronunciation=pronunciation,
                    provenance={
                        "parser_version": config.parser_version,
                        "payload_sha256": record["payload_sha256"],
                        "provider": config.id,
                        "provider_sense_id": sense_id,
                        "request_url": record["request_url"],
                        "source_url": source_url,
                    },
                )
            )
    return tuple(result)


def parse_dictionary_api_dev(
    record: dict[str, Any],
    config: ProviderConfig,
) -> tuple[SenseCandidate, ...]:
    """Parse the tertiary provider without crossing definition objects."""
    normalized_term = _response_normalized_term(
        record,
        provider="DictionaryAPI.dev",
    )
    payload = record["payload"]
    if not isinstance(payload, list):
        raise SnapshotError("DictionaryAPI.dev payload must be a list")
    if not payload:
        raise SnapshotError("DictionaryAPI.dev payload must contain a headword entry")
    result: list[SenseCandidate] = []
    for entry_index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise SnapshotError("DictionaryAPI.dev entry must be an object")
        _validate_response_headword(
            entry.get("word"),
            normalized_term,
            field=f"DictionaryAPI.dev entry {entry_index} headword",
        )
        pronunciation = _metadata_text(
            entry.get("phonetic", ""),
            field="pronunciation",
            maximum=255,
        )
        meanings = entry.get("meanings", [])
        if not isinstance(meanings, list):
            raise SnapshotError("DictionaryAPI.dev meanings must be a list")
        for meaning_index, meaning in enumerate(meanings):
            if not isinstance(meaning, dict):
                raise SnapshotError("DictionaryAPI.dev meaning must be an object")
            definitions = meaning.get("definitions", [])
            if not isinstance(definitions, list):
                raise SnapshotError("DictionaryAPI.dev definitions must be a list")
            for definition_index, definition in enumerate(definitions):
                if not isinstance(definition, dict) or not isinstance(
                    definition.get("definition"), str
                ):
                    continue
                example = definition.get("example")
                if example is not None and not isinstance(example, str):
                    raise SnapshotError(
                        "DictionaryAPI.dev example must be a string or null"
                    )
                synonyms = definition.get("synonyms", [])
                if not isinstance(synonyms, list) or not all(
                    isinstance(synonym, str) for synonym in synonyms
                ):
                    raise SnapshotError("DictionaryAPI.dev synonyms must be strings")
                examples = (
                    (
                        ProviderExample(
                            text=_provider_prose(
                                example,
                                field="example",
                                maximum=1000,
                            ),
                            provenance={"example_index": 0, "kind": "example"},
                        ),
                    )
                    if isinstance(example, str) and example.strip()
                    else ()
                )
                sense_id = (
                    f"entry-{entry_index}-meaning-{meaning_index}-"
                    f"definition-{definition_index}"
                )
                result.append(
                    SenseCandidate(
                        provider=config.id,
                        provider_sense_id=sense_id,
                        provider_synset_id="",
                        definition_index=0,
                        part_of_speech=_metadata_text(
                            meaning.get("partOfSpeech", ""),
                            field="part_of_speech",
                            maximum=32,
                        ),
                        definition=_provider_prose(
                            definition["definition"],
                            field="definition",
                            maximum=1000,
                        ),
                        examples=examples,
                        members=tuple(collapse_whitespace(value) for value in synonyms),
                        pronunciation=pronunciation,
                        provenance={
                            "parser_version": config.parser_version,
                            "payload_sha256": record["payload_sha256"],
                            "provider": config.id,
                            "provider_sense_id": sense_id,
                            "request_url": record["request_url"],
                        },
                    )
                )
    return tuple(result)


def load_cached_candidates(
    cache_path: Path,
    registry: dict[str, ProviderConfig],
) -> dict[str, tuple[SenseCandidate, ...]]:
    """Parse all checked HTTP snapshots through their pinned parser versions."""
    result: dict[str, list[SenseCandidate]] = defaultdict(list)
    for (provider, normalized_term), record in load_http_cache(cache_path).items():
        try:
            config = registry[provider]
        except KeyError as exc:
            raise SnapshotError(
                f"cache references unknown provider {provider!r}"
            ) from exc
        base_url = urlsplit(config.base_url)
        request_url = urlsplit(record["request_url"])
        if (
            request_url.scheme != base_url.scheme
            or request_url.netloc != base_url.netloc
            or request_url.query
            or request_url.fragment
            or not request_url.path.startswith(base_url.path)
        ):
            raise SnapshotError(
                f"cache request URL does not match provider {provider!r}"
            )
        requested_term = unquote(request_url.path[len(base_url.path) :])
        try:
            _display_term, requested_identity = canonical_term(requested_term)
        except ValueError as exc:
            raise SnapshotError(
                f"cache request URL has an invalid term for provider {provider!r}"
            ) from exc
        if requested_identity != normalized_term:
            raise SnapshotError(
                f"cache request URL term does not match {normalized_term!r}"
            )
        if record["status"] == "not-found":
            continue
        try:
            if provider == "freedictionaryapi-v1":
                candidates = parse_free_dictionary_api(record, config)
            elif provider == "dictionaryapi-dev-v2":
                candidates = parse_dictionary_api_dev(record, config)
            else:
                raise SnapshotError(f"no cached response parser for {provider!r}")
        except SnapshotError as exc:
            raise SnapshotError(
                f"invalid cached response for provider {provider!r}, "
                f"term {normalized_term!r}: {exc}"
            ) from exc
        result[normalized_term].extend(candidates)
    return {
        term: tuple(sorted(candidates, key=lambda candidate: candidate.selection_key))
        for term, candidates in result.items()
    }
