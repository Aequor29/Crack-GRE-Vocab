"""Fail-closed sense-alignment and reviewed-selection tests."""

import json
import tempfile
from dataclasses import replace
from pathlib import Path, PosixPath
from typing import Any

from django.test import SimpleTestCase
from vocabulary.alignment import (
    AUTO_ALIGNMENT_MARGIN,
    AUTO_ALIGNMENT_MINIMUM,
    AUTO_ALIGNMENT_POLICY_VERSION,
    auto_select_senses,
)
from vocabulary.artifacts import load_corpus
from vocabulary.builder import build_artifacts
from vocabulary.decisions import ProviderWordDecision, SenseSelection
from vocabulary.example_matching import (
    EXAMPLE_MATCH_POLICY_RULE,
    EXAMPLE_MATCH_POLICY_VERSION,
)
from vocabulary.exceptions import CorpusBuildError
from vocabulary.normalization import canonical_term, sha256_bytes, sha256_file
from vocabulary.providers import ProviderExample, SenseCandidate
from vocabulary.resolution import resolve_word
from vocabulary.review_queue import build_review_queue
from vocabulary.source import SourceAudit, SourceRecord, SourceWord

from tests.vocabulary_helpers import (
    provider_registry_document,
    write_minimal_build_inputs,
)


class _ReplaceAfterReadPath(PosixPath):
    """Test filesystem boundary that changes a file after its first read."""

    __slots__ = ("_did_replace", "_replacement_content")
    _did_replace: bool
    _replacement_content: bytes

    def __new__(cls, path: Path, replacement_content: bytes):
        instance = super().__new__(cls, path)
        instance._did_replace = False
        instance._replacement_content = replacement_content
        return instance

    def __init__(self, path: Path, replacement_content: bytes):
        super().__init__(path)

    def open(self, *args: Any, **kwargs: Any) -> Any:
        opened = super().open(*args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if self._did_replace or "r" not in mode:
            return opened
        self._did_replace = True
        return _ReplaceOnClose(
            opened,
            Path(self),
            self._replacement_content,
        )


class _ReplaceOnClose:
    def __init__(self, opened: Any, path: Path, replacement_content: bytes):
        self._opened = opened
        self._path = path
        self._replacement_content = replacement_content

    def __enter__(self) -> Any:
        return self._opened.__enter__()

    def __exit__(self, *args: Any) -> Any:
        result = self._opened.__exit__(*args)
        self._path.write_bytes(self._replacement_content)
        return result


def _word(term: str, hint: str) -> SourceWord:
    display, normalized = canonical_term(term)
    return SourceWord(
        term=display,
        normalized_term=normalized,
        records=(
            SourceRecord(
                number=1,
                term=display,
                normalized_term=normalized,
                definition=hint,
            ),
        ),
    )


def _candidate(
    sense_id: str,
    definition: str,
    example: str | tuple[str, ...] = "A paired example.",
    *,
    members: tuple[str, ...] = (),
    part_of_speech: str = "adjective",
    pronunciation: str = "",
) -> SenseCandidate:
    example_texts = (example,) if isinstance(example, str) else example
    examples = tuple(
        ProviderExample(
            text=example_text,
            provenance={"example_index": example_index, "kind": "example"},
        )
        for example_index, example_text in enumerate(example_texts)
        if example_text
    )
    return SenseCandidate(
        provider="oewn-2025",
        provider_sense_id=sense_id,
        provider_synset_id=f"{sense_id}-synset",
        definition_index=0,
        part_of_speech=part_of_speech,
        definition=definition,
        examples=examples,
        members=members,
        pronunciation=pronunciation,
        provenance={"provider": "oewn-2025"},
    )


def _audit(word: SourceWord) -> SourceAudit:
    return SourceAudit(
        source_digest="0" * 64,
        records=word.records,
        words=(word,),
        duplicate_groups=(),
        outer_whitespace_definitions=0,
        multiline_definitions=0,
        nonstandard_multiline_definitions=0,
        exact_duplicate_rows=0,
        sort_inversions=0,
        normalized_term_changes=0,
    )


class AutomaticSenseSelectionTests(SimpleTestCase):
    def test_strong_unique_alignment_is_accepted(self):
        word = _word(
            "precipitate",
            "done with very great haste and without due deliberation",
        )
        right = _candidate(
            "right",
            "done with very great haste and without careful deliberation",
            "The precipitate decision caused lasting harm.",
        )
        wrong = _candidate(
            "wrong",
            "fall from clouds",
            "A precipitate fell from the clouds.",
        )

        selection = auto_select_senses(word, (right, wrong))

        assert selection is not None
        self.assertEqual(selection[0].provider_sense_id, "right")

    def test_high_scoring_near_tie_is_rejected(self):
        word = _word("trigger", "cause an event to happen very suddenly")
        first = _candidate(
            "first",
            "cause an event to happen suddenly",
            "A trigger caused the event.",
        )
        second = _candidate(
            "second",
            "cause something to happen very suddenly",
            "The trigger acted suddenly.",
        )

        self.assertIsNone(auto_select_senses(word, (first, second)))

    def test_distinct_exact_matches_are_rejected(self):
        word = _word("disdain", "scorn")
        noun = _candidate(
            "noun",
            "scorn",
            "Her disdain was obvious.",
            part_of_speech="noun",
        )
        verb = _candidate(
            "verb",
            "scorn",
            "They disdain empty praise.",
            part_of_speech="verb",
        )

        self.assertIsNone(auto_select_senses(word, (noun, verb)))

    def test_known_wrong_examples_all_remain_in_review(self):
        regressions = (
            ("accede", "approval or conscent", "take on duties or office"),
            ("check", "arrest abruptly", "the bill in a restaurant"),
            ("forge", "imitate falsely", "move ahead steadily"),
            ("grit", "endure pain or hardship", "cover with a grit"),
            ("hale", "free from infirmity or illness", "draw slowly or heavily"),
            ("minute", "carefully scrutiny", "an indefinitely short time"),
            (
                "pigment",
                "a substance that imparts a color",
                "color or dye with a pigment",
            ),
            ("precipitate", "cause to happen", "hurl or throw violently"),
            ("jot", "write briefly", "a slight but appreciable amount"),
            ("sedentary", "not migratory", "requiring sitting or little activity"),
        )
        for term, hint, wrong_definition in regressions:
            with self.subTest(term=term):
                self.assertIsNone(
                    auto_select_senses(
                        _word(term, hint),
                        (
                            _candidate(
                                "wrong",
                                wrong_definition,
                                f"The word {term} appears in this example.",
                            ),
                        ),
                    )
                )

    def test_selector_does_not_skip_a_better_same_provider_sense_for_an_example(self):
        word = _word("lucid", "clear")
        best_without_headword = _candidate(
            "best",
            "clear",
            "The explanation was easy to understand.",
        )
        lower_with_headword = _candidate(
            "lower",
            "brightly illuminated",
            "The lucid surface reflected light.",
        )

        self.assertIsNone(
            auto_select_senses(
                word,
                (best_without_headword, lower_with_headword),
            )
        )

    def test_one_word_member_synonyms_do_not_bypass_ambiguity_review(self):
        regressions = (
            (
                "distort",
                "twist",
                "form into a spiral shape",
                ("twist",),
                "Mirrors distort the image.",
            ),
            (
                "frail",
                "weak",
                "easily led into evil",
                ("frail", "weak"),
                "The frail frame bent.",
            ),
            (
                "renounce",
                "give up",
                "give up or retire from a position",
                ("renounce", "give up"),
                "They renounce the title.",
            ),
            (
                "requisite",
                "necessary",
                "anything indispensable",
                ("requisite", "necessary"),
                "A permit is requisite.",
            ),
        )
        for term, hint, definition, members, example in regressions:
            with self.subTest(term=term):
                self.assertIsNone(
                    auto_select_senses(
                        _word(term, hint),
                        (
                            _candidate(
                                "wrong",
                                definition,
                                example,
                                members=members,
                            ),
                        ),
                    )
                )

    def test_provider_drift_invalidates_a_reviewed_selection(self):
        word = _word("lucid", "clear")
        candidate = _candidate("lucid-sense", "clear", members=("clear",))
        stale_selection = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256="0" * 64,
        )

        with self.assertRaisesRegex(CorpusBuildError, "stale provider content"):
            resolve_word(
                word,
                (candidate,),
                ProviderWordDecision((stale_selection,)),
                None,
                position=1,
            )

    def test_review_queue_generation_rejects_a_stale_checked_selection(self):
        word = _word("lucid", "clear")
        candidate = _candidate("lucid-sense", "clear", members=("clear",))
        stale_selection = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256="0" * 64,
        )

        with self.assertRaisesRegex(CorpusBuildError, "stale provider content"):
            build_review_queue(
                _audit(word),
                {word.normalized_term: (candidate,)},
                {
                    word.normalized_term: ProviderWordDecision((stale_selection,))
                },
                {},
            )

    def test_resolution_rejects_metadata_too_long_for_the_artifact(self):
        word = _word("lucid", "clear")
        candidate = _candidate(
            "lucid-sense",
            "clear",
            "A lucid explanation helped.",
            members=("clear",),
            part_of_speech="x" * 33,
        )
        selection = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256=candidate.content_digest,
        )

        with self.assertRaisesRegex(CorpusBuildError, "part_of_speech"):
            resolve_word(
                word,
                (candidate,),
                ProviderWordDecision((selection,)),
                None,
                position=1,
            )

    def test_final_provenance_distinguishes_automatic_and_reviewed_selection(self):
        word = _word("lucid", "clear")
        candidate = _candidate(
            "lucid-sense",
            "clear",
            "A lucid explanation helped.",
        )

        automatic = resolve_word(
            word,
            (candidate,),
            None,
            None,
            position=1,
        )
        assert automatic is not None
        self.assertEqual(
            automatic.senses[0].provenance["selection_mode"],
            "automatic",
        )
        self.assertEqual(
            automatic.senses[0].provenance["automatic_alignment_policy_version"],
            AUTO_ALIGNMENT_POLICY_VERSION,
        )
        self.assertEqual(
            automatic.senses[0].provenance["candidate_sha256"],
            candidate.content_digest,
        )

        selection = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256=candidate.content_digest,
        )
        reviewed = resolve_word(
            word,
            (candidate,),
            ProviderWordDecision((selection,)),
            None,
            position=1,
        )
        assert reviewed is not None
        self.assertEqual(reviewed.senses[0].provenance["selection_mode"], "reviewed")
        self.assertEqual(
            reviewed.senses[0].provenance["candidate_sha256"],
            candidate.content_digest,
        )
        self.assertNotIn(
            "automatic_alignment_policy_version",
            reviewed.senses[0].provenance,
        )

    def test_auto_selection_uses_the_first_exact_headword_example(self):
        word = _word("jot", "write briefly")
        candidate = _candidate(
            "jot-sense",
            "write briefly",
            ("She wrote the address down.", "She will jot the address down."),
            part_of_speech="verb",
        )

        selection = auto_select_senses(word, (candidate,))

        assert selection is not None
        self.assertEqual(selection[0].example_index, 1)
        resolved = resolve_word(word, (candidate,), None, None, position=1)
        assert resolved is not None
        self.assertEqual(resolved.senses[0].example, "She will jot the address down.")
        self.assertEqual(
            resolved.senses[0].provenance["example_headword_match"],
            {
                "form": "exact",
                "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
                "surface": "jot",
            },
        )

    def test_example_gate_rejects_substrings_and_fuzzy_relatives(self):
        substring = _candidate(
            "art-sense",
            "creative work",
            "The artifact was displayed.",
            part_of_speech="noun",
        )
        fuzzy = _candidate(
            "study-sense",
            "learn carefully",
            "The studious learner took notes.",
            part_of_speech="verb",
        )

        self.assertIsNone(
            auto_select_senses(_word("art", "creative work"), (substring,))
        )
        self.assertIsNone(
            auto_select_senses(_word("study", "learn carefully"), (fuzzy,))
        )

    def test_example_gate_rejects_inflections_even_when_they_are_regular(self):
        walked = _candidate(
            "walk-sense",
            "move on foot",
            "She walked home.",
            part_of_speech="verb",
        )
        uncertain = _candidate(
            "bar-sense",
            "prevent entry",
            "They bared the door.",
            part_of_speech="verb",
        )

        self.assertIsNone(
            auto_select_senses(_word("walk", "move on foot"), (walked,))
        )
        self.assertIsNone(
            auto_select_senses(_word("bar", "prevent entry"), (uncertain,))
        )

    def test_example_gate_keeps_irregular_and_collision_prone_stems_exact_only(self):
        unsafe_forms = (
            ("sling", "send through the air", "They slinged the stone.", "verb"),
            ("swear", "make a solemn promise", "She sweared an oath.", "verb"),
            ("forsake", "renounce", "He forsaked the claim.", "verb"),
            (
                "parenthesis",
                "an explanatory interruption",
                "The parenthesises were removed.",
                "noun",
            ),
            ("singe", "burn superficially", "The flame was singing the cloth.", "verb"),
        )

        for term, hint, example, part_of_speech in unsafe_forms:
            with self.subTest(term=term):
                candidate = _candidate(
                    f"{term}-sense",
                    hint,
                    example,
                    part_of_speech=part_of_speech,
                )
                self.assertIsNone(auto_select_senses(_word(term, hint), (candidate,)))

    def test_example_gate_requires_exact_multiword_separators(self):
        exact = _candidate(
            "ad-hoc-exact",
            "created for a particular purpose",
            "They formed an ad hoc committee.",
        )
        punctuation_changed = _candidate(
            "ad-hoc-changed",
            "created for a particular purpose",
            "The note read ad, hoc without context.",
        )

        self.assertIsNotNone(
            auto_select_senses(
                _word("ad hoc", "created for a particular purpose"),
                (exact,),
            )
        )
        self.assertIsNone(
            auto_select_senses(
                _word("ad hoc", "created for a particular purpose"),
                (punctuation_changed,),
            )
        )

    def test_queue_reclassifies_unusable_examples_as_fallback_required(self):
        word = _word("lucid", "clear")
        candidate = _candidate(
            "lucid-sense",
            "clear",
            "The explanation was easy to understand.",
        )

        queue = build_review_queue(
            _audit(word),
            {word.normalized_term: (candidate,)},
            {},
            {},
        )

        self.assertEqual(queue["summary"]["fallback_required"], 1)
        self.assertEqual(
            queue["items"][0]["candidates"][0]["eligible_example_indexes"],
            [],
        )

    def test_reviewed_selection_requires_an_exact_headword_example(self):
        word = _word("lucid", "clear")
        candidate = _candidate(
            "lucid-sense",
            "clear",
            "The explanation was easy to understand.",
        )
        ineligible = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256=candidate.content_digest,
        )
        with self.assertRaisesRegex(
            CorpusBuildError,
            "does not contain the exact headword",
        ):
            resolve_word(
                word,
                (candidate,),
                ProviderWordDecision((ineligible,)),
                None,
                position=1,
            )


class ArtifactBuildAcceptanceTests(SimpleTestCase):
    def test_manifest_hashes_the_exact_provider_bytes_used_by_the_corpus(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = write_minimal_build_inputs(root)
            initial_registry = inputs.provider_registry_path.read_bytes()
            replacement_registry = json.dumps(
                provider_registry_document(
                    sha256_file(inputs.oewn_archive_path),
                    oewn_archive_url="https://replacement.test/oewn.zip",
                )
            ).encode()
            changing_registry = _ReplaceAfterReadPath(
                inputs.provider_registry_path,
                replacement_registry,
            )

            output = root / "release"
            build_artifacts(
                replace(inputs, provider_registry_path=changing_registry),
                version="m1-test",
                output_directory=output,
            )

            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            corpus = load_corpus(output / "manifest.json")
            self.assertEqual(
                manifest["inputs"]["provider_registry_sha256"],
                sha256_bytes(initial_registry),
            )
            self.assertEqual(
                corpus.words[0].senses[0].provenance["archive_url"],
                "https://example.test/oewn.zip",
            )

    def test_build_is_deterministic_idempotent_and_records_exact_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = write_minimal_build_inputs(root)
            paths = {
                "source.csv": inputs.source_path,
                "duplicates.json": inputs.duplicate_decisions_path,
                "providers.json": inputs.provider_registry_path,
                "oewn.zip": inputs.oewn_archive_path,
                "senses.json": inputs.sense_decisions_path,
                "overrides.json": inputs.editorial_overrides_path,
                "fallback.jsonl": inputs.fallback_cache_path,
            }
            first_output = root / "first"
            second_output = root / "second"

            self.assertTrue(
                build_artifacts(
                    inputs,
                    version="m1-test",
                    output_directory=first_output,
                )
            )
            first_corpus = (first_output / "corpus.jsonl").read_bytes()
            first_manifest = (first_output / "manifest.json").read_bytes()

            self.assertFalse(
                build_artifacts(
                    inputs,
                    version="m1-test",
                    output_directory=first_output,
                )
            )
            self.assertTrue(
                build_artifacts(
                    inputs,
                    version="m1-test",
                    output_directory=second_output,
                )
            )

            self.assertEqual(
                (second_output / "corpus.jsonl").read_bytes(),
                first_corpus,
            )
            self.assertEqual(
                (second_output / "manifest.json").read_bytes(),
                first_manifest,
            )

            manifest = json.loads(first_manifest)
            self.assertEqual(
                manifest["source"],
                {
                    "canonical_word_count": 1,
                    "row_count": 1,
                    "sha256": sha256_file(paths["source.csv"]),
                },
            )
            self.assertEqual(
                manifest["corpus"],
                {
                    "file": "corpus.jsonl",
                    "sense_count": 1,
                    "sha256": sha256_bytes(first_corpus),
                    "word_count": 1,
                },
            )
            self.assertEqual(
                manifest["inputs"],
                {
                    "duplicate_decisions_sha256": sha256_file(
                        paths["duplicates.json"]
                    ),
                    "editorial_overrides_sha256": sha256_file(
                        paths["overrides.json"]
                    ),
                    "oewn_archive_sha256": sha256_file(paths["oewn.zip"]),
                    "provider_registry_sha256": sha256_file(
                        paths["providers.json"]
                    ),
                    "sense_decisions_sha256": sha256_file(paths["senses.json"]),
                },
            )
            loaded = load_corpus(first_output / "manifest.json")
            self.assertEqual(len(loaded.words), 1)
            self.assertEqual(loaded.sense_count, 1)
            self.assertEqual(
                loaded.words[0].senses[0].provenance["selection_mode"],
                "automatic",
            )

class CheckedReviewQueueTests(SimpleTestCase):
    def test_checked_queue_matches_the_current_fail_closed_policy(self):
        from json import loads
        from pathlib import Path

        backend_root = Path(__file__).resolve().parents[1]
        queue = loads(
            (backend_root / "data/vocabulary/review-queue.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            queue["automatic_alignment"],
            {
                "exact_match_policy": "unique-definition-content-equivalent",
                "minimum_margin": AUTO_ALIGNMENT_MARGIN,
                "minimum_score": AUTO_ALIGNMENT_MINIMUM,
                "policy_version": AUTO_ALIGNMENT_POLICY_VERSION,
            },
        )
        self.assertEqual(queue["schema_version"], 2)
        self.assertEqual(
            queue["example_matching"],
            {
                "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
                "rule": EXAMPLE_MATCH_POLICY_RULE,
            },
        )
        self.assertEqual(
            queue["source_sha256"],
            sha256_file(backend_root / "data/GRE_word.csv"),
        )
        self.assertEqual(queue["summary"]["unresolved"], 0)
        self.assertEqual(queue["items"], [])
