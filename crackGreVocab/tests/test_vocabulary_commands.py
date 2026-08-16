"""Behavior tests for the public vocabulary management commands."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from vocabulary.management.commands.audit_vocabulary_source import (
    Command as AuditCommand,
)
from vocabulary.management.commands.fetch_vocabulary_fallbacks import (
    Command as FetchCommand,
)
from vocabulary.normalization import sha256_file
from vocabulary.providers import load_http_cache


class _Response:
    status = 200

    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


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
                json.dumps(
                    {
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
                                "archive_sha256": "0" * 64,
                                "archive_url": "https://example.test/oewn.zip",
                            },
                        },
                        "schema_version": 2,
                    }
                ),
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
        self.assertIn("cached 1 response", output.getvalue())
