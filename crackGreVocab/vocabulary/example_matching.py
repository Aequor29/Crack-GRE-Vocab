"""Shared learner-facing headword/example matching policy."""

import re
from dataclasses import dataclass

from .normalization import collapse_whitespace

EXAMPLE_MATCH_POLICY_VERSION = 3
EXAMPLE_MATCH_POLICY_RULE = "whole-token-exact-headword-with-exact-phrase-separators"
_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class ExampleSurfaceMatch:
    form: str
    surface: str


def match_example_text(
    normalized_term: str,
    _part_of_speech: str,
    example: str,
) -> ExampleSurfaceMatch | None:
    """Match the exact headword with Unicode-aware boundaries and separators."""
    term = collapse_whitespace(normalized_term)
    text = collapse_whitespace(example)
    term_matches = list(_TOKEN.finditer(term))
    text_matches = list(_TOKEN.finditer(text))
    if not term_matches:
        return None
    target_tokens = [match.group(0).casefold() for match in term_matches]
    text_tokens = [match.group(0).casefold() for match in text_matches]

    if len(term_matches) > 1:
        separators = [
            term[first.end() : second.start()]
            for first, second in zip(
                term_matches[:-1],
                term_matches[1:],
                strict=True,
            )
        ]
        for start in range(len(text_matches) - len(term_matches) + 1):
            end = start + len(term_matches)
            if text_tokens[start:end] != target_tokens:
                continue
            actual_separators = [
                text[first.end() : second.start()]
                for first, second in zip(
                    text_matches[start : end - 1],
                    text_matches[start + 1 : end],
                    strict=True,
                )
            ]
            if actual_separators == separators:
                surface = text[
                    text_matches[start].start() : text_matches[end - 1].end()
                ]
                return ExampleSurfaceMatch(form="exact", surface=surface)
        return None

    for token, match in zip(text_tokens, text_matches, strict=True):
        if token == target_tokens[0]:
            return ExampleSurfaceMatch(form="exact", surface=match.group(0))
    return None
