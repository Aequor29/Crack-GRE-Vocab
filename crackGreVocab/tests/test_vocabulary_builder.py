"""Fail-closed sense-alignment and reviewed-selection tests."""

import json
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from vocabulary.artifacts import load_corpus
from vocabulary.builder import (
    AUTO_ALIGNMENT_MARGIN,
    AUTO_ALIGNMENT_MINIMUM,
    AUTO_ALIGNMENT_POLICY_VERSION,
    BuildInputs,
    EditorialWord,
    SenseSelection,
    _resolved_word,
    auto_select_senses,
    build_artifacts,
    review_queue_document,
)
from vocabulary.example_matching import (
    EXAMPLE_MATCH_POLICY_RULE,
    EXAMPLE_MATCH_POLICY_VERSION,
)
from vocabulary.exceptions import CorpusBuildError
from vocabulary.normalization import canonical_term, sha256_bytes, sha256_file
from vocabulary.providers import ProviderConfig, ProviderExample, SenseCandidate
from vocabulary.source import SourceAudit, SourceRecord, SourceWord


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
            source_hints=("clear",),
        )

        with self.assertRaisesRegex(CorpusBuildError, "stale provider content"):
            _resolved_word(
                word,
                (candidate,),
                (stale_selection,),
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
            source_hints=("clear",),
        )

        with self.assertRaisesRegex(CorpusBuildError, "stale provider content"):
            review_queue_document(
                _audit(word),
                {word.normalized_term: (candidate,)},
                {word.normalized_term: (stale_selection,)},
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
            source_hints=("clear",),
        )

        with self.assertRaisesRegex(CorpusBuildError, "part_of_speech"):
            _resolved_word(
                word,
                (candidate,),
                (selection,),
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

        automatic = _resolved_word(
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
            source_hints=("clear",),
        )
        reviewed = _resolved_word(
            word,
            (candidate,),
            (selection,),
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
        resolved = _resolved_word(word, (candidate,), None, None, position=1)
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

        queue = review_queue_document(
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

    def test_reviewed_selection_must_cover_every_hint_and_use_an_eligible_example(self):
        word = _word("lucid", "1. clear\n2. rational")
        candidate = _candidate(
            "lucid-sense",
            "clear",
            "The explanation was easy to understand.",
        )
        incomplete = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256=candidate.content_digest,
            source_hints=("clear",),
        )
        with self.assertRaisesRegex(CorpusBuildError, "every source hint"):
            _resolved_word(
                word,
                (candidate,),
                (incomplete,),
                None,
                position=1,
            )

        ineligible = SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=0,
            example_index=0,
            candidate_sha256=candidate.content_digest,
            source_hints=("clear", "rational"),
        )
        with self.assertRaisesRegex(
            CorpusBuildError,
            "does not contain the exact headword",
        ):
            _resolved_word(
                word,
                (candidate,),
                (ineligible,),
                None,
                position=1,
            )


class ArtifactBuildAcceptanceTests(SimpleTestCase):
    def test_build_is_deterministic_idempotent_and_records_exact_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = {
                name: root / name
                for name in (
                    "source.csv",
                    "duplicates.json",
                    "providers.json",
                    "oewn.zip",
                    "senses.json",
                    "overrides.json",
                    "fallback.jsonl",
                )
            }
            contents = {
                "source.csv": b"word,definition\nLucid,clear\n",
                "duplicates.json": b'{"fixture":"duplicates"}\n',
                "providers.json": b'{"fixture":"providers"}\n',
                "oewn.zip": b"fixture archive\n",
                "senses.json": b'{"fixture":"senses"}\n',
                "overrides.json": b'{"fixture":"overrides"}\n',
                "fallback.jsonl": b'{"fixture":"fallback"}\n',
            }
            for name, path in paths.items():
                path.write_bytes(contents[name])

            inputs = BuildInputs(
                source_path=paths["source.csv"],
                duplicate_decisions_path=paths["duplicates.json"],
                provider_registry_path=paths["providers.json"],
                oewn_archive_path=paths["oewn.zip"],
                sense_decisions_path=paths["senses.json"],
                editorial_overrides_path=paths["overrides.json"],
                fallback_cache_path=paths["fallback.jsonl"],
            )
            word = _word("lucid", "clear")
            candidate = _candidate(
                "lucid-sense",
                "clear and easy to understand",
                "A lucid explanation settled the question.",
            )
            selection = SenseSelection(
                provider=candidate.provider,
                provider_sense_id=candidate.provider_sense_id,
                provider_synset_id=candidate.provider_synset_id,
                definition_index=0,
                example_index=0,
                candidate_sha256=candidate.content_digest,
                source_hints=("clear",),
            )
            audit = replace(
                _audit(word),
                source_digest=sha256_file(paths["source.csv"]),
            )
            context: tuple[
                SourceAudit,
                dict[str, ProviderConfig],
                dict[str, tuple[SenseCandidate, ...]],
                dict[str, tuple[SenseSelection, ...]],
                dict[str, EditorialWord],
            ] = (
                audit,
                {},
                {word.normalized_term: (candidate,)},
                {word.normalized_term: (selection,)},
                {},
            )
            first_output = root / "first"
            second_output = root / "second"

            with patch(
                "vocabulary.builder.load_build_context",
                return_value=context,
            ):
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
                    "fallback_cache_sha256": sha256_file(
                        paths["fallback.jsonl"]
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
                "reviewed",
            )


class BuildInputProvenanceTests(SimpleTestCase):
    def test_build_rejects_an_input_replaced_before_publication(self):
        for changed_name, expected_label in (
            ("source.csv", "source_sha256"),
            ("fallback.jsonl", "fallback_cache_sha256"),
        ):
            with self.subTest(changed_name=changed_name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    paths = {
                        name: root / name
                        for name in (
                            "source.csv",
                            "duplicates.json",
                            "providers.json",
                            "oewn.zip",
                            "senses.json",
                            "overrides.json",
                            "fallback.jsonl",
                        )
                    }
                    for path in paths.values():
                        path.write_bytes(b"initial")
                    inputs = BuildInputs(
                        source_path=paths["source.csv"],
                        duplicate_decisions_path=paths["duplicates.json"],
                        provider_registry_path=paths["providers.json"],
                        oewn_archive_path=paths["oewn.zip"],
                        sense_decisions_path=paths["senses.json"],
                        editorial_overrides_path=paths["overrides.json"],
                        fallback_cache_path=paths["fallback.jsonl"],
                    )
                    audit = replace(
                        _audit(_word("lucid", "clear")),
                        source_digest=sha256_file(paths["source.csv"]),
                    )

                    def replace_input(
                        _inputs: BuildInputs,
                    ) -> tuple[object, ...]:
                        paths[changed_name].write_bytes(b"replacement")
                        loaded_audit = replace(
                            audit,
                            source_digest=sha256_file(paths["source.csv"]),
                        )
                        return loaded_audit, {}, {}, {}, {}

                    with (
                        patch(
                            "vocabulary.builder.load_build_context",
                            side_effect=replace_input,
                        ),
                        patch(
                            "vocabulary.builder.build_corpus_words",
                            return_value=(),
                        ),
                    ):
                        with self.assertRaisesRegex(
                            CorpusBuildError,
                            expected_label,
                        ):
                            build_artifacts(
                                inputs,
                                version="v1",
                                output_directory=root / "v1",
                            )

                    self.assertFalse((root / "v1").exists())


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
            queue["summary"],
            {
                "fallback_required": 0,
                "multiple_eligible_candidates": 0,
                "no_headword_example": 0,
                "no_same_sense_example": 0,
                "resolved_automatically": 22,
                "resolved_by_override": 613,
                "resolved_by_selection": 2399,
                "review_required": 0,
                "single_eligible_candidate": 0,
                "unresolved": 0,
                "without_candidates": 0,
            },
        )
        self.assertEqual(
            sum(item["fallback_required"] for item in queue["items"]),
            0,
        )
        self.assertEqual(
            sum(item["review_required"] for item in queue["items"]),
            0,
        )
        self.assertEqual(queue["items"], [])
