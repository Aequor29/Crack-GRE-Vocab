"""Retained source and canonical identity contract tests."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from vocabulary.exceptions import SourceAuditError
from vocabulary.normalization import canonical_term, sha256_bytes, sha256_file
from vocabulary.source import audit_source

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class VocabularySourceTests(SimpleTestCase):
    def test_missing_source_is_reported_as_a_domain_error(self):
        with self.assertRaisesRegex(SourceAuditError, "cannot parse GRE_word.csv"):
            audit_source(Path("missing-words.csv"), Path("missing-decisions.json"))

    def test_checked_audit_matches_the_retained_source(self):
        audit = audit_source(
            BACKEND_ROOT / "data/GRE_word.csv",
            BACKEND_ROOT / "data/vocabulary/duplicate-decisions.json",
        )
        checked_audit = json.loads(
            (BACKEND_ROOT / "data/vocabulary/source-audit.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(audit.as_dict(), checked_audit)
        self.assertEqual(len(audit.records), 3041)
        self.assertEqual(len(audit.words), 3034)
        self.assertEqual(len(audit.duplicate_groups), 7)

    def test_unreviewed_duplicate_collapse_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "words.csv"
            source.write_text(
                "word,definition\nLucid,clear\nlucid,easy to understand\n",
                encoding="utf-8",
            )
            decisions = root / "decisions.json"
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

            with self.assertRaisesRegex(
                SourceAuditError,
                "duplicate decisions do not match",
            ):
                audit_source(source, decisions)

    def test_audit_hashes_and_parses_the_same_source_bytes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "words.csv"
            original_content = b"word,definition\nLucid,clear\n"
            replacement_content = b"word,definition\nOpaque,unclear\n"
            source.write_bytes(original_content)
            decisions = root / "decisions.json"
            decisions.write_text(
                json.dumps(
                    {
                        "collapse": [],
                        "schema_version": 1,
                        "source_sha256": sha256_bytes(original_content),
                    }
                ),
                encoding="utf-8",
            )
            original_read_bytes = Path.read_bytes

            def read_then_replace(path: Path) -> bytes:
                content = original_read_bytes(path)
                if path == source:
                    source.write_bytes(replacement_content)
                return content

            with patch.object(Path, "read_bytes", autospec=True) as read_bytes:
                read_bytes.side_effect = read_then_replace
                audit = audit_source(source, decisions)

            self.assertEqual(audit.source_digest, sha256_bytes(original_content))
            self.assertEqual(
                [word.normalized_term for word in audit.words],
                ["lucid"],
            )
            self.assertNotEqual(audit.source_digest, sha256_file(source))

    def test_nfkc_casefold_identity_preserves_accents_and_enforces_length(self):
        display, identity = canonical_term("  CLIQUE\u0301  ")

        self.assertEqual(display, "CLIQUÉ")
        self.assertEqual(identity, "cliqué")
        self.assertNotEqual(identity, "clique")
        self.assertEqual(len(canonical_term("ß" * 64)[1]), 128)
        with self.assertRaisesRegex(ValueError, "after casefolding"):
            canonical_term("ß" * 65)
