"""Network-only refresh helpers kept outside the strict offline build."""

import fcntl
import json
import os
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .exceptions import EnrichmentFetchError, SnapshotError
from .files import atomic_replace_bytes
from .normalization import (
    canonical_json_bytes,
    canonical_term,
    sha256_bytes,
    sha256_file,
)
from .providers import (
    ProviderConfig,
    load_http_cache,
    parse_http_candidates,
)

OpenUrl = Callable[..., Any]


def download_pinned_archive(
    config: ProviderConfig,
    destination: Path,
    *,
    open_url: OpenUrl | None = None,
) -> bool:
    """Download one pinned bulk archive atomically; return whether it changed."""
    if config.kind != "bulk-zip":
        raise EnrichmentFetchError(f"provider {config.id!r} is not a bulk archive")
    if destination.exists() and sha256_file(destination) == config.archive_sha256:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".download",
    )
    try:
        request = Request(
            config.archive_url,
            headers={"User-Agent": "Crack-GRE-Vocab-corpus-builder/1"},
        )
        try:
            response = (open_url or urlopen)(request, timeout=120)
            with response, os.fdopen(descriptor, "wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise EnrichmentFetchError(
                f"failed to download pinned provider {config.id}: {exc}"
            ) from exc

        actual_digest = sha256_file(Path(temporary_name))
        if actual_digest != config.archive_sha256:
            raise EnrichmentFetchError(
                f"downloaded {config.id} checksum mismatch: expected "
                f"{config.archive_sha256}, got {actual_digest}"
            )
        os.replace(temporary_name, destination)
        return True
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _request_json(
    url: str,
    *,
    open_url: OpenUrl,
    sleeper: Callable[[float], None],
    clock: Callable[[], float],
    retries: int,
    before_attempt: Callable[[], None] | None = None,
) -> tuple[int, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Crack-GRE-Vocab-corpus-builder/1",
        },
    )
    for attempt in range(retries + 1):
        if before_attempt is not None:
            before_attempt()
        retry_wait = 0.0
        try:
            response = open_url(request, timeout=30)
            with response:
                status = int(getattr(response, "status", None) or 200)
                content = response.read()
        except HTTPError as exc:
            if exc.code == 404:
                content = exc.read()
                try:
                    return 404, json.loads(content) if content else {}
                except UnicodeError, json.JSONDecodeError:
                    return 404, {}
            if exc.code != 429 and exc.code < 500:
                raise EnrichmentFetchError(
                    f"provider returned HTTP {exc.code}"
                ) from exc
            error: BaseException = exc
            retry_wait = _retry_after_seconds(exc, clock=clock)
        except (URLError, OSError, TimeoutError) as exc:
            error = exc
        else:
            try:
                return status, json.loads(content)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise EnrichmentFetchError(
                    "provider returned malformed UTF-8 JSON"
                ) from exc

        if attempt == retries:
            raise EnrichmentFetchError(
                f"provider unavailable after {retries + 1} attempts: {error}"
            ) from error
        sleeper(max(float(2**attempt), retry_wait))
    raise AssertionError("unreachable")


def _retry_after_seconds(
    error: HTTPError,
    *,
    clock: Callable[[], float],
) -> float:
    if error.code != 429 and not 500 <= error.code < 600:
        return 0.0
    value = error.headers.get("Retry-After") if error.headers is not None else None
    if value is None:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except TypeError, ValueError, OverflowError:
            return 0.0
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, retry_at.timestamp() - clock())


def _pace_request(
    state_path: Path,
    *,
    minimum_interval_seconds: float,
    sleeper: Callable[[float], None],
    clock: Callable[[], float],
) -> None:
    """Persist request starts so repeated and concurrent commands share pacing."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a+", encoding="utf-8") as state:
        fcntl.flock(state.fileno(), fcntl.LOCK_EX)
        state.seek(0)
        raw_last_request = state.read().strip()
        try:
            last_request = float(raw_last_request) if raw_last_request else 0.0
        except ValueError as exc:
            raise EnrichmentFetchError(
                f"invalid fallback rate-limit state at {state_path}"
            ) from exc
        now = clock()
        wait_seconds = max(
            0.0,
            last_request + minimum_interval_seconds - now,
        )
        if wait_seconds:
            sleeper(wait_seconds)
            now = clock()
        state.seek(0)
        state.truncate()
        state.write(f"{now:.6f}\n")
        state.flush()
        os.fsync(state.fileno())
        fcntl.flock(state.fileno(), fcntl.LOCK_UN)


def _write_http_cache(
    path: Path,
    records: dict[tuple[str, str], dict[str, Any]],
) -> None:
    content = b"".join(canonical_json_bytes(records[key]) for key in sorted(records))
    atomic_replace_bytes(path, content)


def _checkpoint_http_cache(
    path: Path,
    records: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Replace the single writer's cache with its complete checkpoint."""
    try:
        _write_http_cache(path, records)
    except OSError as exc:
        raise EnrichmentFetchError(
            f"cannot checkpoint fallback cache {path}: {exc}"
        ) from exc


@contextmanager
def _exclusive_cache_writer(cache_path: Path) -> Iterator[None]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    try:
        with lock_path.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise EnrichmentFetchError(
                    f"another fallback fetch owns cache {cache_path}"
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except EnrichmentFetchError:
        raise
    except OSError as exc:
        raise EnrichmentFetchError(
            f"cannot lock fallback cache {cache_path}: {exc}"
        ) from exc


def _fetch_http_fallbacks_owned(
    config: ProviderConfig,
    terms: Iterable[str],
    cache_path: Path,
    *,
    limit: int,
    checkpoint_every: int = 25,
    open_url: OpenUrl = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    rate_state_path: Path | None = None,
    retries: int = 2,
) -> tuple[int, int]:
    if config.kind != "http-json":
        raise EnrichmentFetchError(f"provider {config.id!r} is not an HTTP provider")
    if limit < 1:
        raise EnrichmentFetchError("fetch limit must be at least one")
    if config.rate_limit_per_hour is not None and limit > config.rate_limit_per_hour:
        raise EnrichmentFetchError(
            f"fetch limit exceeds {config.id} hourly limit of "
            f"{config.rate_limit_per_hour}"
        )
    if checkpoint_every < 1:
        raise EnrichmentFetchError("checkpoint interval must be at least one")

    try:
        records = load_http_cache(cache_path)
    except SnapshotError as exc:
        raise EnrichmentFetchError(str(exc)) from exc

    normalized_terms: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_term in terms:
        try:
            term, normalized_term = canonical_term(raw_term)
        except ValueError as exc:
            raise EnrichmentFetchError(
                f"invalid fallback term {raw_term!r}: {exc}"
            ) from exc
        if normalized_term not in seen:
            seen.add(normalized_term)
            normalized_terms.append((term, normalized_term))

    all_missing = [
        item for item in normalized_terms if (config.id, item[1]) not in records
    ]
    missing = all_missing[:limit]
    pacing_state = rate_state_path or cache_path.with_name(
        f"{cache_path.name}.{config.id}.rate-limit"
    )
    completed = 0
    for term, normalized_term in missing:
        request_url = f"{config.base_url}{quote(term, safe='')}"
        try:
            status, payload = _request_json(
                request_url,
                open_url=open_url,
                sleeper=sleeper,
                clock=clock,
                retries=retries,
                before_attempt=lambda: _pace_request(
                    pacing_state,
                    minimum_interval_seconds=config.minimum_interval_seconds,
                    sleeper=sleeper,
                    clock=clock,
                ),
            )
        except EnrichmentFetchError as exc:
            raise EnrichmentFetchError(
                f"provider {config.id!r} request failed for term "
                f"{normalized_term!r}: {exc}"
            ) from exc
        if status not in {200, 404}:
            raise EnrichmentFetchError(
                f"provider returned unsupported successful HTTP status {status}"
            )
        if not isinstance(payload, (dict, list)):
            raise EnrichmentFetchError(
                f"provider payload for {term!r} must be an object or list"
            )
        record = {
            "http_status": status,
            "normalized_term": normalized_term,
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "provider": config.id,
            "request_url": request_url,
            "status": "ok" if status == 200 else "not-found",
        }
        if status == 200:
            try:
                parse_http_candidates(record, config)
            except SnapshotError as exc:
                raise EnrichmentFetchError(
                    f"provider {config.id!r} returned an invalid response for "
                    f"term {normalized_term!r}: {exc}"
                ) from exc
        records[(config.id, normalized_term)] = record
        completed += 1
        if completed % checkpoint_every == 0:
            _checkpoint_http_cache(cache_path, records)

    if completed and completed % checkpoint_every:
        _checkpoint_http_cache(cache_path, records)
    return completed, len(all_missing) - completed


def fetch_http_fallbacks(
    config: ProviderConfig,
    terms: Iterable[str],
    cache_path: Path,
    *,
    limit: int,
    checkpoint_every: int = 25,
    open_url: OpenUrl | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    rate_state_path: Path | None = None,
    retries: int = 2,
) -> tuple[int, int]:
    """Fetch a bounded resumable batch while one command owns the cache."""
    with _exclusive_cache_writer(cache_path):
        return _fetch_http_fallbacks_owned(
            config,
            terms,
            cache_path,
            limit=limit,
            checkpoint_every=checkpoint_every,
            open_url=open_url or urlopen,
            sleeper=sleeper,
            clock=clock,
            rate_state_path=rate_state_path,
            retries=retries,
        )
