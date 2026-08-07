"""Canonical text and identifier helpers for vocabulary artifacts."""

import hashlib
import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

WORD_ID_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://github.com/Aequor29/Crack-GRE-Vocab/vocabulary-word",
)

_HTML_TAG = re.compile(r"<[^>]+>")
_VERSION = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")


def collapse_whitespace(value: str) -> str:
    """Apply Unicode compatibility normalization and collapse whitespace."""
    return " ".join(unicodedata.normalize("NFKC", value).split())


def canonical_term(value: str) -> tuple[str, str]:
    """Return display and identity forms without removing accents."""
    term = collapse_whitespace(value)
    if not term:
        raise ValueError("word must not be empty")
    if len(term) > 128:
        raise ValueError("word must be at most 128 characters")
    if not all(character.isalpha() or character in {" ", "-"} for character in term):
        raise ValueError("word may contain only Unicode letters, spaces, and hyphens")
    if term.startswith("-") or term.endswith("-") or "--" in term:
        raise ValueError("word contains an invalid hyphen placement")

    normalized_term = term.casefold()
    if len(normalized_term) > 128:
        raise ValueError(
            "word identity must be at most 128 characters after casefolding"
        )
    return term, normalized_term


def canonical_prose(value: str, *, field: str, maximum: int) -> str:
    """Normalize one definition or example while rejecting markup and controls."""
    text = collapse_whitespace(value)
    if not text:
        raise ValueError(f"{field} must not be empty")
    if len(text) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters")
    if _HTML_TAG.search(text):
        raise ValueError(f"{field} must not contain HTML")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in text):
        raise ValueError(f"{field} must not contain control characters")
    return text


def canonical_version(value: str) -> str:
    """Validate an immutable corpus version label."""
    if not _VERSION.fullmatch(value):
        raise ValueError(
            "corpus version must start with a lowercase letter or digit and contain "
            "only lowercase letters, digits, dots, underscores, or hyphens"
        )
    return value


def stable_word_id(normalized_term: str) -> uuid.UUID:
    """Derive the initial stable identity for a normalized source term."""
    return uuid.uuid5(WORD_ID_NAMESPACE, normalized_term)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize repository artifacts deterministically as UTF-8 plus LF."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
