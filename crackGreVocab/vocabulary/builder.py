"""Offline orchestration for review queues and immutable corpus releases."""

import os
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import (
    CORPUS_SCHEMA_VERSION,
    CanonicalWord,
    corpus_jsonl_bytes,
)
from .decisions import (
    EditorialWord,
    ProviderWordDecision,
    load_editorial_overrides,
    load_sense_decisions,
)
from .exceptions import CorpusBuildError, SnapshotError, SourceAuditError
from .normalization import (
    canonical_json_bytes,
    canonical_version,
    sha256_bytes,
    sha256_file,
)
from .providers import (
    SenseCandidate,
    load_cached_candidates,
    load_oewn_candidates,
    load_provider_registry,
)
from .resolution import build_corpus_words
from .review_queue import build_review_queue, write_review_queue
from .source import SourceAudit, audit_source


@dataclass(frozen=True)
class BuildInputs:
    """Every checked local input required by review and release construction."""

    source_path: Path
    duplicate_decisions_path: Path
    provider_registry_path: Path
    oewn_archive_path: Path
    sense_decisions_path: Path
    editorial_overrides_path: Path
    fallback_cache_path: Path


@dataclass(frozen=True)
class BuildContext:
    """Validated local inputs ready for queue generation or release resolution."""

    audit: SourceAudit
    candidates: dict[str, tuple[SenseCandidate, ...]]
    selections: dict[str, ProviderWordDecision]
    overrides: dict[str, EditorialWord]


def _load_build_context(inputs: BuildInputs) -> BuildContext:
    try:
        audit = audit_source(inputs.source_path, inputs.duplicate_decisions_path)
        registry = load_provider_registry(inputs.provider_registry_path)
        oewn_config = registry["oewn-2025"]
        source_terms = {word.normalized_term for word in audit.words}
        candidates: dict[str, list[SenseCandidate]] = defaultdict(list)
        for term, values in load_oewn_candidates(
            inputs.oewn_archive_path,
            oewn_config,
            source_terms,
        ).items():
            candidates[term].extend(values)
        for term, values in load_cached_candidates(
            inputs.fallback_cache_path,
            registry,
        ).items():
            if term not in source_terms:
                raise CorpusBuildError(
                    f"fallback cache contains non-source term {term!r}"
                )
            candidates[term].extend(values)
    except (SourceAuditError, SnapshotError, KeyError) as exc:
        raise CorpusBuildError(str(exc)) from exc

    selections = load_sense_decisions(
        inputs.sense_decisions_path,
        source_digest=audit.source_digest,
    )
    overrides = load_editorial_overrides(
        inputs.editorial_overrides_path,
        source_digest=audit.source_digest,
    )
    unknown_decisions = sorted((set(selections) | set(overrides)) - source_terms)
    if unknown_decisions:
        raise CorpusBuildError(
            f"reviewed content contains non-source terms: {unknown_decisions[:10]}"
        )
    overlap = sorted(set(selections) & set(overrides))
    if overlap:
        raise CorpusBuildError(
            f"terms cannot have both provider selections and overrides: {overlap[:10]}"
        )

    priorities = {provider.id: provider.priority for provider in registry.values()}
    frozen_candidates = {
        term: tuple(
            sorted(
                values,
                key=lambda candidate: (
                    priorities[candidate.provider],
                    candidate.selection_key,
                ),
            )
        )
        for term, values in candidates.items()
    }
    return BuildContext(
        audit=audit,
        candidates=frozen_candidates,
        selections=selections,
        overrides=overrides,
    )


def prepare_review_queue(inputs: BuildInputs, *, output_path: Path) -> dict[str, Any]:
    """Validate local inputs, generate the current queue, and replace it atomically."""
    context = _load_build_context(inputs)
    document = build_review_queue(
        context.audit,
        context.candidates,
        context.selections,
        context.overrides,
    )
    write_review_queue(output_path, document)
    return document


def _input_digests(inputs: BuildInputs) -> dict[str, str]:
    paths = {
        "source_sha256": inputs.source_path,
        "duplicate_decisions_sha256": inputs.duplicate_decisions_path,
        "editorial_overrides_sha256": inputs.editorial_overrides_path,
        "oewn_archive_sha256": inputs.oewn_archive_path,
        "provider_registry_sha256": inputs.provider_registry_path,
        "sense_decisions_sha256": inputs.sense_decisions_path,
    }
    if inputs.fallback_cache_path.exists():
        paths["fallback_cache_sha256"] = inputs.fallback_cache_path
    values: dict[str, str] = {}
    for label, path in paths.items():
        try:
            values[label] = sha256_file(path)
        except OSError as exc:
            raise CorpusBuildError(
                f"cannot hash build input {label} at {path}: {exc}"
            ) from exc
    return values


def build_manifest(
    *,
    version: str,
    audit: SourceAudit,
    words: tuple[CanonicalWord, ...],
    corpus_digest: str,
    input_digests: Mapping[str, str],
) -> dict[str, Any]:
    """Build the canonical manifest for one resolved corpus release."""
    try:
        corpus_version = canonical_version(version)
    except (TypeError, ValueError) as exc:
        raise CorpusBuildError(str(exc)) from exc
    return {
        "corpus": {
            "file": "corpus.jsonl",
            "sense_count": sum(len(word.senses) for word in words),
            "sha256": corpus_digest,
            "word_count": len(words),
        },
        "corpus_version": corpus_version,
        "inputs": dict(input_digests),
        "schema_version": CORPUS_SCHEMA_VERSION,
        "source": {
            "canonical_word_count": len(audit.words),
            "row_count": len(audit.records),
            "sha256": audit.source_digest,
        },
    }


def write_artifact_directory(
    output_directory: Path,
    *,
    corpus_content: bytes,
    manifest_content: bytes,
) -> bool:
    """Create an immutable version directory; identical reruns are a no-op."""
    if output_directory.exists():
        try:
            unchanged = (
                output_directory / "corpus.jsonl"
            ).read_bytes() == corpus_content and (
                output_directory / "manifest.json"
            ).read_bytes() == manifest_content
        except OSError:
            unchanged = False
        if unchanged:
            return False
        raise CorpusBuildError(
            "immutable corpus directory already exists with different content: "
            f"{output_directory}"
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(
        tempfile.mkdtemp(
            dir=output_directory.parent,
            prefix=f".{output_directory.name}.",
        )
    )
    try:
        (temporary_directory / "corpus.jsonl").write_bytes(corpus_content)
        (temporary_directory / "manifest.json").write_bytes(manifest_content)
        os.replace(temporary_directory, output_directory)
    except BaseException:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    return True


def build_artifacts(
    inputs: BuildInputs,
    *,
    version: str,
    output_directory: Path,
) -> bool:
    """Build one immutable corpus release from checksum-verified local inputs."""
    digests = _input_digests(inputs)
    context = _load_build_context(inputs)
    if context.audit.source_digest != digests["source_sha256"]:
        raise CorpusBuildError("source digest changed before it was loaded")
    words = build_corpus_words(
        context.audit,
        context.candidates,
        context.selections,
        context.overrides,
    )
    corpus_content = corpus_jsonl_bytes(words)
    manifest = build_manifest(
        version=version,
        audit=context.audit,
        words=words,
        corpus_digest=sha256_bytes(corpus_content),
        input_digests={
            label: digest
            for label, digest in digests.items()
            if label != "source_sha256"
        },
    )
    return write_artifact_directory(
        output_directory,
        corpus_content=corpus_content,
        manifest_content=canonical_json_bytes(manifest),
    )
