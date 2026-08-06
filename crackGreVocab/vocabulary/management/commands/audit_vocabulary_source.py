"""Validate the retained source list and emit its deterministic audit."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from vocabulary.exceptions import SourceAuditError
from vocabulary.normalization import canonical_json_bytes
from vocabulary.source import audit_source


class Command(BaseCommand):
    help = "Audit GRE_word.csv against reviewed duplicate-collapse decisions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--source", required=True, type=Path)
        parser.add_argument("--duplicate-decisions", required=True, type=Path)
        parser.add_argument("--output", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            audit = audit_source(options["source"], options["duplicate_decisions"])
        except SourceAuditError as exc:
            raise CommandError(str(exc)) from exc
        document = audit.as_dict(source_path=str(options["source"]))
        if options["output"] is not None:
            options["output"].parent.mkdir(parents=True, exist_ok=True)
            options["output"].write_bytes(canonical_json_bytes(document))
        else:
            self.stdout.write(json.dumps(document, ensure_ascii=False, indent=2))
