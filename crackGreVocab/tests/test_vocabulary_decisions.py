"""Reviewed-content schema tests at the decision-module interface."""

import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from vocabulary.decisions import load_editorial_overrides, load_sense_decisions
from vocabulary.exceptions import CorpusBuildError


class VocabularyDecisionTests(SimpleTestCase):
    source_digest = "0" * 64

    def _write(self, root: Path, name: str, document: dict[str, object]) -> Path:
        path = root / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_provider_selection_keeps_only_candidate_identity_and_review_note(self):
        document = {
            "schema_version": 4,
            "selections": {
                "lucid": {
                    "review_note": "The alternate legacy gloss was too broad.",
                    "senses": [
                        {
                            "candidate_sha256": "1" * 64,
                            "definition_index": 0,
                            "example_index": 1,
                            "provider": "oewn-2025",
                            "provider_sense_id": "lucid%5:00",
                            "provider_synset_id": "0001-a",
                        }
                    ],
                }
            },
            "source_sha256": self.source_digest,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self._write(Path(temporary_directory), "senses.json", document)
            decisions = load_sense_decisions(
                path,
                source_digest=self.source_digest,
            )

        decision = decisions["lucid"]
        self.assertEqual(
            decision.review_note,
            "The alternate legacy gloss was too broad.",
        )
        self.assertEqual(decision.senses[0].example_index, 1)

    def test_legacy_hint_disposition_fields_are_not_part_of_the_schema(self):
        document = {
            "schema_version": 4,
            "selections": {
                "lucid": {
                    "rejected_source_hints": [],
                    "senses": [],
                }
            },
            "source_sha256": self.source_digest,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self._write(Path(temporary_directory), "senses.json", document)
            with self.assertRaisesRegex(CorpusBuildError, "invalid fields"):
                load_sense_decisions(path, source_digest=self.source_digest)

    def test_editorial_override_loads_paired_learning_content(self):
        document = {
            "schema_version": 4,
            "source_sha256": self.source_digest,
            "words": {
                "lucid": {
                    "pronunciation": "",
                    "senses": [
                        {
                            "definition": "clear and easy to understand",
                            "editorial_id": "m1-lucid-1",
                            "example": "Her lucid explanation resolved the issue.",
                            "part_of_speech": "adjective",
                        }
                    ],
                }
            },
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = self._write(Path(temporary_directory), "overrides.json", document)
            overrides = load_editorial_overrides(
                path,
                source_digest=self.source_digest,
            )

        sense = overrides["lucid"].senses[0]
        self.assertEqual(sense.definition, "clear and easy to understand")
        self.assertIn("lucid", sense.example)
