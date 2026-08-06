"""Fetch an explicit, bounded, resumable set of fallback responses."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from vocabulary.exceptions import EnrichmentFetchError, SnapshotError
from vocabulary.fetching import fetch_http_fallbacks
from vocabulary.providers import load_provider_registry


def _review_queue_terms(path: Path) -> list[str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EnrichmentFetchError(f"cannot read review queue {path}: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 2:
        raise EnrichmentFetchError("review queue must use schema_version 2")
    items = document.get("items")
    if not isinstance(items, list):
        raise EnrichmentFetchError("review queue must contain items")
    return [
        str(item["term"])
        for item in items
        if isinstance(item, dict)
        and item.get("fallback_required") is True
        and isinstance(item.get("term"), str)
    ]


class Command(BaseCommand):
    help = "Fetch a rate-bounded fallback queue into a resumable local JSONL cache."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--providers", required=True, type=Path)
        parser.add_argument(
            "--provider",
            choices=("freedictionaryapi-v1", "dictionaryapi-dev-v2"),
            required=True,
        )
        parser.add_argument("--cache", required=True, type=Path)
        parser.add_argument("--review-queue", type=Path)
        parser.add_argument("--term", action="append", default=[])
        parser.add_argument("--limit", required=True, type=int)
        parser.add_argument("--checkpoint-every", default=25, type=int)
        parser.add_argument("--rate-state", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        terms = list(options["term"])
        if options["review_queue"] is not None:
            try:
                terms.extend(_review_queue_terms(options["review_queue"]))
            except EnrichmentFetchError as exc:
                raise CommandError(str(exc)) from exc
        if not terms:
            raise CommandError("provide --term or --review-queue with fallback items")
        try:
            registry = load_provider_registry(options["providers"])
            config = registry[options["provider"]]
        except KeyError as exc:
            raise CommandError(f"unknown provider {options['provider']!r}") from exc
        except SnapshotError as exc:
            raise CommandError(str(exc)) from exc
        try:
            completed, remaining = fetch_http_fallbacks(
                config,
                terms,
                options["cache"],
                limit=options["limit"],
                checkpoint_every=options["checkpoint_every"],
                rate_state_path=options["rate_state"],
            )
        except EnrichmentFetchError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"cached {completed} response(s); {remaining} selected response(s) "
                "remain"
            )
        )
