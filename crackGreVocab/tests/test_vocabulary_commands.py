"""Behavior tests for the public vocabulary management commands."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TransactionTestCase
from vocabulary.builder import BuildInputs
from vocabulary.management.commands.audit_vocabulary_source import (
    Command as AuditCommand,
)
from vocabulary.management.commands.build_vocabulary_corpus import (
    Command as BuildCommand,
)
from vocabulary.management.commands.fetch_vocabulary_fallbacks import (
    Command as FetchCommand,
)
from vocabulary.management.commands.import_vocabulary_corpus import (
    Command as ImportCommand,
)
from vocabulary.management.commands.prepare_vocabulary_review import (
    Command as PrepareCommand,
)
from vocabulary.management.commands.refresh_vocabulary_snapshot import (
    Command as RefreshCommand,
)
from vocabulary.normalization import sha256_bytes, sha256_file
from vocabulary.providers import load_http_cache

from tests.vocabulary_helpers import (
    canonical_word,
    provider_registry_document,
    write_minimal_build_inputs,
    write_test_artifact,
)


class _Response:
    status = 200

    def __init__(self, payload: bytes):
        self.payload = payload
        self.consumed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size: int | None = None):
        if self.consumed:
            return b""
        self.consumed = True
        return self.payload


def _build_input_arguments(inputs: BuildInputs) -> list[str]:
    return [
        "--source",
        str(inputs.source_path),
        "--duplicate-decisions",
        str(inputs.duplicate_decisions_path),
        "--providers",
        str(inputs.provider_registry_path),
        "--oewn-archive",
        str(inputs.oewn_archive_path),
        "--sense-decisions",
        str(inputs.sense_decisions_path),
        "--editorial-overrides",
        str(inputs.editorial_overrides_path),
        "--fallback-cache",
        str(inputs.fallback_cache_path),
    ]


class VocabularyCommandTests(SimpleTestCase):
    def test_audit_command_records_the_actual_source_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "custom.csv"
            source.write_text("word,definition\nLucid,clear\n", encoding="utf-8")
            decisions = root / "duplicates.json"
            decisions.write_text(
                json.dumps(
                    {
                        "collapse": [],
                        "schema_version": 1,
                        "source_sha256": sha256_file(source),
                    }
                ),
                encoding="utf-8",
            )
            audit_path = root / "audit.json"

            AuditCommand().run_from_argv(
                [
                    "manage.py",
                    "audit_vocabulary_source",
                    "--source",
                    str(source),
                    "--duplicate-decisions",
                    str(decisions),
                    "--output",
                    str(audit_path),
                ]
            )
            audit = json.loads(audit_path.read_text(encoding="utf-8"))

        self.assertEqual(audit["source"]["path"], str(source))

    def test_fetch_command_persists_a_resumable_provider_response(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            providers = root / "providers.json"
            providers.write_text(
                json.dumps(provider_registry_document("0" * 64)),
                encoding="utf-8",
            )
            cache = root / "fallback.jsonl"
            output = StringIO()

            with patch(
                "vocabulary.fetching.urlopen",
                return_value=_Response(
                    json.dumps({"entries": [], "word": "Lucid"}).encode()
                ),
            ):
                FetchCommand(stdout=output).run_from_argv(
                    [
                        "manage.py",
                        "fetch_vocabulary_fallbacks",
                        "--providers",
                        str(providers),
                        "--provider",
                        "freedictionaryapi-v1",
                        "--cache",
                        str(cache),
                        "--term",
                        "Lucid",
                        "--limit",
                        "1",
                        "--rate-state",
                        str(root / "rate-limit"),
                    ]
                )
            stored = load_http_cache(cache)

        self.assertEqual(set(stored), {("freedictionaryapi-v1", "lucid")})
        self.assertEqual(stored[("freedictionaryapi-v1", "lucid")]["status"], "ok")

    def test_refresh_command_downloads_the_pinned_archive(self):
        archive_content = b"pinned archive bytes"
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            providers = root / "providers.json"
            providers.write_text(
                json.dumps(
                    provider_registry_document(sha256_bytes(archive_content))
                ),
                encoding="utf-8",
            )
            destination = root / "oewn.zip"
            output = StringIO()

            with patch(
                "vocabulary.fetching.urlopen",
                return_value=_Response(archive_content),
            ):
                RefreshCommand(stdout=output).run_from_argv(
                    [
                        "manage.py",
                        "refresh_vocabulary_snapshot",
                        "--providers",
                        str(providers),
                        "--destination",
                        str(destination),
                    ]
                )

            self.assertEqual(destination.read_bytes(), archive_content)

    def test_prepare_command_writes_the_actionable_queue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = write_minimal_build_inputs(root)
            queue_path = root / "review-queue.json"
            output = StringIO()

            PrepareCommand(stdout=output).run_from_argv(
                [
                    "manage.py",
                    "prepare_vocabulary_review",
                    *_build_input_arguments(inputs),
                    "--output",
                    str(queue_path),
                ]
            )
            queue = json.loads(queue_path.read_text(encoding="utf-8"))

        self.assertEqual(queue["items"], [])

    def test_build_command_writes_an_immutable_release(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = write_minimal_build_inputs(root)
            release = root / "m1-test"
            output = StringIO()

            BuildCommand(stdout=output).run_from_argv(
                [
                    "manage.py",
                    "build_vocabulary_corpus",
                    *_build_input_arguments(inputs),
                    "--corpus-version",
                    "m1-test",
                    "--output-directory",
                    str(release),
                ]
            )
            manifest = json.loads(
                (release / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(manifest["corpus_version"], "m1-test")


class VocabularyImportCommandTests(TransactionTestCase):
    def test_import_command_writes_the_public_import_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = write_test_artifact(
                root / "m1-test",
                version="m1-test",
                words=(canonical_word("Lucid"),),
            )
            report_path = root / "import-report.json"
            output = StringIO()

            ImportCommand(stdout=output).run_from_argv(
                [
                    "manage.py",
                    "import_vocabulary_corpus",
                    str(manifest),
                    "--report",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertTrue(report["created_corpus"])
        self.assertEqual(report["version"], "m1-test")
