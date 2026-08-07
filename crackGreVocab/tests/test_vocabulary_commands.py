"""Management-command parser smoke tests."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from vocabulary.management.commands.audit_vocabulary_source import (
    Command as AuditCommand,
)
from vocabulary.management.commands.build_vocabulary_corpus import (
    Command as BuildCommand,
)
from vocabulary.management.commands.fetch_vocabulary_fallbacks import (
    Command as FetchCommand,
)
from vocabulary.normalization import sha256_file
from vocabulary.providers import ProviderConfig


class VocabularyCommandTests(SimpleTestCase):
    def test_build_command_uses_a_non_conflicting_corpus_version_option(self):
        output = StringIO()
        command = BuildCommand(stdout=output)
        argv = [
            "manage.py",
            "build_vocabulary_corpus",
            "--source",
            "words.csv",
            "--duplicate-decisions",
            "duplicates.json",
            "--providers",
            "providers.json",
            "--oewn-archive",
            "oewn.zip",
            "--sense-decisions",
            "senses.json",
            "--editorial-overrides",
            "overrides.json",
            "--fallback-cache",
            "fallback.jsonl",
            "--corpus-version",
            "m1-v1",
            "--output-directory",
            "versions/m1-v1",
        ]

        with patch(
            "vocabulary.management.commands.build_vocabulary_corpus.build_artifacts",
            return_value=False,
        ) as build_artifacts:
            command.run_from_argv(argv)

        self.assertEqual(build_artifacts.call_args.kwargs["version"], "m1-v1")
        self.assertIn("already identical", output.getvalue())

    def test_fetch_command_passes_the_shared_rate_state_path(self):
        output = StringIO()
        command = FetchCommand(stdout=output)
        config = ProviderConfig(
            id="freedictionaryapi-v1",
            kind="http-json",
            priority=2,
            parser_version=1,
            base_url="https://example.test/",
            rate_limit_per_hour=1000,
            minimum_interval_seconds=3.6,
        )
        argv = [
            "manage.py",
            "fetch_vocabulary_fallbacks",
            "--providers",
            "providers.json",
            "--provider",
            "freedictionaryapi-v1",
            "--cache",
            "fallback.jsonl",
            "--term",
            "Lucid",
            "--limit",
            "1",
            "--rate-state",
            ".cache/vocabulary/free.rate-limit",
        ]

        with (
            patch(
                "vocabulary.management.commands.fetch_vocabulary_fallbacks."
                "load_provider_registry",
                return_value={config.id: config},
            ),
            patch(
                "vocabulary.management.commands.fetch_vocabulary_fallbacks."
                "fetch_http_fallbacks",
                return_value=(1, 0),
            ) as fetch,
        ):
            command.run_from_argv(argv)

        self.assertEqual(
            fetch.call_args.kwargs["rate_state_path"],
            Path(".cache/vocabulary/free.rate-limit"),
        )

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
