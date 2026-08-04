"""Strict environment parsing for Django settings."""

import os
from collections.abc import Iterable
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def required_env(name: str) -> str:
    """Return a non-empty environment variable or fail startup."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required environment variable {name} is missing.")
    return value


def postgres_database_url(name: str = "DATABASE_URL") -> str:
    """Return a PostgreSQL URL that identifies a database."""
    value = required_env(name)
    try:
        parsed = urlparse(value)
        parsed.port
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"{name} must be a valid PostgreSQL URL."
        ) from exc

    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(f"{name} must use PostgreSQL.")
    if not value.casefold().startswith(f"{parsed.scheme}://"):
        raise ImproperlyConfigured(
            f"{name} must be a valid PostgreSQL URL."
        )
    if not parsed.path.strip("/"):
        raise ImproperlyConfigured(f"{name} must include a database name.")
    return value


def env_bool(name: str, *, default: bool) -> bool:
    """Parse an explicit boolean without treating arbitrary strings as true."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    value = raw_value.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"{name} must be one of: "
        f"{', '.join(sorted(_TRUE_VALUES | _FALSE_VALUES))}."
    )


def env_list(name: str, *, default: Iterable[str] = ()) -> list[str]:
    """Parse comma- or whitespace-delimited configuration into clean values."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return list(default)
    return [
        value
        for chunk in raw_value.split(",")
        for value in chunk.split()
        if value
    ]
