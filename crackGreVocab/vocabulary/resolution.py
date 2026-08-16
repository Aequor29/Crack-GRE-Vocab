"""Resolve reviewed or automatic choices into canonical corpus words."""

from collections.abc import Mapping

from .alignment import (
    AUTO_ALIGNMENT_POLICY_VERSION,
    ExampleMatch,
    auto_select_senses,
    eligible_example_matches,
)
from .artifacts import CanonicalSense, CanonicalWord
from .decisions import EditorialWord, ProviderWordDecision
from .example_matching import EXAMPLE_MATCH_POLICY_VERSION, match_example_text
from .exceptions import CorpusBuildError
from .normalization import collapse_whitespace, stable_word_id
from .providers import SenseCandidate
from .source import SourceAudit, SourceWord


def _review_note_provenance(review_note: str) -> dict[str, str]:
    return {"review_note": review_note} if review_note else {}


def resolve_word(
    word: SourceWord,
    candidates: tuple[SenseCandidate, ...],
    decision: ProviderWordDecision | None,
    override: EditorialWord | None,
    *,
    position: int,
) -> CanonicalWord | None:
    """Resolve one source word or return None when human review is still required."""
    if override is not None:
        editorial_senses: list[CanonicalSense] = []
        for sense_position, sense in enumerate(override.senses, start=1):
            matched = match_example_text(
                word.normalized_term,
                sense.part_of_speech,
                sense.example,
            )
            if matched is None:
                raise CorpusBuildError(
                    f"editorial example for {word.term!r} does not contain the "
                    "exact headword"
                )
            editorial_senses.append(
                CanonicalSense(
                    position=sense_position,
                    part_of_speech=sense.part_of_speech,
                    definition=sense.definition,
                    example=sense.example,
                    provenance={
                        "editorial_id": sense.editorial_id,
                        "example_headword_match": {
                            "form": matched.form,
                            "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
                            "surface": matched.surface,
                        },
                        "provider": "editorial-override",
                        **_review_note_provenance(override.review_note),
                        "reviewed": True,
                        "selection_mode": "editorial",
                    },
                )
            )
        return CanonicalWord(
            position=position,
            word_id=stable_word_id(word.normalized_term),
            term=word.term,
            normalized_term=word.normalized_term,
            pronunciation=override.pronunciation,
            senses=tuple(editorial_senses),
        )

    selection_mode = "reviewed"
    review_note = ""
    if decision is None:
        selected_senses = auto_select_senses(word, candidates)
        if selected_senses is None:
            return None
        selection_mode = "automatic"
    else:
        selected_senses = decision.senses
        review_note = decision.review_note
    if not selected_senses:
        raise CorpusBuildError(
            f"sense decision for {word.term!r} needs a retained sense"
        )

    by_key = {candidate.selection_key: candidate for candidate in candidates}
    resolved: list[tuple[SenseCandidate, ExampleMatch, str, str]] = []
    for selection in selected_senses:
        try:
            candidate = by_key[selection.candidate_key]
        except KeyError as exc:
            raise CorpusBuildError(
                f"reviewed sense for {word.term!r} is absent from pinned inputs: "
                f"{selection.candidate_key}"
            ) from exc
        if candidate.content_digest != selection.candidate_sha256:
            raise CorpusBuildError(
                f"reviewed sense for {word.term!r} was approved against stale "
                "provider content"
            )
        try:
            candidate.examples[selection.example_index]
        except IndexError as exc:
            raise CorpusBuildError(
                f"reviewed sense for {word.term!r} selects a missing same-sense example"
            ) from exc
        example_match = next(
            (
                match
                for match in eligible_example_matches(word, candidate)
                if match.example_index == selection.example_index
            ),
            None,
        )
        if example_match is None:
            raise CorpusBuildError(
                f"selected example for {word.term!r} does not contain the exact "
                "headword"
            )
        part_of_speech = collapse_whitespace(candidate.part_of_speech)
        pronunciation = collapse_whitespace(candidate.pronunciation)
        if len(part_of_speech) > 32:
            raise CorpusBuildError(
                f"provider part_of_speech for {word.term!r} is too long"
            )
        if len(pronunciation) > 255:
            raise CorpusBuildError(
                f"provider pronunciation for {word.term!r} is too long"
            )
        resolved.append((candidate, example_match, part_of_speech, pronunciation))

    if len(
        {
            (candidate.definition, example_match.example.text)
            for candidate, example_match, _part_of_speech, _pronunciation in resolved
        }
    ) != len(resolved):
        raise CorpusBuildError(f"reviewed senses for {word.term!r} contain duplicates")

    senses = tuple(
        CanonicalSense(
            position=sense_position,
            part_of_speech=part_of_speech,
            definition=candidate.definition,
            example=example_match.example.text,
            provenance={
                **candidate.provenance,
                "candidate_sha256": candidate.content_digest,
                **(
                    {
                        "automatic_alignment_policy_version": (
                            AUTO_ALIGNMENT_POLICY_VERSION
                        )
                    }
                    if selection_mode == "automatic"
                    else {}
                ),
                "example": example_match.example.provenance,
                "example_headword_match": {
                    "form": example_match.form,
                    "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
                    "surface": example_match.surface,
                },
                "example_index": example_match.example_index,
                **_review_note_provenance(review_note),
                "selection_mode": selection_mode,
            },
        )
        for sense_position, (
            candidate,
            example_match,
            part_of_speech,
            _pronunciation,
        ) in enumerate(resolved, start=1)
    )
    pronunciation = next(
        (
            pronunciation
            for _candidate, _example_match, _part_of_speech, pronunciation in resolved
            if pronunciation
        ),
        "",
    )
    return CanonicalWord(
        position=position,
        word_id=stable_word_id(word.normalized_term),
        term=word.term,
        normalized_term=word.normalized_term,
        pronunciation=pronunciation,
        senses=senses,
    )


def build_corpus_words(
    audit: SourceAudit,
    candidates: dict[str, tuple[SenseCandidate, ...]],
    selections: Mapping[str, ProviderWordDecision],
    overrides: dict[str, EditorialWord],
) -> tuple[CanonicalWord, ...]:
    """Resolve the complete audited source into ordered canonical words."""
    words: list[CanonicalWord] = []
    unresolved: list[str] = []
    for position, word in enumerate(audit.words, start=1):
        resolved = resolve_word(
            word,
            candidates.get(word.normalized_term, ()),
            selections.get(word.normalized_term),
            overrides.get(word.normalized_term),
            position=position,
        )
        if resolved is None:
            unresolved.append(word.term)
        else:
            words.append(resolved)
    if unresolved:
        raise CorpusBuildError(
            f"{len(unresolved)} word(s) still require reviewed paired senses; "
            f"first unresolved: {unresolved[:10]}"
        )
    return tuple(words)
