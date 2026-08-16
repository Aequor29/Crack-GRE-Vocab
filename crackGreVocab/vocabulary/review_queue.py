"""Deterministic review queue generation for unresolved corpus words."""

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .alignment import (
    AUTO_ALIGNMENT_MARGIN,
    AUTO_ALIGNMENT_MINIMUM,
    AUTO_ALIGNMENT_POLICY_VERSION,
    auto_select_senses,
    eligible_example_matches,
    source_hints,
)
from .decisions import EditorialWord, ProviderWordDecision
from .example_matching import EXAMPLE_MATCH_POLICY_RULE, EXAMPLE_MATCH_POLICY_VERSION
from .normalization import canonical_json_bytes
from .providers import SenseCandidate
from .resolution import resolve_word
from .source import SourceAudit

REVIEW_QUEUE_SCHEMA_VERSION = 2


def build_review_queue(
    audit: SourceAudit,
    candidates: dict[str, tuple[SenseCandidate, ...]],
    selections: Mapping[str, ProviderWordDecision],
    overrides: dict[str, EditorialWord],
) -> dict[str, Any]:
    """Return unresolved words and the exact candidate material needed to review."""
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
            resolve_word(word, values, selection, None, position=1)
            continue
        if override is not None:
            resolve_word(word, (), None, override, position=1)
            continue
        if auto_select_senses(word, values) is not None:
            auto_resolved += 1
            continue

        eligible_by_candidate = {
            candidate.selection_key: eligible_example_matches(word, candidate)
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
                "source_hints": list(source_hints(word)),
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
