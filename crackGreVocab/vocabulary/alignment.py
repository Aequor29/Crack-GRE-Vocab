"""Fail-closed alignment of retained GRE hints to provider senses."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from .decisions import SenseSelection
from .example_matching import match_example_text
from .normalization import collapse_whitespace
from .providers import ProviderExample, SenseCandidate
from .source import SourceWord

AUTO_ALIGNMENT_POLICY_VERSION = 2
AUTO_ALIGNMENT_MINIMUM = 0.60
AUTO_ALIGNMENT_MARGIN = 0.20
PROVIDER_PRIORITY = (
    "oewn-2025",
    "freedictionaryapi-v1",
    "dictionaryapi-dev-v2",
)
_NUMBERED_HINT = re.compile(r"^\.?\d+[.]\s*")
_ALIGNMENT_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "be",
    "for",
    "from",
    "in",
    "of",
    "on",
    "one",
    "or",
    "someone",
    "something",
    "that",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class ExampleMatch:
    """An exact-headword example eligible for one provider candidate."""

    example: ProviderExample
    example_index: int
    form: str
    surface: str


def source_hints(word: SourceWord) -> tuple[str, ...]:
    """Return the distinct normalized hints retained for review and alignment."""
    hints: list[str] = []
    for record in word.records:
        for raw_hint in record.definition.splitlines():
            hint = _NUMBERED_HINT.sub("", collapse_whitespace(raw_hint))
            if hint and hint not in hints:
                hints.append(hint)
    return tuple(hints)


def eligible_example_matches(
    word: SourceWord,
    candidate: SenseCandidate,
) -> tuple[ExampleMatch, ...]:
    """Return same-sense examples containing the exact source headword."""
    matches: list[ExampleMatch] = []
    for example_index, example in enumerate(candidate.examples):
        matched = match_example_text(
            word.normalized_term,
            candidate.part_of_speech,
            example.text,
        )
        if matched is None:
            continue
        matches.append(
            ExampleMatch(
                example=example,
                example_index=example_index,
                form=matched.form,
                surface=matched.surface,
            )
        )
    return tuple(matches)


def _alignment_tokens(value: str) -> set[str]:
    return {
        token
        for token in _ALIGNMENT_TOKEN.findall(collapse_whitespace(value).casefold())
        if token not in _STOPWORDS
    }


def _alignment_score(hint: str, candidate: SenseCandidate) -> float:
    normalized_hint = collapse_whitespace(hint).casefold()
    normalized_definition = collapse_whitespace(candidate.definition).casefold()
    normalized_members = {
        collapse_whitespace(member).casefold() for member in candidate.members
    }
    if normalized_hint == normalized_definition:
        return 1.0

    hint_tokens = _alignment_tokens(normalized_hint)
    candidate_tokens = _alignment_tokens(normalized_definition)
    for member in normalized_members:
        candidate_tokens.update(_alignment_tokens(member))
    if not hint_tokens or not candidate_tokens:
        return 0.0
    overlap = len(hint_tokens & candidate_tokens) / len(hint_tokens | candidate_tokens)
    sequence = SequenceMatcher(None, normalized_hint, normalized_definition).ratio()
    return max(overlap, overlap * 0.7 + sequence * 0.3)


def _is_exact_alignment(hint: str, candidate: SenseCandidate) -> bool:
    normalized_hint = collapse_whitespace(hint).casefold()
    return normalized_hint == collapse_whitespace(candidate.definition).casefold()


def _automatic_content_key(candidate: SenseCandidate) -> tuple[Any, ...]:
    return (
        collapse_whitespace(candidate.definition).casefold(),
        collapse_whitespace(candidate.part_of_speech).casefold(),
        tuple(example.text for example in candidate.examples),
        collapse_whitespace(candidate.pronunciation),
    )


def _accepts_automatic_alignment(
    hint: str,
    ranked: list[tuple[float, SenseCandidate]],
) -> bool:
    best_score, best = ranked[0]
    exact_matches = [
        candidate
        for _score, candidate in ranked
        if _is_exact_alignment(hint, candidate)
    ]
    if exact_matches:
        return (
            _is_exact_alignment(hint, best)
            and len({_automatic_content_key(candidate) for candidate in exact_matches})
            == 1
        )
    runner_up_score = ranked[1][0] if len(ranked) > 1 else 0.0
    return (
        best_score >= AUTO_ALIGNMENT_MINIMUM
        and best_score - runner_up_score >= AUTO_ALIGNMENT_MARGIN
    )


def auto_select_senses(
    word: SourceWord,
    candidates: tuple[SenseCandidate, ...],
) -> tuple[SenseSelection, ...] | None:
    """Select candidates only when every source hint aligns unambiguously."""
    selected: list[tuple[SenseCandidate, ExampleMatch]] = []
    selected_keys: set[tuple[str, str, str, int]] = set()
    for hint in source_hints(word):
        aligned: tuple[SenseCandidate, ExampleMatch] | None = None
        for provider in PROVIDER_PRIORITY:
            provider_candidates = [
                candidate for candidate in candidates if candidate.provider == provider
            ]
            if not provider_candidates:
                continue
            ranked = sorted(
                (
                    (_alignment_score(hint, candidate), candidate)
                    for candidate in provider_candidates
                ),
                key=lambda pair: (-pair[0], pair[1].selection_key),
            )
            _best_score, best = ranked[0]
            if not _accepts_automatic_alignment(hint, ranked):
                continue
            examples = eligible_example_matches(word, best)
            if examples:
                aligned = (best, examples[0])
                break
        if aligned is None:
            return None
        candidate, example_match = aligned
        if candidate.selection_key not in selected_keys:
            selected_keys.add(candidate.selection_key)
            selected.append((candidate, example_match))
    if not selected:
        return None
    return tuple(
        SenseSelection(
            provider=candidate.provider,
            provider_sense_id=candidate.provider_sense_id,
            provider_synset_id=candidate.provider_synset_id,
            definition_index=candidate.definition_index,
            example_index=example_match.example_index,
            candidate_sha256=candidate.content_digest,
        )
        for candidate, example_match in selected
    )
