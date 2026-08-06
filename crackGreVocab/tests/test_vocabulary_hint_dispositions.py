"""Schema-v3 source-hint disposition tests."""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from django.test import SimpleTestCase
from vocabulary.builder import (
    EditorialWord,
    ProviderWordDecision,
    RejectedSourceHint,
    SenseSelection,
    _resolved_word,
    load_editorial_overrides,
    load_sense_decisions,
)
from vocabulary.exceptions import CorpusBuildError
from vocabulary.normalization import canonical_term
from vocabulary.providers import ProviderExample, SenseCandidate
from vocabulary.source import SourceRecord, SourceWord

SOURCE_DIGEST = "0" * 64


def _word() -> SourceWord:
    term, normalized_term = canonical_term("abandon")
    record = SourceRecord(
        number=1,
        term=term,
        normalized_term=normalized_term,
        definition="1. freedom from constraint\n2. withdraw",
    )
    return SourceWord(
        term=term,
        normalized_term=normalized_term,
        records=(record,),
    )


def _candidate() -> SenseCandidate:
    return SenseCandidate(
        provider="oewn-2025",
        provider_sense_id="abandon%1:07:00::",
        provider_synset_id="04892593-n",
        definition_index=0,
        part_of_speech="noun",
        definition="freedom from constraint or inhibition",
        examples=(
            ProviderExample(
                text="She danced with abandon.",
                provenance={"example_index": 0, "kind": "example"},
            ),
        ),
        members=("abandon",),
        pronunciation="",
        provenance={"provider": "oewn-2025"},
    )


def _selection(
    candidate: SenseCandidate,
    *source_hints: str,
) -> SenseSelection:
    return SenseSelection(
        provider=candidate.provider,
        provider_sense_id=candidate.provider_sense_id,
        provider_synset_id=candidate.provider_synset_id,
        definition_index=candidate.definition_index,
        example_index=0,
        candidate_sha256=candidate.content_digest,
        source_hints=source_hints,
    )


def _rejection(source_hint: str = "withdraw") -> RejectedSourceHint:
    return RejectedSourceHint(
        source_hint=source_hint,
        rationale="The legacy hint is too vague to identify a reviewable sense.",
    )


def _provider_document(candidate: SenseCandidate) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "selections": {
            "abandon": {
                "rejected_source_hints": [
                    {
                        "rationale": _rejection().rationale,
                        "source_hint": "withdraw",
                    }
                ],
                "senses": [
                    {
                        "candidate_sha256": candidate.content_digest,
                        "definition_index": candidate.definition_index,
                        "example_index": 0,
                        "provider": candidate.provider,
                        "provider_sense_id": candidate.provider_sense_id,
                        "provider_synset_id": candidate.provider_synset_id,
                        "source_hints": ["freedom from constraint"],
                    }
                ],
            }
        },
        "source_sha256": SOURCE_DIGEST,
    }


def _editorial_document() -> dict[str, Any]:
    return {
        "schema_version": 3,
        "source_sha256": SOURCE_DIGEST,
        "words": {
            "abandon": {
                "pronunciation": "",
                "rejected_source_hints": [
                    {
                        "rationale": _rejection().rationale,
                        "source_hint": "withdraw",
                    }
                ],
                "replacement_mode": "none",
                "senses": [
                    {
                        "definition": "freedom from constraint or inhibition",
                        "editorial_id": "m1-abandon-1",
                        "example": "She danced with abandon.",
                        "part_of_speech": "noun",
                        "source_hints": ["freedom from constraint"],
                    }
                ],
            }
        },
    }


def _load_document(
    document: dict[str, Any],
    loader: Callable[..., object],
) -> object:
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "decisions.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return loader(path, source_digest=SOURCE_DIGEST)


class HintDispositionTests(SimpleTestCase):
    def test_provider_rejection_completes_coverage_and_is_retained(self):
        candidate = _candidate()
        decisions = _load_document(
            _provider_document(candidate),
            load_sense_decisions,
        )
        assert isinstance(decisions, dict)

        resolved = _resolved_word(
            _word(),
            (candidate,),
            decisions["abandon"],
            None,
            position=1,
        )

        assert resolved is not None
        self.assertEqual(
            resolved.senses[0].provenance["rejected_source_hints"],
            [
                {
                    "rationale": _rejection().rationale,
                    "source_hint": "withdraw",
                }
            ],
        )

    def test_editorial_rejection_completes_coverage_and_is_retained(self):
        overrides = _load_document(
            _editorial_document(),
            load_editorial_overrides,
        )
        assert isinstance(overrides, dict)

        resolved = _resolved_word(
            _word(),
            (),
            None,
            overrides["abandon"],
            position=1,
        )

        assert resolved is not None
        self.assertEqual(
            resolved.senses[0].provenance["rejected_source_hints"],
            [
                {
                    "rationale": _rejection().rationale,
                    "source_hint": "withdraw",
                }
            ],
        )

    def test_editorial_can_replace_fully_rejected_contaminated_hints(self):
        document = _editorial_document()
        word = document["words"]["abandon"]
        word["rejected_source_hints"] = [
            {
                "rationale": "The legacy hint belongs to an adjacent source row.",
                "source_hint": "freedom from constraint",
            },
            {
                "rationale": "The legacy hint is too vague to retain safely.",
                "source_hint": "withdraw",
            },
        ]
        word["senses"][0]["source_hints"] = []
        word["replacement_mode"] = "source-contamination"
        overrides = _load_document(document, load_editorial_overrides)
        assert isinstance(overrides, dict)

        resolved = _resolved_word(
            _word(),
            (),
            None,
            overrides["abandon"],
            position=1,
        )

        assert resolved is not None
        self.assertEqual(resolved.senses[0].provenance["source_hints"], [])
        self.assertEqual(
            len(resolved.senses[0].provenance["rejected_source_hints"]),
            2,
        )

    def test_unanchored_editorial_sense_cannot_mix_with_hint_anchored_senses(self):
        document = _editorial_document()
        unanchored = json.loads(json.dumps(document["words"]["abandon"]["senses"][0]))
        unanchored["editorial_id"] = "m1-abandon-replacement"
        unanchored["source_hints"] = []
        document["words"]["abandon"]["senses"].append(unanchored)
        document["words"]["abandon"]["replacement_mode"] = (
            "source-contamination"
        )
        overrides = _load_document(document, load_editorial_overrides)
        assert isinstance(overrides, dict)

        with self.assertRaisesRegex(CorpusBuildError, "unanchored replacement"):
            _resolved_word(
                _word(),
                (),
                None,
                overrides["abandon"],
                position=1,
            )

    def test_unanchored_editorial_requires_explicit_contamination_approval(self):
        document = _editorial_document()
        word = document["words"]["abandon"]
        word["rejected_source_hints"] = [
            {
                "rationale": "The hint was copied from an adjacent row.",
                "source_hint": hint,
            }
            for hint in ("freedom from constraint", "withdraw")
        ]
        word["senses"][0]["source_hints"] = []
        overrides = _load_document(document, load_editorial_overrides)
        assert isinstance(overrides, dict)

        with self.assertRaisesRegex(CorpusBuildError, "source-contamination"):
            _resolved_word(
                _word(),
                (),
                None,
                overrides["abandon"],
                position=1,
            )

    def test_editorial_loader_requires_supported_pos_and_replacement_mode(self):
        invalid_pos = _editorial_document()
        invalid_pos["words"]["abandon"]["senses"][0]["part_of_speech"] = ""
        with self.assertRaisesRegex(CorpusBuildError, "supported value"):
            _load_document(invalid_pos, load_editorial_overrides)

        invalid_mode = _editorial_document()
        invalid_mode["words"]["abandon"]["replacement_mode"] = "arbitrary"
        with self.assertRaisesRegex(CorpusBuildError, "replacement_mode"):
            _load_document(invalid_mode, load_editorial_overrides)

    def test_dispositions_reject_unknown_duplicate_overlap_and_missing_hints(self):
        candidate = _candidate()
        selection = _selection(candidate, "freedom from constraint")
        cases = (
            (
                "unknown source hints",
                ProviderWordDecision((selection,), (_rejection("escape"),)),
            ),
            (
                "covers a source hint more than once",
                ProviderWordDecision(
                    (
                        _selection(
                            candidate,
                            "freedom from constraint",
                            "freedom from constraint",
                        ),
                    ),
                    (_rejection(),),
                ),
            ),
            (
                "rejects a source hint more than once",
                ProviderWordDecision((selection,), (_rejection(), _rejection())),
            ),
            (
                "both retains and rejects",
                ProviderWordDecision(
                    (_selection(candidate, "freedom from constraint", "withdraw"),),
                    (_rejection(),),
                ),
            ),
            (
                "does not dispose every source hint",
                ProviderWordDecision((selection,), ()),
            ),
        )
        for message, decision in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(CorpusBuildError, message):
                    _resolved_word(
                        _word(),
                        (candidate,),
                        decision,
                        None,
                        position=1,
                    )

    def test_provider_and_editorial_orphan_rejections_are_rejected(self):
        provider = ProviderWordDecision((), (_rejection(),))
        editorial = EditorialWord(
            pronunciation="",
            replacement_mode="none",
            senses=(),
            rejected_source_hints=(_rejection(),),
        )

        with self.assertRaisesRegex(CorpusBuildError, "orphan rejected source hints"):
            _resolved_word(_word(), (), provider, None, position=1)
        with self.assertRaisesRegex(CorpusBuildError, "orphan rejected source hints"):
            _resolved_word(_word(), (), None, editorial, position=1)

    def test_both_loaders_require_exact_fields_and_canonical_rationales(self):
        candidate = _candidate()
        cases = []
        for document, loader, root_key in (
            (_provider_document(candidate), load_sense_decisions, "selections"),
            (_editorial_document(), load_editorial_overrides, "words"),
        ):
            word = document[root_key]["abandon"]
            rejection = word["rejected_source_hints"][0]

            empty = json.loads(json.dumps(document))
            empty[root_key]["abandon"]["rejected_source_hints"][0][
                "rationale"
            ] = ""
            cases.append(("must not be empty", empty, loader))

            noncanonical = json.loads(json.dumps(document))
            noncanonical[root_key]["abandon"]["rejected_source_hints"][0][
                "rationale"
            ] = f"  {rejection['rationale']}  "
            cases.append(("must be canonical", noncanonical, loader))

            extra_field = json.loads(json.dumps(document))
            extra_field[root_key]["abandon"]["rejected_source_hints"][0][
                "reviewer"
            ] = "test"
            cases.append(("must contain exactly", extra_field, loader))

        for message, document, loader in cases:
            with self.subTest(message=message, loader=loader.__name__):
                with self.assertRaisesRegex(CorpusBuildError, message):
                    _load_document(document, loader)

    def test_loaders_reject_orphan_rejections(self):
        candidate = _candidate()
        for document, loader, root_key in (
            (_provider_document(candidate), load_sense_decisions, "selections"),
            (_editorial_document(), load_editorial_overrides, "words"),
        ):
            document[root_key]["abandon"]["senses"] = []
            with self.subTest(loader=loader.__name__):
                with self.assertRaisesRegex(
                    CorpusBuildError,
                    "orphan rejected source hints",
                ):
                    _load_document(document, loader)
