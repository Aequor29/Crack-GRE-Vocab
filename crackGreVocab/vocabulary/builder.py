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
    load_editorial_overrides_snapshot,
    load_sense_decisions_snapshot,
)
from .exceptions import CorpusBuildError, SnapshotError, SourceAuditError
from .files import FileSnapshot
from .normalization import (
    canonical_json_bytes,
    canonical_version,
    sha256_bytes,
)
from .providers import (
    SenseCandidate,
    load_cached_candidates_snapshot,
    load_oewn_candidates_snapshot,
    load_provider_registry_snapshot,
)
from .resolution import build_corpus_words
from .review_queue import build_review_queue, write_review_queue
from .source import SourceAudit, audit_source_snapshots


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


@dataclass(frozen=True)
class BuildInputSnapshots:
    """Exact bytes consumed from every checked input in one build attempt."""

    source: FileSnapshot
    duplicate_decisions: FileSnapshot
    provider_registry: FileSnapshot
    oewn_archive: FileSnapshot
    sense_decisions: FileSnapshot
    editorial_overrides: FileSnapshot
    fallback_cache: FileSnapshot | None

    def manifest_digests(self) -> dict[str, str]:
        """Return manifest hashes derived from these already-consumed bytes."""
        digests = {
            "duplicate_decisions_sha256": self.duplicate_decisions.sha256,
            "editorial_overrides_sha256": self.editorial_overrides.sha256,
            "oewn_archive_sha256": self.oewn_archive.sha256,
            "provider_registry_sha256": self.provider_registry.sha256,
            "sense_decisions_sha256": self.sense_decisions.sha256,
        }
        if self.fallback_cache is not None:
            digests["fallback_cache_sha256"] = self.fallback_cache.sha256
        return digests


def _read_build_inputs(inputs: BuildInputs) -> BuildInputSnapshots:
    required_paths = {
        "source": inputs.source_path,
        "duplicate decisions": inputs.duplicate_decisions_path,
        "provider registry": inputs.provider_registry_path,
        "OEWN archive": inputs.oewn_archive_path,
        "sense decisions": inputs.sense_decisions_path,
        "editorial overrides": inputs.editorial_overrides_path,
    }
    snapshots: dict[str, FileSnapshot] = {}
    for label, path in required_paths.items():
        try:
            snapshots[label] = FileSnapshot.read(path)
        except OSError as exc:
            raise CorpusBuildError(
                f"cannot read build input {label} at {path}: {exc}"
            ) from exc
    try:
        fallback_cache = (
            FileSnapshot.read(inputs.fallback_cache_path)
            if inputs.fallback_cache_path.exists()
            else None
        )
    except OSError as exc:
        raise CorpusBuildError(
            f"cannot read fallback cache at {inputs.fallback_cache_path}: {exc}"
        ) from exc
    return BuildInputSnapshots(
        source=snapshots["source"],
        duplicate_decisions=snapshots["duplicate decisions"],
        provider_registry=snapshots["provider registry"],
        oewn_archive=snapshots["OEWN archive"],
        sense_decisions=snapshots["sense decisions"],
        editorial_overrides=snapshots["editorial overrides"],
        fallback_cache=fallback_cache,
    )


def _load_build_context(inputs: BuildInputSnapshots) -> BuildContext:
    try:
        audit = audit_source_snapshots(inputs.source, inputs.duplicate_decisions)
        registry = load_provider_registry_snapshot(inputs.provider_registry)
        oewn_config = registry["oewn-2025"]
        source_terms = {word.normalized_term for word in audit.words}
        candidates: dict[str, list[SenseCandidate]] = defaultdict(list)
        for term, values in load_oewn_candidates_snapshot(
            inputs.oewn_archive,
            oewn_config,
            source_terms,
        ).items():
            candidates[term].extend(values)
        for term, values in load_cached_candidates_snapshot(
            inputs.fallback_cache,
            registry,
        ).items():
            if term not in source_terms:
                raise CorpusBuildError(
                    f"fallback cache contains non-source term {term!r}"
                )
            candidates[term].extend(values)
    except (SourceAuditError, SnapshotError, KeyError) as exc:
        raise CorpusBuildError(str(exc)) from exc

    selections = load_sense_decisions_snapshot(
        inputs.sense_decisions,
        source_digest=audit.source_digest,
    )
    overrides = load_editorial_overrides_snapshot(
        inputs.editorial_overrides,
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
    context = _load_build_context(_read_build_inputs(inputs))
    document = build_review_queue(
        context.audit,
        context.candidates,
        context.selections,
        context.overrides,
    )
    write_review_queue(output_path, document)
    return document


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
    snapshots = _read_build_inputs(inputs)
    context = _load_build_context(snapshots)
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
        input_digests=snapshots.manifest_digests(),
    )
    return write_artifact_directory(
        output_directory,
        corpus_content=corpus_content,
        manifest_content=canonical_json_bytes(manifest),
    )
