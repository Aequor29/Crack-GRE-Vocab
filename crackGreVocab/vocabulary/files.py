"""Filesystem primitives for immutable inputs and durable artifact replacement."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .normalization import sha256_bytes


@dataclass(frozen=True)
class FileSnapshot:
    """One file's path, exact consumed bytes, and their precomputed digest."""

    path: Path
    content: bytes
    sha256: str

    @classmethod
    def read(cls, path: Path) -> FileSnapshot:
        """Read a file once and bind its digest to those exact bytes."""
        content = path.read_bytes()
        return cls(path=path, content=content, sha256=sha256_bytes(content))


def atomic_replace_bytes(path: Path, content: bytes) -> None:
    """Durably replace a file with bytes written in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(content)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
