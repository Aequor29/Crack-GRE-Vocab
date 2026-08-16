"""Canonical artifact validation and immutability tests."""

import json
import tempfile
import uuid
from pathlib import Path

from django.test import SimpleTestCase
from vocabulary.artifacts import load_corpus
from vocabulary.builder import write_artifact_directory
from vocabulary.exceptions import CorpusBuildError, CorpusImportError
from vocabulary.normalization import canonical_json_bytes, sha256_bytes
from vocabulary.source import audit_source

from tests.vocabulary_helpers import (
    canonical_word,
    rewrite_corpus_word,
    write_test_artifact,
)


class VocabularyArtifactTests(SimpleTestCase):
    def test_loader_rejects_a_forged_example_match_after_digest_recalculation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            corpus_path = manifest_path.parent / "corpus.jsonl"
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
            corpus["senses"][0]["example"] = "The explanation was clear."
            corpus["senses"][0]["provenance"]["example_headword_match"] = {
                "form": "exact",
                "policy_version": 2,
                "surface": "lucid",
            }
            corpus_content = canonical_json_bytes(corpus)
            corpus_path.write_bytes(corpus_content)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["corpus"]["sha256"] = sha256_bytes(corpus_content)
            manifest_path.write_bytes(canonical_json_bytes(manifest))

            with self.assertRaisesRegex(CorpusImportError, "does not contain"):
                load_corpus(manifest_path)

    def test_loader_rejects_forged_match_provenance_for_valid_example(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            corpus_path = manifest_path.parent / "corpus.jsonl"
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
            corpus["senses"][0]["provenance"]["example_headword_match"] = {
                "form": "exact",
                "policy_version": 3,
                "surface": "forged",
            }
            corpus_content = canonical_json_bytes(corpus)
            corpus_path.write_bytes(corpus_content)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["corpus"]["sha256"] = sha256_bytes(corpus_content)
            manifest_path.write_bytes(canonical_json_bytes(manifest))

            with self.assertRaisesRegex(CorpusImportError, "does not match its text"):
                load_corpus(manifest_path)

    def test_loader_rejects_a_non_deterministic_word_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            rewrite_corpus_word(manifest, word_id=str(uuid.uuid4()))

            with self.assertRaisesRegex(CorpusImportError, "stable identity"):
                load_corpus(manifest)

    def test_loader_rejects_content_that_does_not_match_the_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            with (manifest.parent / "corpus.jsonl").open("ab") as corpus:
                corpus.write(b" ")

            with self.assertRaisesRegex(CorpusImportError, "digest"):
                load_corpus(manifest)

    def test_loader_rejects_noncanonical_bytes_with_a_recomputed_digest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            rewrite_corpus_word(manifest, position=True)

            with self.assertRaisesRegex(CorpusImportError, "bytes are not canonical"):
                load_corpus(manifest)

    def test_loader_rejects_impossible_source_row_count(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(
                    canonical_word(
                        "Alpha",
                        position=1,
                        example="Alpha appears here.",
                    ),
                    canonical_word(
                        "Beta",
                        position=2,
                        example="Beta appears here.",
                    ),
                ),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source"]["row_count"] = 1
            manifest_path.write_bytes(canonical_json_bytes(manifest))

            with self.assertRaisesRegex(
                CorpusImportError,
                "row_count cannot be smaller",
            ):
                load_corpus(manifest_path)

    def test_loader_rejects_an_absolute_corpus_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["corpus"]["file"] = str(
                (manifest_path.parent / "corpus.jsonl").resolve()
            )
            manifest_path.write_bytes(canonical_json_bytes(manifest))

            with self.assertRaisesRegex(CorpusImportError, "relative path"):
                load_corpus(manifest_path)

    def test_loader_wraps_an_invalid_corpus_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["corpus"]["file"] = "\u0000"
            manifest_path.write_bytes(canonical_json_bytes(manifest))

            with self.assertRaisesRegex(
                CorpusImportError,
                "invalid manifest corpus file path",
            ):
                load_corpus(manifest_path)

    def test_version_directory_allows_only_an_identical_rerun(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "v1"

            self.assertTrue(
                write_artifact_directory(
                    output,
                    corpus_content=b'{"word":"lucid"}\n',
                    manifest_content=b'{"version":"v1"}\n',
                )
            )
            self.assertFalse(
                write_artifact_directory(
                    output,
                    corpus_content=b'{"word":"lucid"}\n',
                    manifest_content=b'{"version":"v1"}\n',
                )
            )
            with self.assertRaisesRegex(CorpusBuildError, "different content"):
                write_artifact_directory(
                    output,
                    corpus_content=b'{"word":"changed"}\n',
                    manifest_content=b'{"version":"v1"}\n',
                )


class CheckedCorpusArtifactTests(SimpleTestCase):
    def test_milestone_one_release_matches_the_audited_source_membership(self):
        backend_root = Path(__file__).resolve().parents[1]
        artifact = load_corpus(
            backend_root
            / "data/vocabulary/versions/m1-v2/manifest.json"
        )
        audit = audit_source(
            backend_root / "data/GRE_word.csv",
            backend_root / "data/vocabulary/duplicate-decisions.json",
        )

        self.assertEqual(
            tuple(word.normalized_term for word in artifact.words),
            tuple(word.normalized_term for word in audit.words),
        )
        self.assertEqual(artifact.source_digest, audit.source_digest)
        self.assertTrue(
            all(word.senses for word in artifact.words),
            "every source word must retain learning content",
        )
