"""Stable learner-specific ordering of new Words."""

import hashlib
import json
from collections.abc import Iterable
from heapq import nsmallest
from uuid import UUID


def select_new_word_ids(
    word_ids: Iterable[UUID],
    *,
    learner_id: int,
    corpus_version: str,
    planner_version: str,
    limit: int,
) -> tuple[UUID, ...]:
    """Select a stable learner-specific prefix from eligible Word identities.

    SHA-256 ranks are independent of input order and Python's hash seed. The
    Word UUID breaks digest ties. Streaming top-K selection takes O(U log K)
    time and O(K) working memory for U candidates (O(U) time when K is one).
    """
    if limit <= 0:
        return ()
    namespace = json.dumps(
        [planner_version, str(learner_id), corpus_version],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    ranked = (
        (hashlib.sha256(namespace + word_id.bytes).digest(), word_id)
        for word_id in word_ids
    )
    return tuple(word_id for _, word_id in nsmallest(limit, ranked))
