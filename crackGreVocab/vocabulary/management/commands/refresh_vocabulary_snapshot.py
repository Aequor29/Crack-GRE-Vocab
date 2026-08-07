"""Download one checksum-pinned bulk vocabulary provider snapshot."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from vocabulary.exceptions import EnrichmentFetchError, SnapshotError
from vocabulary.fetching import download_pinned_archive
from vocabulary.providers import load_provider_registry


class Command(BaseCommand):
    help = "Download a pinned bulk provider archive outside the offline build."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--providers", required=True, type=Path)
        parser.add_argument("--provider", default="oewn-2025")
        parser.add_argument("--destination", required=True, type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            registry = load_provider_registry(options["providers"])
            config = registry[options["provider"]]
            changed = download_pinned_archive(config, options["destination"])
        except KeyError as exc:
            raise CommandError(f"unknown provider {options['provider']!r}") from exc
        except (EnrichmentFetchError, SnapshotError) as exc:
            raise CommandError(str(exc)) from exc
        state = "downloaded" if changed else "already verified"
        self.stdout.write(self.style.SUCCESS(f"{config.id}: {state}"))
