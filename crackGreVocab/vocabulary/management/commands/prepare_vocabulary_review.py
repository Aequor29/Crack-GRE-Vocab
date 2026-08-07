"""Generate the offline sense-review and fallback queue."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from vocabulary.builder import (
    BuildInputs,
    load_build_context,
    review_queue_document,
    write_review_queue,
)
from vocabulary.exceptions import CorpusBuildError


class Command(BaseCommand):
    help = "Generate unresolved same-sense candidates from pinned local inputs."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--source", required=True, type=Path)
        parser.add_argument("--duplicate-decisions", required=True, type=Path)
        parser.add_argument("--providers", required=True, type=Path)
        parser.add_argument("--oewn-archive", required=True, type=Path)
        parser.add_argument("--sense-decisions", required=True, type=Path)
        parser.add_argument("--editorial-overrides", required=True, type=Path)
        parser.add_argument("--fallback-cache", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        inputs = BuildInputs(
            source_path=options["source"],
            duplicate_decisions_path=options["duplicate_decisions"],
            provider_registry_path=options["providers"],
            oewn_archive_path=options["oewn_archive"],
            sense_decisions_path=options["sense_decisions"],
            editorial_overrides_path=options["editorial_overrides"],
            fallback_cache_path=options["fallback_cache"],
        )
        try:
            audit, _registry, candidates, selections, overrides = load_build_context(
                inputs
            )
            document = review_queue_document(
                audit,
                candidates,
                selections,
                overrides,
            )
            write_review_queue(options["output"], document)
        except CorpusBuildError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "review queue contains "
                f"{document['summary']['unresolved']} unresolved word(s)"
            )
        )
