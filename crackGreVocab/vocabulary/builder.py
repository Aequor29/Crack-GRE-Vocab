"""Strict offline review-queue and canonical corpus construction."""

import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .artifacts import (
    CORPUS_SCHEMA_VERSION,
    CanonicalSense,
    CanonicalWord,
    corpus_jsonl_bytes,
)
from .example_matching import (
    EXAMPLE_MATCH_POLICY_RULE,
    EXAMPLE_MATCH_POLICY_VERSION,
    match_example_text,
)
from .exceptions import CorpusBuildError, SnapshotError, SourceAuditError
from .normalization import (
    canonical_json_bytes,
    canonical_prose,
    canonical_term,
    canonical_version,
    collapse_whitespace,
    sha256_bytes,
    sha256_file,
    stable_word_id,
)
from .providers import (
    ProviderConfig,
    ProviderExample,
    SenseCandidate,
    load_cached_candidates,
    load_oewn_candidates,
    load_provider_registry,
)
from .source import SourceAudit, SourceWord, audit_source

DECISION_SCHEMA_VERSION = 3
REVIEW_QUEUE_SCHEMA_VERSION = 2
AUTO_ALIGNMENT_POLICY_VERSION = 2
AUTO_ALIGNMENT_MINIMUM = 0.60
AUTO_ALIGNMENT_MARGIN = 0.20
EDITORIAL_PARTS_OF_SPEECH = frozenset(
    {
        "adjective",
        "adverb",
        "conjunction",
        "determiner",
        "interjection",
        "noun",
        "preposition",
        "pronoun",
        "verb",
    }
)
EDITORIAL_REPLACEMENT_MODES = frozenset({"none", "source-contamination"})
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
class SenseSelection:
    provider: str
    provider_sense_id: str
    provider_synset_id: str
    definition_index: int
    example_index: int
    candidate_sha256: str
    source_hints: tuple[str, ...]

    @property
    def candidate_key(self) -> tuple[str, str, str, int]:
        return (
            self.provider,
            self.provider_sense_id,
            self.provider_synset_id,
            self.definition_index,
        )


@dataclass(frozen=True)
class RejectedSourceHint:
    source_hint: str
    rationale: str


@dataclass(frozen=True)
class ProviderWordDecision:
    senses: tuple[SenseSelection, ...]
    rejected_source_hints: tuple[RejectedSourceHint, ...]


ProviderDecisionInput = ProviderWordDecision | tuple[SenseSelection, ...]


@dataclass(frozen=True)
class EditorialSense:
    editorial_id: str
    part_of_speech: str
    definition: str
    example: str
    source_hints: tuple[str, ...]


@dataclass(frozen=True)
class EditorialWord:
    pronunciation: str
    replacement_mode: str
    senses: tuple[EditorialSense, ...]
    rejected_source_hints: tuple[RejectedSourceHint, ...]


@dataclass(frozen=True)
class ExampleMatch:
    example: ProviderExample
    example_index: int
    form: str
    surface: str


@dataclass(frozen=True)
class BuildInputs:
    source_path: Path
    duplicate_decisions_path: Path
    provider_registry_path: Path
    oewn_archive_path: Path
    sense_decisions_path: Path
    editorial_overrides_path: Path
    fallback_cache_path: Path


def _load_document(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusBuildError(f"cannot read {label} at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusBuildError(f"{label} must be a JSON object")
    return value


def _parse_rejected_source_hints(
    value: object,
    *,
    label: str,
) -> tuple[RejectedSourceHint, ...]:
    if not isinstance(value, list):
        raise CorpusBuildError(f"{label} rejected_source_hints must be a list")
    parsed: list[RejectedSourceHint] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {"rationale", "source_hint"}:
            raise CorpusBuildError(
                f"{label} rejected source hints must contain exactly "
                "source_hint and rationale"
            )
        raw_source_hint = item["source_hint"]
        raw_rationale = item["rationale"]
        if not isinstance(raw_source_hint, str):
            raise CorpusBuildError(f"{label} rejected source hint must be a string")
        source_hint = collapse_whitespace(raw_source_hint)
        if not source_hint or source_hint != raw_source_hint:
            raise CorpusBuildError(
                f"{label} rejected source hint must be non-empty and canonical"
            )
        if source_hint in seen:
            raise CorpusBuildError(
                f"{label} rejects source hint {source_hint!r} more than once"
            )
        try:
            rationale = canonical_prose(
                raw_rationale,
                field="rejection rationale",
                maximum=1000,
            )
        except (TypeError, ValueError) as exc:
            raise CorpusBuildError(
                f"invalid {label} rejection rationale: {exc}"
            ) from exc
        if rationale != raw_rationale:
            raise CorpusBuildError(f"{label} rejection rationale must be canonical")
        seen.add(source_hint)
        parsed.append(
            RejectedSourceHint(
                source_hint=source_hint,
                rationale=rationale,
            )
        )
    return tuple(parsed)


def load_sense_decisions(
    path: Path,
    *,
    source_digest: str,
) -> dict[str, ProviderWordDecision]:
    document = _load_document(path, label="sense decisions")
    if set(document) != {"schema_version", "selections", "source_sha256"}:
        raise CorpusBuildError("sense decisions have invalid top-level fields")
    if document.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise CorpusBuildError(
            f"sense decisions must use schema_version {DECISION_SCHEMA_VERSION}"
        )
    if document.get("source_sha256") != source_digest:
        raise CorpusBuildError("sense decisions do not match the current source digest")
    raw_selections = document.get("selections")
    if not isinstance(raw_selections, dict):
        raise CorpusBuildError("sense decisions must contain a selections object")
    selections: dict[str, ProviderWordDecision] = {}
    for normalized_term, raw_word in raw_selections.items():
        if not isinstance(normalized_term, str) or not isinstance(raw_word, dict):
            raise CorpusBuildError("sense selection keys and entries are invalid")
        try:
            term, identity = canonical_term(normalized_term)
        except ValueError as exc:
            raise CorpusBuildError(f"invalid sense decision term: {exc}") from exc
        if term != normalized_term or identity != normalized_term:
            raise CorpusBuildError(
                f"sense decision key {normalized_term!r} is not normalized"
            )
        if set(raw_word) != {"rejected_source_hints", "senses"}:
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} has invalid fields"
            )
        raw_items = raw_word["senses"]
        if not isinstance(raw_items, list):
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} senses must be a list"
            )
        rejected_source_hints = _parse_rejected_source_hints(
            raw_word["rejected_source_hints"],
            label=f"sense decision for {normalized_term!r}",
        )
        parsed: list[SenseSelection] = []
        for item in raw_items:
            if not isinstance(item, dict) or set(item) != {
                "candidate_sha256",
                "definition_index",
                "example_index",
                "provider",
                "provider_sense_id",
                "provider_synset_id",
                "source_hints",
            }:
                raise CorpusBuildError(
                    f"sense decision for {normalized_term!r} has invalid fields"
                )
            raw_source_hints = item["source_hints"]
            if (
                not all(
                    isinstance(item[field], str)
                    for field in (
                        "candidate_sha256",
                        "provider",
                        "provider_sense_id",
                        "provider_synset_id",
                    )
                )
                or not all(
                    isinstance(item[field], int)
                    and not isinstance(item[field], bool)
                    and item[field] >= 0
                    for field in ("definition_index", "example_index")
                )
                or not isinstance(raw_source_hints, list)
            ):
                raise CorpusBuildError(
                    f"sense decision for {normalized_term!r} has invalid values"
                )
            source_hints = tuple(
                collapse_whitespace(hint)
                for hint in raw_source_hints
                if isinstance(hint, str) and collapse_whitespace(hint)
            )
            if (
                not source_hints
                or len(source_hints) != len(raw_source_hints)
                or len(set(source_hints)) != len(source_hints)
                or any(
                    hint != raw_hint
                    for hint, raw_hint in zip(
                        source_hints,
                        raw_source_hints,
                        strict=True,
                    )
                )
            ):
                raise CorpusBuildError(
                    f"sense decision for {normalized_term!r} has invalid source hints"
                )
            parsed.append(
                SenseSelection(
                    provider=item["provider"],
                    provider_sense_id=item["provider_sense_id"],
                    provider_synset_id=item["provider_synset_id"],
                    definition_index=item["definition_index"],
                    example_index=item["example_index"],
                    candidate_sha256=item["candidate_sha256"],
                    source_hints=source_hints,
                )
            )
        if not parsed:
            if rejected_source_hints:
                raise CorpusBuildError(
                    f"sense decision for {normalized_term!r} has orphan rejected "
                    "source hints without a retained sense"
                )
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} must select at least one sense"
            )
        if len({selection.candidate_key for selection in parsed}) != len(parsed):
            raise CorpusBuildError(
                f"sense decision for {normalized_term!r} selects a sense twice"
            )
        selections[normalized_term] = ProviderWordDecision(
            senses=tuple(parsed),
            rejected_source_hints=rejected_source_hints,
        )
    return selections


def load_editorial_overrides(
    path: Path,
    *,
    source_digest: str,
) -> dict[str, EditorialWord]:
    document = _load_document(path, label="editorial overrides")
    if set(document) != {"schema_version", "source_sha256", "words"}:
        raise CorpusBuildError("editorial overrides have invalid top-level fields")
    if document.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise CorpusBuildError(
            f"editorial overrides must use schema_version {DECISION_SCHEMA_VERSION}"
        )
    if document.get("source_sha256") != source_digest:
        raise CorpusBuildError("editorial overrides do not match the source digest")
    raw_words = document.get("words")
    if not isinstance(raw_words, dict):
        raise CorpusBuildError("editorial overrides must contain a words object")
    overrides: dict[str, EditorialWord] = {}
    editorial_ids: set[str] = set()
    for normalized_term, raw_word in raw_words.items():
        if not isinstance(normalized_term, str) or not isinstance(raw_word, dict):
            raise CorpusBuildError("editorial override entries must be objects")
        try:
            term, identity = canonical_term(normalized_term)
        except ValueError as exc:
            raise CorpusBuildError(f"invalid editorial override term: {exc}") from exc
        if term != normalized_term or identity != normalized_term:
            raise CorpusBuildError(
                f"editorial override key {normalized_term!r} is not normalized"
            )
        if set(raw_word) != {
            "pronunciation",
            "rejected_source_hints",
            "replacement_mode",
            "senses",
        }:
            raise CorpusBuildError(
                f"editorial override for {normalized_term!r} has invalid fields"
            )
        rejected_source_hints = _parse_rejected_source_hints(
            raw_word["rejected_source_hints"],
            label=f"editorial override for {normalized_term!r}",
        )
        pronunciation = raw_word["pronunciation"]
        if not isinstance(pronunciation, str):
            raise CorpusBuildError(
                f"editorial pronunciation for {normalized_term!r} must be a string"
            )
        pronunciation = collapse_whitespace(pronunciation)
        if len(pronunciation) > 255:
            raise CorpusBuildError(
                f"editorial pronunciation for {normalized_term!r} is too long"
            )
        replacement_mode = raw_word["replacement_mode"]
        if replacement_mode not in EDITORIAL_REPLACEMENT_MODES:
            raise CorpusBuildError(
                f"editorial override for {normalized_term!r} has an invalid "
                "replacement_mode"
            )
        raw_senses = raw_word["senses"]
        if not isinstance(raw_senses, list):
            raise CorpusBuildError(
                f"editorial override for {normalized_term!r} senses must be a list"
            )
        if not raw_senses:
            if rejected_source_hints:
                raise CorpusBuildError(
                    f"editorial override for {normalized_term!r} has orphan rejected "
                    "source hints without a retained sense"
                )
            raise CorpusBuildError(
                f"editorial override for {normalized_term!r} needs senses"
            )
        senses: list[EditorialSense] = []
        for raw_sense in raw_senses:
            if not isinstance(raw_sense, dict) or set(raw_sense) != {
                "definition",
                "editorial_id",
                "example",
                "part_of_speech",
                "source_hints",
            }:
                raise CorpusBuildError(
                    f"editorial sense for {normalized_term!r} has invalid fields"
                )
            editorial_id = raw_sense["editorial_id"]
            part_of_speech = raw_sense["part_of_speech"]
            raw_source_hints = raw_sense["source_hints"]
            if not isinstance(editorial_id, str) or not editorial_id:
                raise CorpusBuildError("editorial_id must be a non-empty string")
            if editorial_id in editorial_ids:
                raise CorpusBuildError(f"duplicate editorial_id {editorial_id!r}")
            editorial_ids.add(editorial_id)
            if not isinstance(part_of_speech, str):
                raise CorpusBuildError("editorial part_of_speech must be a string")
            canonical_part_of_speech = collapse_whitespace(part_of_speech)
            if (
                canonical_part_of_speech != part_of_speech
                or part_of_speech not in EDITORIAL_PARTS_OF_SPEECH
            ):
                raise CorpusBuildError(
                    "editorial part_of_speech must be a canonical supported value"
                )
            if not isinstance(raw_source_hints, list):
                raise CorpusBuildError("editorial source_hints must be a list")
            source_hints = tuple(
                collapse_whitespace(hint)
                for hint in raw_source_hints
                if isinstance(hint, str) and collapse_whitespace(hint)
            )
            if (
                len(source_hints) != len(raw_source_hints)
                or len(set(source_hints)) != len(source_hints)
                or any(
                    hint != raw_hint
                    for hint, raw_hint in zip(
                        source_hints,
                        raw_source_hints,
                        strict=True,
                    )
                )
            ):
                raise CorpusBuildError("editorial source_hints are invalid")
            try:
                definition = canonical_prose(
                    raw_sense["definition"],
                    field="definition",
                    maximum=1000,
                )
                example = canonical_prose(
                    raw_sense["example"],
                    field="example",
                    maximum=1000,
                )
            except (TypeError, ValueError) as exc:
                raise CorpusBuildError(
                    f"invalid editorial sense for {normalized_term!r}: {exc}"
                ) from exc
            senses.append(
                EditorialSense(
                    editorial_id=editorial_id,
                    part_of_speech=part_of_speech,
                    definition=definition,
                    example=example,
                    source_hints=source_hints,
                )
            )
        overrides[normalized_term] = EditorialWord(
            pronunciation=pronunciation,
            replacement_mode=replacement_mode,
            senses=tuple(senses),
            rejected_source_hints=rejected_source_hints,
        )
    return overrides


def load_build_context(
    inputs: BuildInputs,
) -> tuple[
    SourceAudit,
    dict[str, ProviderConfig],
    dict[str, tuple[SenseCandidate, ...]],
    dict[str, ProviderWordDecision],
    dict[str, EditorialWord],
]:
    """Load every local input without importing any network helper."""
    try:
        audit = audit_source(inputs.source_path, inputs.duplicate_decisions_path)
        registry = load_provider_registry(inputs.provider_registry_path)
        oewn_config = registry["oewn-2025"]
        source_terms = {word.normalized_term for word in audit.words}
        candidates: dict[str, list[SenseCandidate]] = defaultdict(list)
        for term, values in load_oewn_candidates(
            inputs.oewn_archive_path,
            oewn_config,
            source_terms,
        ).items():
            candidates[term].extend(values)
        for term, values in load_cached_candidates(
            inputs.fallback_cache_path,
            registry,
        ).items():
            if term not in source_terms:
                raise CorpusBuildError(
                    f"fallback cache contains non-source term {term!r}"
                )
            candidates[term].extend(values)
    except (SourceAuditError, SnapshotError, KeyError) as exc:
        raise CorpusBuildError(str(exc)) from exc
    selections = load_sense_decisions(
        inputs.sense_decisions_path,
        source_digest=audit.source_digest,
    )
    overrides = load_editorial_overrides(
        inputs.editorial_overrides_path,
        source_digest=audit.source_digest,
    )
    unknown_decisions = sorted((set(selections) | set(overrides)) - source_terms)
    if unknown_decisions:
        raise CorpusBuildError(
            f"reviewed content contains non-source terms: {unknown_decisions[:10]}"
        )
    overlap = sorted(set(selections) & set(overrides))
    if overlap:
        raise CorpusBuildError(
            f"terms cannot have both provider selections and overrides: {overlap[:10]}"
        )
    priorities = {provider.id: provider.priority for provider in registry.values()}
    frozen_candidates = {
        term: tuple(
            sorted(
                values,
                key=lambda candidate: (
                    priorities[candidate.provider],
                    candidate.selection_key,
                ),
            )
        )
        for term, values in candidates.items()
    }
    return audit, registry, frozen_candidates, selections, overrides


def _source_hints(word: SourceWord) -> list[str]:
    hints: list[str] = []
    for record in word.records:
        for raw_hint in record.definition.splitlines():
            hint = _NUMBERED_HINT.sub("", collapse_whitespace(raw_hint))
            if hint and hint not in hints:
                hints.append(hint)
    return hints


def _provider_decision_parts(
    decision: ProviderDecisionInput,
) -> tuple[tuple[SenseSelection, ...], tuple[RejectedSourceHint, ...]]:
    if isinstance(decision, ProviderWordDecision):
        return decision.senses, decision.rejected_source_hints
    return decision, ()


def _rejection_provenance(
    rejected_source_hints: tuple[RejectedSourceHint, ...],
) -> list[dict[str, str]]:
    return [
        {
            "rationale": disposition.rationale,
            "source_hint": disposition.source_hint,
        }
        for disposition in rejected_source_hints
    ]


def _validate_source_hint_dispositions(
    word: SourceWord,
    selected_hints: list[str],
    rejected_source_hints: tuple[RejectedSourceHint, ...],
    *,
    label: str,
) -> None:
    expected = set(_source_hints(word))
    selected = set(selected_hints)
    rejected_values = [item.source_hint for item in rejected_source_hints]
    rejected = set(rejected_values)
    if len(selected_hints) != len(selected):
        raise CorpusBuildError(f"{label} covers a source hint more than once")
    if len(rejected_values) != len(rejected):
        raise CorpusBuildError(f"{label} rejects a source hint more than once")
    overlap = sorted(selected & rejected)
    if overlap:
        raise CorpusBuildError(
            f"{label} both retains and rejects source hints: {overlap[:10]}"
        )
    unknown = sorted((selected | rejected) - expected)
    if unknown:
        raise CorpusBuildError(
            f"{label} contains unknown source hints: {unknown[:10]}"
        )
    missing = sorted(expected - selected - rejected)
    if missing:
        raise CorpusBuildError(
            f"{label} does not dispose every source hint; missing: {missing[:10]}"
        )


def _eligible_example_matches(
    word: SourceWord,
    candidate: SenseCandidate,
) -> tuple[ExampleMatch, ...]:
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
    """Score only lexical evidence from the retained definition hints."""
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
    sequence = SequenceMatcher(
        None,
        normalized_hint,
        normalized_definition,
    ).ratio()
    return max(overlap, overlap * 0.7 + sequence * 0.3)


def _is_exact_alignment(hint: str, candidate: SenseCandidate) -> bool:
    """Return whether retained text exactly matches a provider definition."""
    normalized_hint = collapse_whitespace(hint).casefold()
    return normalized_hint == collapse_whitespace(candidate.definition).casefold()


def _automatic_content_key(candidate: SenseCandidate) -> tuple[Any, ...]:
    """Identify semantic content without relying on provider sense ordering."""
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
    """Fail closed unless the best sense is both strong and unambiguous."""
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
    """Align every source hint before accepting any provider-local example."""
    selected: list[tuple[SenseCandidate, ExampleMatch, list[str]]] = []
    hints = _source_hints(word)
    for hint in hints:
        aligned: tuple[SenseCandidate, ExampleMatch] | None = None
        for provider in (
            "oewn-2025",
            "freedictionaryapi-v1",
            "dictionaryapi-dev-v2",
        ):
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
            eligible_examples = _eligible_example_matches(word, best)
            if eligible_examples:
                aligned = (best, eligible_examples[0])
                break
            # The best-aligned provider sense has no example. Continue to the
            # next provider rather than borrowing an example from another sense.
        if aligned is None:
            return None
        candidate, example_match = aligned
        existing = next(
            (
                item
                for item in selected
                if item[0].selection_key == candidate.selection_key
            ),
            None,
        )
        if existing is None:
            selected.append((candidate, example_match, [hint]))
        else:
            existing[2].append(hint)
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
            source_hints=tuple(source_hints),
        )
        for candidate, example_match, source_hints in selected
    )


def review_queue_document(
    audit: SourceAudit,
    candidates: dict[str, tuple[SenseCandidate, ...]],
    selections: Mapping[str, ProviderDecisionInput],
    overrides: dict[str, EditorialWord],
) -> dict[str, Any]:
    """Return only unresolved words and their same-sense candidate material."""
    items: list[dict[str, Any]] = []
    auto_resolved = 0
    fallback_required = 0
    review_required = 0
    single_eligible_candidate = 0
    multiple_eligible_candidates = 0
    no_headword_example = 0
    no_same_sense_example = 0
    without_candidates = 0
    for word in audit.words:
        selection = selections.get(word.normalized_term)
        override = overrides.get(word.normalized_term)
        values = candidates.get(word.normalized_term, ())
        if selection is not None:
            _resolved_word(
                word,
                values,
                selection,
                None,
                position=1,
            )
            continue
        if override is not None:
            _resolved_word(
                word,
                (),
                None,
                override,
                position=1,
            )
            continue
        if auto_select_senses(word, values) is not None:
            auto_resolved += 1
            continue
        eligible_by_candidate = {
            candidate.selection_key: _eligible_example_matches(word, candidate)
            for candidate in values
        }
        paired_candidate_count = sum(bool(candidate.examples) for candidate in values)
        eligible_candidate_count = sum(
            bool(matches) for matches in eligible_by_candidate.values()
        )
        needs_fallback = eligible_candidate_count == 0
        if needs_fallback:
            fallback_required += 1
            if not values:
                without_candidates += 1
                reason = "no-provider-candidates"
            elif paired_candidate_count == 0:
                no_same_sense_example += 1
                reason = "no-same-sense-example"
            else:
                no_headword_example += 1
                reason = "no-headword-example"
        else:
            review_required += 1
            if eligible_candidate_count == 1:
                single_eligible_candidate += 1
                reason = "low-confidence-source-alignment"
            else:
                multiple_eligible_candidates += 1
                reason = "ambiguous-source-alignment"
        items.append(
            {
                "candidates": [
                    {
                        "candidate_sha256": candidate.content_digest,
                        "eligible_example_indexes": [
                            match.example_index
                            for match in eligible_by_candidate[candidate.selection_key]
                        ],
                        **candidate.as_review_dict(),
                    }
                    for candidate in values
                ],
                "fallback_required": needs_fallback,
                "eligible_candidate_count": eligible_candidate_count,
                "normalized_term": word.normalized_term,
                "paired_candidate_count": paired_candidate_count,
                "reason": reason,
                "review_required": not needs_fallback,
                "source_hints": _source_hints(word),
                "term": word.term,
            }
        )
    return {
        "automatic_alignment": {
            "exact_match_policy": "unique-definition-content-equivalent",
            "minimum_margin": AUTO_ALIGNMENT_MARGIN,
            "minimum_score": AUTO_ALIGNMENT_MINIMUM,
            "policy_version": AUTO_ALIGNMENT_POLICY_VERSION,
        },
        "example_matching": {
            "policy_version": EXAMPLE_MATCH_POLICY_VERSION,
            "rule": EXAMPLE_MATCH_POLICY_RULE,
        },
        "items": items,
        "schema_version": REVIEW_QUEUE_SCHEMA_VERSION,
        "source_sha256": audit.source_digest,
        "summary": {
            "fallback_required": fallback_required,
            "multiple_eligible_candidates": multiple_eligible_candidates,
            "no_headword_example": no_headword_example,
            "no_same_sense_example": no_same_sense_example,
            "resolved_automatically": auto_resolved,
            "resolved_by_override": len(overrides),
            "resolved_by_selection": len(selections),
            "review_required": review_required,
            "single_eligible_candidate": single_eligible_candidate,
            "unresolved": len(items),
            "without_candidates": without_candidates,
        },
    }


def _resolved_word(
    word: SourceWord,
    candidates: tuple[SenseCandidate, ...],
    selections: ProviderDecisionInput | None,
    override: EditorialWord | None,
    *,
    position: int,
) -> CanonicalWord | None:
    if override is not None:
        if not override.senses:
            if override.rejected_source_hints:
                raise CorpusBuildError(
                    f"editorial override for {word.term!r} has orphan rejected "
                    "source hints without a retained sense"
                )
            raise CorpusBuildError(
                f"editorial override for {word.term!r} needs a retained sense"
            )
        covered_hints = [
            hint for sense in override.senses for hint in sense.source_hints
        ]
        unanchored_senses = [
            sense for sense in override.senses if not sense.source_hints
        ]
        if unanchored_senses and (
            len(unanchored_senses) != 1 or covered_hints
        ):
            raise CorpusBuildError(
                f"editorial override for {word.term!r} may use exactly one "
                "unanchored replacement sense only when every source hint is "
                "rejected"
            )
        if unanchored_senses and override.replacement_mode != "source-contamination":
            raise CorpusBuildError(
                f"editorial override for {word.term!r} needs explicit "
                "source-contamination replacement_mode"
            )
        if not unanchored_senses and override.replacement_mode != "none":
            raise CorpusBuildError(
                f"editorial override for {word.term!r} uses replacement_mode "
                "without an unanchored replacement sense"
            )
        _validate_source_hint_dispositions(
            word,
            covered_hints,
            override.rejected_source_hints,
            label=f"editorial override for {word.term!r}",
        )
        rejected_provenance = _rejection_provenance(
            override.rejected_source_hints
        )
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
                        "rejected_source_hints": rejected_provenance,
                        "replacement_mode": override.replacement_mode,
                        "reviewed": True,
                        "selection_mode": "editorial",
                        "source_hints": list(sense.source_hints),
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
    rejected_source_hints: tuple[RejectedSourceHint, ...] = ()
    if selections is None:
        selected_senses = auto_select_senses(word, candidates)
        if selected_senses is None:
            return None
        selection_mode = "automatic"
    else:
        selected_senses, rejected_source_hints = _provider_decision_parts(selections)
        if not selected_senses:
            if rejected_source_hints:
                raise CorpusBuildError(
                    f"sense decision for {word.term!r} has orphan rejected source "
                    "hints without a retained sense"
                )
            raise CorpusBuildError(
                f"sense decision for {word.term!r} needs a retained sense"
            )

    covered_hints = [
        hint for selection in selected_senses for hint in selection.source_hints
    ]
    _validate_source_hint_dispositions(
        word,
        covered_hints,
        rejected_source_hints,
        label=f"sense selections for {word.term!r}",
    )
    rejected_provenance = _rejection_provenance(rejected_source_hints)

    by_key = {candidate.selection_key: candidate for candidate in candidates}
    resolved: list[tuple[SenseCandidate, ExampleMatch, str, str, tuple[str, ...]]] = []
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
                for match in _eligible_example_matches(word, candidate)
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
        resolved.append(
            (
                candidate,
                example_match,
                part_of_speech,
                pronunciation,
                selection.source_hints,
            )
        )
    if len(
        {
            (candidate.definition, example_match.example.text)
            for (
                candidate,
                example_match,
                _part_of_speech,
                _pronunciation,
                _hints,
            ) in resolved
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
                "rejected_source_hints": rejected_provenance,
                "selection_mode": selection_mode,
                "source_hints": list(source_hints),
            },
        )
        for sense_position, (
            candidate,
            example_match,
            part_of_speech,
            _pronunciation,
            source_hints,
        ) in enumerate(
            resolved,
            start=1,
        )
    )
    pronunciation = next(
        (
            pronunciation
            for (
                _candidate,
                _example_match,
                _part_of_speech,
                pronunciation,
                _hints,
            ) in resolved
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
    selections: Mapping[str, ProviderDecisionInput],
    overrides: dict[str, EditorialWord],
) -> tuple[CanonicalWord, ...]:
    words: list[CanonicalWord] = []
    unresolved: list[str] = []
    for position, word in enumerate(audit.words, start=1):
        resolved = _resolved_word(
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


def _input_digests(inputs: BuildInputs) -> dict[str, str]:
    paths = {
        "duplicate_decisions_sha256": inputs.duplicate_decisions_path,
        "editorial_overrides_sha256": inputs.editorial_overrides_path,
        "oewn_archive_sha256": inputs.oewn_archive_path,
        "provider_registry_sha256": inputs.provider_registry_path,
        "sense_decisions_sha256": inputs.sense_decisions_path,
    }
    if inputs.fallback_cache_path.exists():
        paths["fallback_cache_sha256"] = inputs.fallback_cache_path
    values: dict[str, str] = {}
    for label, path in paths.items():
        try:
            values[label] = sha256_file(path)
        except OSError as exc:
            raise CorpusBuildError(
                f"cannot hash build input {label} at {path}: {exc}"
            ) from exc
    return values


def _provenance_digests(inputs: BuildInputs) -> dict[str, str]:
    try:
        source_digest = sha256_file(inputs.source_path)
    except OSError as exc:
        raise CorpusBuildError(
            f"cannot hash build input source_sha256 at {inputs.source_path}: {exc}"
        ) from exc
    return {"source_sha256": source_digest, **_input_digests(inputs)}


def build_manifest(
    *,
    version: str,
    audit: SourceAudit,
    words: tuple[CanonicalWord, ...],
    corpus_digest: str,
    input_digests: Mapping[str, str],
) -> dict[str, Any]:
    try:
        corpus_version = canonical_version(version)
    except (TypeError, ValueError) as exc:
        raise CorpusBuildError(str(exc)) from exc
    return {
        "corpus": {
            "file": "corpus.jsonl",
            "sense_count": sum(len(word.senses) for word in words),
            "sha256": corpus_digest,
            "word_count": len(words),
        },
        "corpus_version": corpus_version,
        "inputs": dict(input_digests),
        "schema_version": CORPUS_SCHEMA_VERSION,
        "source": {
            "canonical_word_count": len(audit.words),
            "row_count": len(audit.records),
            "sha256": audit.source_digest,
        },
    }


def write_artifact_directory(
    output_directory: Path,
    *,
    corpus_content: bytes,
    manifest_content: bytes,
) -> bool:
    """Create an immutable version directory; identical reruns are a no-op."""
    if output_directory.exists():
        try:
            unchanged = (
                output_directory / "corpus.jsonl"
            ).read_bytes() == corpus_content and (
                output_directory / "manifest.json"
            ).read_bytes() == manifest_content
        except OSError:
            unchanged = False
        if unchanged:
            return False
        raise CorpusBuildError(
            f"immutable corpus directory already exists with different content: "
            f"{output_directory}"
        )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = Path(
        tempfile.mkdtemp(
            dir=output_directory.parent,
            prefix=f".{output_directory.name}.",
        )
    )
    try:
        (temporary_directory / "corpus.jsonl").write_bytes(corpus_content)
        (temporary_directory / "manifest.json").write_bytes(manifest_content)
        os.replace(temporary_directory, output_directory)
    except BaseException:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    return True


def build_artifacts(
    inputs: BuildInputs,
    *,
    version: str,
    output_directory: Path,
) -> bool:
    """Build only from checksum-verified local files, without network access."""
    initial_digests = _provenance_digests(inputs)
    audit, _registry, candidates, selections, overrides = load_build_context(inputs)
    words = build_corpus_words(audit, candidates, selections, overrides)
    corpus_content = corpus_jsonl_bytes(words)
    final_digests = _provenance_digests(inputs)
    changed_inputs = {
        label
        for label in initial_digests.keys() | final_digests.keys()
        if initial_digests.get(label) != final_digests.get(label)
    }
    if audit.source_digest != initial_digests["source_sha256"]:
        changed_inputs.add("source_sha256")
    if changed_inputs:
        raise CorpusBuildError(
            "build inputs changed while the corpus was being built; retry with "
            f"stable local inputs: {sorted(changed_inputs)}"
        )
    manifest = build_manifest(
        version=version,
        audit=audit,
        words=words,
        corpus_digest=sha256_bytes(corpus_content),
        input_digests={
            label: digest
            for label, digest in final_digests.items()
            if label != "source_sha256"
        },
    )
    return write_artifact_directory(
        output_directory,
        corpus_content=corpus_content,
        manifest_content=canonical_json_bytes(manifest),
    )


def write_review_queue(path: Path, document: dict[str, Any]) -> None:
    """Replace a generated queue atomically without touching reviewed decisions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(canonical_json_bytes(document))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
