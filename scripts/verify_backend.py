"""Run repository backend checks and verify the published API schema."""

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "crackGreVocab"


def main() -> None:
    """Check backend source, dependencies, database behavior, and API drift."""
    arguments: tuple[str, ...]
    for arguments in (
        ("-m", "ruff", "check", "crackGreVocab", "scripts", "e2e"),
        ("-m", "mypy", "crackGreVocab", "scripts", "e2e"),
        (
            "-m",
            "compileall",
            "-q",
            "-x",
            r"(^|/)([.]|node_modules|artifacts|test-results|playwright-report)",
            "crackGreVocab",
            "scripts",
            "e2e",
        ),
        ("-m", "pip", "check"),
    ):
        subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)
    for arguments in (
        ("check", "--database", "default"),
        ("makemigrations", "--check", "--dry-run"),
        ("test", "--noinput", "--verbosity", "2"),
    ):
        subprocess.run(
            [sys.executable, "manage.py", *arguments], cwd=BACKEND, check=True
        )
    with TemporaryDirectory() as directory:
        schema = Path(directory) / "openapi.json"
        subprocess.run(
            [
                sys.executable,
                "manage.py",
                "spectacular",
                "--file",
                str(schema),
                "--format",
                "openapi-json",
                "--validate",
                "--fail-on-warn",
            ],
            cwd=BACKEND,
            check=True,
        )
        if schema.read_bytes() != (BACKEND / "openapi.json").read_bytes():
            raise SystemExit("API schema drift: regenerate crackGreVocab/openapi.json.")


if __name__ == "__main__":
    main()
