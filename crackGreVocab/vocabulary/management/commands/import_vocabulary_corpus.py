"""Import one validated canonical corpus into the clean database."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from vocabulary.exceptions import CorpusImportError
from vocabulary.importer import import_corpus
from vocabulary.normalization import canonical_json_bytes


class Command(BaseCommand):
    help = "Atomically import or re-activate one immutable corpus manifest."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("manifest", type=Path)
        parser.add_argument("--no-activate", action="store_true")
        parser.add_argument("--report", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            report = import_corpus(
                options["manifest"],
                activate=not options["no_activate"],
            )
        except CorpusImportError as exc:
            raise CommandError(str(exc)) from exc
        document = report.as_dict()
        if options["report"] is not None:
            options["report"].parent.mkdir(parents=True, exist_ok=True)
            options["report"].write_bytes(canonical_json_bytes(document))
        self.stdout.write(json.dumps(document, sort_keys=True))
