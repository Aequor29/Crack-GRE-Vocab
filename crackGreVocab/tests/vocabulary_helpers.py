"""Small artifact factories shared by vocabulary persistence tests."""

import json
import zipfile
from pathlib import Path

from vocabulary.artifacts import CanonicalSense, CanonicalWord, corpus_jsonl_bytes
from vocabulary.builder import BuildInputs
from vocabulary.example_matching import EXAMPLE_MATCH_POLICY_VERSION, match_example_text
from vocabulary.normalization import (
    canonical_json_bytes,
    canonical_term,
    sha256_bytes,
    sha256_file,
    stable_word_id,
)


def provider_registry_document(
    oewn_archive_sha256: str,
    *,
    oewn_archive_url: str = "https://example.test/oewn.zip",
) -> dict[str, object]:
    """Return the complete mutable provider pins used by test pipelines."""
    return {
        "providers": {
            "dictionaryapi-dev-v2": {
                "base_url": "https://example.test/dictionary/",
                "minimum_interval_seconds": 1.0,
            },
            "freedictionaryapi-v1": {
                "base_url": "https://example.test/free/",
                "minimum_interval_seconds": 3.6,
                "rate_limit_per_hour": 1000,
            },
            "oewn-2025": {
                "archive_sha256": oewn_archive_sha256,
                "archive_url": oewn_archive_url,
            },
        },
        "schema_version": 2,
    }


def write_minimal_build_inputs(root: Path) -> BuildInputs:
    """Write a complete one-word offline build fixture and return its paths."""
    source = root / "source.csv"
    duplicates = root / "duplicates.json"
    providers = root / "providers.json"
    oewn_archive = root / "oewn.zip"
    sense_decisions = root / "senses.json"
    editorial_overrides = root / "overrides.json"
    fallback_cache = root / "fallback.jsonl"

    source.write_text(
        "word,definition\nLucid,clear and easy to understand\n",
        encoding="utf-8",
    )
    source_digest = sha256_file(source)
    duplicates.write_text(
        json.dumps(
            {
                "collapse": [],
                "schema_version": 1,
                "source_sha256": source_digest,
            }
        ),
        encoding="utf-8",
    )
    with zipfile.ZipFile(oewn_archive, "w") as archive:
        archive.writestr(
            "entries-l.json",
            json.dumps(
                {
                    "lucid": {
                        "a": {
                            "sense": [
                                {"id": "lucid%5:00", "synset": "0001-a"}
                            ]
                        }
                    }
                }
            ),
        )
        archive.writestr(
            "adj.test.json",
            json.dumps(
                {
                    "0001-a": {
                        "definition": ["clear and easy to understand"],
                        "example": ["A lucid explanation settled the question."],
                        "members": ["lucid"],
                        "partOfSpeech": "adjective",
                    }
                }
            ),
        )
    providers.write_text(
        json.dumps(provider_registry_document(sha256_file(oewn_archive))),
        encoding="utf-8",
    )
    for path, collection in (
        (sense_decisions, "selections"),
        (editorial_overrides, "words"),
    ):
        path.write_text(
            json.dumps(
                {
                    collection: {},
                    "schema_version": 4,
                    "source_sha256": source_digest,
                }
            ),
            encoding="utf-8",
        )
    return BuildInputs(
        source_path=source,
        duplicate_decisions_path=duplicates,
        provider_registry_path=providers,
        oewn_archive_path=oewn_archive,
        sense_decisions_path=sense_decisions,
        editorial_overrides_path=editorial_overrides,
        fallback_cache_path=fallback_cache,
    )


def canonical_word(
    term: str,
    *,
    position: int = 1,
    definition: str = "clear and precise",
    example: str = "Her explanation was lucid.",
) -> CanonicalWord:
    display_term, normalized_term = canonical_term(term)
    matched = match_example_text(normalized_term, "adjective", example)
    if matched is None:
        raise ValueError("fixture example must contain its headword")
    return CanonicalWord(
        position=position,
        word_id=stable_word_id(normalized_term),
        term=display_term,
        normalized_term=normalized_term,
        pronunciation="",
        senses=(
            CanonicalSense(
                position=1,
                part_of_speech="adjective",
                definition=definition,
                example=example,
                provenance={
                    "example_headword_match": {
                        "form": matched.form,
                        "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
                        "surface": matched.surface,
                    },
                    "fixture": "v1",
                    "provider": "test-provider",
                },
            ),
        ),
    )


def write_test_artifact(
    directory: Path,
    *,
    version: str,
    words: tuple[CanonicalWord, ...],
) -> Path:
    directory.mkdir(parents=True)
    corpus_content = corpus_jsonl_bytes(words)
    (directory / "corpus.jsonl").write_bytes(corpus_content)
    manifest = {
        "corpus": {
            "file": "corpus.jsonl",
            "sense_count": sum(len(word.senses) for word in words),
            "sha256": sha256_bytes(corpus_content),
            "word_count": len(words),
        },
        "corpus_version": version,
        "inputs": {"fixture_sha256": "0" * 64},
        "schema_version": 1,
        "source": {
            "canonical_word_count": len(words),
            "row_count": len(words),
            "sha256": "1" * 64,
        },
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return manifest_path


def rewrite_corpus_word(manifest_path: Path, **changes: object) -> None:
    """Rewrite a one-word fixture while keeping its manifest digest coherent."""
    corpus_path = manifest_path.parent / "corpus.jsonl"
    document = json.loads(corpus_path.read_text(encoding="utf-8"))
    document.update(changes)
    corpus_content = canonical_json_bytes(document)
    corpus_path.write_bytes(corpus_content)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["corpus"]["sha256"] = sha256_bytes(corpus_content)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
