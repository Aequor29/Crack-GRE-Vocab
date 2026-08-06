"""Build immutable corpus artifacts strictly from reviewed local inputs."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from vocabulary.builder import BuildInputs, build_artifacts
from vocabulary.exceptions import CorpusBuildError
from vocabulary.normalization import canonical_version


class Command(BaseCommand):
    help = "Build a deterministic corpus without any network access."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--source", required=True, type=Path)
        parser.add_argument("--duplicate-decisions", required=True, type=Path)
        parser.add_argument("--providers", required=True, type=Path)
        parser.add_argument("--oewn-archive", required=True, type=Path)
        parser.add_argument("--sense-decisions", required=True, type=Path)
        parser.add_argument("--editorial-overrides", required=True, type=Path)
        parser.add_argument("--fallback-cache", required=True, type=Path)
        parser.add_argument("--corpus-version", required=True)
        parser.add_argument("--output-directory", required=True, type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            version = canonical_version(options["corpus_version"])
        except (TypeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
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
            changed = build_artifacts(
                inputs,
                version=version,
                output_directory=options["output_directory"],
            )
        except CorpusBuildError as exc:
            raise CommandError(str(exc)) from exc
        state = "built" if changed else "already identical"
        self.stdout.write(self.style.SUCCESS(f"corpus {state}"))
