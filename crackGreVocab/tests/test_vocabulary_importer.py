"""Atomic, idempotent vocabulary import tests against PostgreSQL."""

import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TransactionTestCase
from vocabulary.artifacts import load_corpus
from vocabulary.exceptions import CorpusImportError
from vocabulary.importer import _validate_existing_corpus, import_corpus
from vocabulary.models import (
    CorpusEntry,
    CorpusVersion,
    VocabularySense,
    VocabularyWord,
)

from tests.vocabulary_helpers import canonical_word, write_test_artifact


class VocabularyImporterTests(TransactionTestCase):
    def test_idempotency_validation_uses_a_constant_query_count(self):
        terms = (
            "Alpha",
            "Bravo",
            "Charlie",
            "Delta",
            "Echo",
            "Foxtrot",
            "Golf",
            "Hotel",
            "India",
            "Juliet",
        )
        words = tuple(
            canonical_word(
                term,
                position=position,
                example=f"The example includes {term}.",
            )
            for position, term in enumerate(terms, start=1)
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=words,
            )
            import_corpus(manifest)
            artifact = load_corpus(manifest)
            existing = CorpusVersion.objects.get(version="v1")

            with self.assertNumQueries(2):
                _validate_existing_corpus(existing, artifact)

    def test_fresh_import_is_active_and_an_identical_rerun_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )

            first = import_corpus(manifest)
            repeated = import_corpus(manifest)

        self.assertTrue(first.created_corpus)
        self.assertTrue(first.activated)
        self.assertEqual(first.created_words, 1)
        self.assertFalse(repeated.created_corpus)
        self.assertFalse(repeated.activated)
        self.assertEqual(CorpusVersion.objects.filter(is_active=True).count(), 1)
        self.assertEqual(CorpusEntry.objects.count(), 1)
        self.assertEqual(VocabularySense.objects.count(), 1)

    def test_every_definition_and_example_persists_and_late_tampering_fails(self):
        lucid = canonical_word(
            "Lucid",
            position=1,
            definition="clear and easy to understand",
            example="Her lucid explanation resolved the confusion.",
        )
        lucid = replace(
            lucid,
            senses=(
                lucid.senses[0],
                replace(
                    lucid.senses[0],
                    position=2,
                    definition="bright or luminous",
                    example="A lucid glow filled the room.",
                ),
            ),
        )
        opaque = canonical_word(
            "Opaque",
            position=2,
            definition="not transparent",
            example="The opaque glass blocked the view.",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(lucid, opaque),
            )
            artifact = load_corpus(manifest)
            report = import_corpus(manifest)

            expected_content = [
                (
                    word.position,
                    sense.position,
                    sense.definition,
                    sense.example,
                )
                for word in artifact.words
                for sense in word.senses
            ]
            stored_content = list(
                VocabularySense.objects.order_by("entry__position", "position")
                .values_list(
                    "entry__position",
                    "position",
                    "definition",
                    "example",
                )
            )

            self.assertEqual(report.word_count, 2)
            self.assertEqual(report.sense_count, 3)
            self.assertEqual(stored_content, expected_content)

            VocabularySense.objects.filter(
                entry__position=2,
                position=1,
            ).update(
                definition="tampered definition",
                example="A tampered Opaque example replaced the reviewed text.",
            )

            with self.assertRaisesRegex(CorpusImportError, "not immutable"):
                import_corpus(manifest)

    def test_reimport_detects_deep_database_tampering(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )
            import_corpus(manifest)
            VocabularySense.objects.update(
                provenance={"fixture": "tampered", "provider": "test-provider"}
            )

            with self.assertRaisesRegex(CorpusImportError, "not immutable"):
                import_corpus(manifest)

    def test_database_failure_rolls_back_every_row(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest = write_test_artifact(
                Path(temporary_directory) / "v1",
                version="v1",
                words=(canonical_word("Lucid"),),
            )

            with patch.object(
                VocabularySense.objects,
                "bulk_create",
                side_effect=DatabaseError("fixture failure"),
            ):
                with self.assertRaisesRegex(CorpusImportError, "database rejected"):
                    import_corpus(manifest)

        self.assertFalse(CorpusVersion.objects.exists())
        self.assertFalse(VocabularyWord.objects.exists())
        self.assertFalse(CorpusEntry.objects.exists())
        self.assertFalse(VocabularySense.objects.exists())

    def test_release_spelling_does_not_mutate_an_older_corpus(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first_manifest = write_test_artifact(
                root / "v1",
                version="v1",
                words=(
                    canonical_word(
                        "Straße",
                        example="Die Straße war still.",
                    ),
                ),
            )
            second_manifest = write_test_artifact(
                root / "v2",
                version="v2",
                words=(
                    canonical_word(
                        "STRASSE",
                        example="The STRASSE remained quiet.",
                    ),
                ),
            )

            import_corpus(first_manifest)
            import_corpus(second_manifest)

        self.assertEqual(VocabularyWord.objects.count(), 1)
        self.assertEqual(VocabularyWord.objects.get().term, "Straße")
        self.assertEqual(
            CorpusEntry.objects.get(corpus__version="v1").term,
            "Straße",
        )
        self.assertEqual(
            CorpusEntry.objects.get(corpus__version="v2").term,
            "STRASSE",
        )
        self.assertFalse(CorpusVersion.objects.get(version="v1").is_active)
        self.assertTrue(CorpusVersion.objects.get(version="v2").is_active)
