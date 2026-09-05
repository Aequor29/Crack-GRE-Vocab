"""Validate and audit the GRE vocabulary source list."""

import csv
import io
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import SourceAuditError
from .files import FileSnapshot
from .normalization import canonical_term

SOURCE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SourceRecord:
    """One validated retained-source row."""

    number: int
    term: str
    normalized_term: str
    definition: str


@dataclass(frozen=True)
class SourceWord:
    """One canonical word identity after reviewed duplicate collapse."""

    term: str
    normalized_term: str
    records: tuple[SourceRecord, ...]


@dataclass(frozen=True)
class SourceAudit:
    """Deterministic source findings and canonical words."""

    source_digest: str
    records: tuple[SourceRecord, ...]
    words: tuple[SourceWord, ...]
    duplicate_groups: tuple[SourceWord, ...]
    outer_whitespace_definitions: int
    multiline_definitions: int
    nonstandard_multiline_definitions: int
    exact_duplicate_rows: int
    sort_inversions: int
    normalized_term_changes: int

    def as_dict(self, *, source_path: str = "data/GRE_word.csv") -> dict[str, Any]:
        return {
            "schema_version": SOURCE_SCHEMA_VERSION,
            "source": {
                "header": ["word", "definition"],
                "path": source_path,
                "sha256": self.source_digest,
            },
            "counts": {
                "canonical_words": len(self.words),
                "exact_duplicate_rows": self.exact_duplicate_rows,
                "multiline_definitions": self.multiline_definitions,
                "nonstandard_multiline_definitions": (
                    self.nonstandard_multiline_definitions
                ),
                "normalized_term_changes": self.normalized_term_changes,
                "outer_whitespace_definitions": self.outer_whitespace_definitions,
                "source_rows": len(self.records),
                "sort_inversions": self.sort_inversions,
            },
            "duplicate_collapses": [
                {
                    "definitions": [record.definition for record in group.records],
                    "normalized_term": group.normalized_term,
                    "source_records": [record.number for record in group.records],
                }
                for group in self.duplicate_groups
            ],
        }


def _load_decisions(
    snapshot: FileSnapshot,
    *,
    source_digest: str,
) -> dict[str, tuple[int, ...]]:
    try:
        document = json.loads(snapshot.content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SourceAuditError(
            f"cannot read duplicate decisions at {snapshot.path}: {exc}"
        ) from exc

    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise SourceAuditError("duplicate decisions must use schema_version 1")
    if document.get("source_sha256") != source_digest:
        raise SourceAuditError(
            "duplicate decisions were not reviewed for the current GRE_word.csv digest"
        )
    collapses = document.get("collapse")
    if not isinstance(collapses, list):
        raise SourceAuditError("duplicate decisions must contain a collapse list")

    decisions: dict[str, tuple[int, ...]] = {}
    for item in collapses:
        if not isinstance(item, dict):
            raise SourceAuditError("each duplicate collapse decision must be an object")
        normalized_term = item.get("normalized_term")
        source_records = item.get("source_records")
        if not isinstance(normalized_term, str) or not isinstance(source_records, list):
            raise SourceAuditError(
                "each duplicate collapse needs normalized_term and source_records"
            )
        if normalized_term in decisions:
            raise SourceAuditError(f"duplicate decision for {normalized_term!r}")
        if not source_records or not all(
            isinstance(number, int) and number >= 1 for number in source_records
        ):
            raise SourceAuditError(
                f"duplicate decision for {normalized_term!r} has invalid source records"
            )
        decisions[normalized_term] = tuple(source_records)
    return decisions


def audit_source_snapshots(
    source: FileSnapshot,
    duplicate_decisions: FileSnapshot,
) -> SourceAudit:
    """Audit exact source and duplicate-decision bytes already read from disk."""
    records: list[SourceRecord] = []
    try:
        with io.StringIO(source.content.decode("utf-8"), newline="") as source_file:
            reader = csv.reader(source_file, strict=True)
            header = next(reader, None)
            if header != ["word", "definition"]:
                raise SourceAuditError(
                    "GRE_word.csv must have the exact header: word,definition"
                )
            for record_number, row in enumerate(reader, start=1):
                if len(row) != 2:
                    raise SourceAuditError(
                        f"source record {record_number} must contain exactly two "
                        "columns"
                    )
                raw_term, definition = row
                try:
                    term, normalized_term = canonical_term(raw_term)
                except ValueError as exc:
                    raise SourceAuditError(
                        f"source record {record_number} has an invalid word: {exc}"
                    ) from exc
                if not definition.strip():
                    raise SourceAuditError(
                        f"source record {record_number} has an empty definition hint"
                    )
                records.append(
                    SourceRecord(
                        number=record_number,
                        term=term,
                        normalized_term=normalized_term,
                        definition=definition,
                    )
                )
    except SourceAuditError:
        raise
    except (UnicodeError, csv.Error) as exc:
        raise SourceAuditError(f"cannot parse GRE_word.csv: {exc}") from exc

    if not records:
        raise SourceAuditError("GRE_word.csv must contain at least one word")

    grouped: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.normalized_term].append(record)

    decisions = _load_decisions(
        duplicate_decisions,
        source_digest=source.sha256,
    )
    actual_duplicates = {
        normalized_term: tuple(record.number for record in grouped_records)
        for normalized_term, grouped_records in grouped.items()
        if len(grouped_records) > 1
    }
    if decisions != actual_duplicates:
        missing = sorted(set(actual_duplicates) - set(decisions))
        obsolete = sorted(set(decisions) - set(actual_duplicates))
        mismatched = sorted(
            term
            for term in set(decisions) & set(actual_duplicates)
            if decisions[term] != actual_duplicates[term]
        )
        raise SourceAuditError(
            "duplicate decisions do not match the source "
            f"(missing={missing}, obsolete={obsolete}, mismatched={mismatched})"
        )

    words = tuple(
        SourceWord(
            term=grouped_records[0].term,
            normalized_term=normalized_term,
            records=tuple(grouped_records),
        )
        for normalized_term, grouped_records in sorted(grouped.items())
    )
    duplicate_groups = tuple(word for word in words if len(word.records) > 1)
    row_counts = Counter(
        (record.normalized_term, record.definition) for record in records
    )

    return SourceAudit(
        source_digest=source.sha256,
        records=tuple(records),
        words=words,
        duplicate_groups=duplicate_groups,
        outer_whitespace_definitions=sum(
            record.definition != record.definition.strip() for record in records
        ),
        multiline_definitions=sum(
            "\n" in record.definition or "\r" in record.definition for record in records
        ),
        nonstandard_multiline_definitions=sum(
            ("\n" in record.definition or "\r" in record.definition)
            and re.match(r"^\s*1[.]", record.definition) is None
            for record in records
        ),
        exact_duplicate_rows=sum(
            count - 1 for count in row_counts.values() if count > 1
        ),
        sort_inversions=sum(
            first.normalized_term > second.normalized_term
            for first, second in zip(records, records[1:], strict=False)
        ),
        normalized_term_changes=sum(
            record.term != record.normalized_term for record in records
        ),
    )


def audit_source(source_path: Path, duplicate_decisions_path: Path) -> SourceAudit:
    """Validate the source and require exact decisions for every duplicate term."""
    try:
        source = FileSnapshot.read(source_path)
    except OSError as exc:
        raise SourceAuditError(f"cannot parse GRE_word.csv: {exc}") from exc
    try:
        duplicate_decisions = FileSnapshot.read(duplicate_decisions_path)
    except OSError as exc:
        raise SourceAuditError(
            f"cannot read duplicate decisions at {duplicate_decisions_path}: {exc}"
        ) from exc
    return audit_source_snapshots(source, duplicate_decisions)
