"""Small artifact factories shared by vocabulary persistence tests."""

import json
from pathlib import Path

from vocabulary.artifacts import CanonicalSense, CanonicalWord, corpus_jsonl_bytes
from vocabulary.example_matching import EXAMPLE_MATCH_POLICY_VERSION, match_example_text
from vocabulary.normalization import (
    canonical_json_bytes,
    canonical_term,
    sha256_bytes,
    stable_word_id,
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
