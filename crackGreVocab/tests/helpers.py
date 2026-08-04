"""Shared helpers for isolated Django settings startup tests."""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

BASE_SETTINGS_ENVIRONMENT = {
    "ALLOWED_HOSTS": "api.example.com",
    "DATABASE_URL": "postgresql://user:password@localhost:5432/app",
    "DEBUG": "false",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": "false",
    "SECRET_KEY": "test-only-secret",
    "TRUST_X_FORWARDED_PROTO": "false",
}

_PASSTHROUGH_ENVIRONMENT_NAMES = (
    "LANG",
    "LC_ALL",
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
)


def run_settings_script(
    script: str,
    *,
    overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a settings import in an isolated interpreter and environment."""
    environment = {
        name: os.environ[name]
        for name in _PASSTHROUGH_ENVIRONMENT_NAMES
        if name in os.environ
    }
    environment.update(BASE_SETTINGS_ENVIRONMENT)
    environment["PYTHON_DOTENV_DISABLED"] = "1"
    if overrides:
        environment.update(overrides)

    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        cwd=BACKEND_ROOT,
        env=environment,
        text=True,
        timeout=10,
    )
