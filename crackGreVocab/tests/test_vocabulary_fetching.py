"""Bounded, resumable network acquisition tests without live HTTP."""

import fcntl
import io
import json
import tempfile
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote

from django.test import SimpleTestCase
from vocabulary.exceptions import EnrichmentFetchError
from vocabulary.fetching import (
    _request_json,
    fetch_http_fallbacks,
)
from vocabulary.normalization import canonical_json_bytes, sha256_bytes
from vocabulary.providers import ProviderConfig, load_http_cache


class _Response:
    status = 200

    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return self.payload


class _Clock:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _config() -> ProviderConfig:
    return ProviderConfig(
        id="freedictionaryapi-v1",
        kind="http-json",
        priority=2,
        parser_version=1,
        base_url="https://example.test/",
        rate_limit_per_hour=1000,
        minimum_interval_seconds=3.6,
    )


def _dictionary_config() -> ProviderConfig:
    return ProviderConfig(
        id="dictionaryapi-dev-v2",
        kind="http-json",
        priority=3,
        parser_version=1,
        base_url="https://example.test/",
        rate_limit_per_hour=1000,
        minimum_interval_seconds=3.6,
    )


def _free_dictionary_payload(request) -> dict[str, object]:
    return {
        "entries": [],
        "word": unquote(request.full_url.rsplit("/", 1)[-1]),
    }


class FallbackFetchingTests(SimpleTestCase):
    def test_a_second_writer_fails_without_touching_the_cache(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache = Path(temporary_directory) / "fallback.jsonl"
            lock_path = cache.with_name(f"{cache.name}.lock")
            with lock_path.open("a+", encoding="utf-8") as owner:
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(
                    EnrichmentFetchError,
                    "another fallback fetch owns cache",
                ):
                    fetch_http_fallbacks(
                        _config(),
                        ["Lucid"],
                        cache,
                        limit=1,
                    )

            self.assertFalse(cache.exists())

    def test_bounded_batch_reports_the_full_remaining_queue_and_resumes(self):
        terms = [
            f"Term {chr(97 + index // 26)}{chr(97 + index % 26)}"
            for index in range(600)
        ]
        clock = _Clock()

        def open_url(request, **_kwargs):
            return _Response(json.dumps(_free_dictionary_payload(request)).encode())

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache = root / "fallback.jsonl"
            first = fetch_http_fallbacks(
                _config(),
                terms,
                cache,
                limit=100,
                checkpoint_every=100,
                open_url=open_url,
                sleeper=clock.sleep,
                clock=clock,
                rate_state_path=root / "rate-limit",
            )
            second = fetch_http_fallbacks(
                _config(),
                terms,
                cache,
                limit=100,
                checkpoint_every=100,
                open_url=open_url,
                sleeper=clock.sleep,
                clock=clock,
                rate_state_path=root / "rate-limit",
            )
            cached = load_http_cache(cache)

        self.assertEqual(first, (100, 500))
        self.assertEqual(second, (100, 400))
        self.assertEqual(len(cached), 200)

    def test_repeated_fetches_resume_and_share_persistent_pacing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache = root / "fallback.jsonl"
            pacing_state = root / "rate-limit"
            clock = _Clock()
            requested_urls: list[str] = []

            def open_url(request, **_kwargs):
                requested_urls.append(request.full_url)
                return _Response(
                    json.dumps(_free_dictionary_payload(request)).encode()
                )

            first = fetch_http_fallbacks(
                _config(),
                ["Alpha"],
                cache,
                limit=1,
                checkpoint_every=1,
                open_url=open_url,
                sleeper=clock.sleep,
                clock=clock,
                rate_state_path=pacing_state,
            )
            second = fetch_http_fallbacks(
                _config(),
                ["Alpha", "Beta"],
                cache,
                limit=1,
                checkpoint_every=1,
                open_url=open_url,
                sleeper=clock.sleep,
                clock=clock,
                rate_state_path=pacing_state,
            )
            no_op = fetch_http_fallbacks(
                _config(),
                ["Alpha", "Beta"],
                cache,
                limit=2,
                open_url=open_url,
                sleeper=clock.sleep,
                clock=clock,
                rate_state_path=pacing_state,
            )

            records = load_http_cache(cache)

        self.assertEqual(first, (1, 0))
        self.assertEqual(second, (1, 0))
        self.assertEqual(no_op, (0, 0))
        self.assertEqual(len(clock.sleeps), 1)
        self.assertAlmostEqual(clock.sleeps[0], 3.6)
        self.assertEqual(len(requested_urls), 2)
        self.assertEqual(
            set(records),
            {("freedictionaryapi-v1", "alpha"), ("freedictionaryapi-v1", "beta")},
        )

    def test_malformed_response_does_not_replace_the_existing_cache(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache = root / "fallback.jsonl"
            payload: dict[str, object] = {"entries": [], "word": "Alpha"}
            existing = {
                "http_status": 200,
                "normalized_term": "alpha",
                "payload": payload,
                "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
                "provider": "freedictionaryapi-v1",
                "request_url": "https://example.test/Alpha",
                "status": "ok",
            }
            cache.write_bytes(canonical_json_bytes(existing))
            original = cache.read_bytes()

            with self.assertRaisesRegex(
                EnrichmentFetchError,
                "freedictionaryapi-v1.*beta.*malformed",
            ):
                fetch_http_fallbacks(
                    _config(),
                    ["Beta"],
                    cache,
                    limit=1,
                    open_url=lambda *_args, **_kwargs: _Response(b"not-json"),
                    sleeper=lambda _seconds: None,
                    clock=lambda: 100.0,
                    rate_state_path=root / "rate-limit",
                )

            self.assertEqual(cache.read_bytes(), original)

    def test_semantically_invalid_response_is_not_cached(self):
        payload = {
            "entries": [
                {
                    "partOfSpeech": "adjective",
                    "senses": [
                        {
                            "definition": "clear",
                            "examples": ["a lucid\u0000 explanation"],
                            "subsenses": [],
                        }
                    ],
                }
            ],
            "word": "lucid",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache = root / "fallback.jsonl"

            with self.assertRaisesRegex(
                EnrichmentFetchError,
                "freedictionaryapi-v1.*lucid.*control characters",
            ):
                fetch_http_fallbacks(
                    _config(),
                    ["Lucid"],
                    cache,
                    limit=1,
                    open_url=lambda *_args, **_kwargs: _Response(
                        canonical_json_bytes(payload)
                    ),
                    sleeper=lambda _seconds: None,
                    clock=lambda: 100.0,
                    rate_state_path=root / "rate-limit",
                )

            self.assertFalse(cache.exists())

    def test_mismatched_response_headword_does_not_change_the_cache(self):
        response_payload: dict[str, object] = {
            "entries": [],
            "word": "opaque",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache = root / "fallback.jsonl"
            existing_payload: dict[str, object] = {
                "entries": [],
                "word": "Alpha",
            }
            existing = {
                "http_status": 200,
                "normalized_term": "alpha",
                "payload": existing_payload,
                "payload_sha256": sha256_bytes(
                    canonical_json_bytes(existing_payload)
                ),
                "provider": "freedictionaryapi-v1",
                "request_url": "https://example.test/Alpha",
                "status": "ok",
            }
            cache.write_bytes(canonical_json_bytes(existing))
            original = cache.read_bytes()

            with self.assertRaisesRegex(
                EnrichmentFetchError,
                "freedictionaryapi-v1.*beta.*headword does not match",
            ):
                fetch_http_fallbacks(
                    _config(),
                    ["Beta"],
                    cache,
                    limit=1,
                    open_url=lambda *_args, **_kwargs: _Response(
                        canonical_json_bytes(response_payload)
                    ),
                    sleeper=lambda _seconds: None,
                    clock=lambda: 100.0,
                    rate_state_path=root / "rate-limit",
                )

            self.assertEqual(cache.read_bytes(), original)

    def test_non_string_dictionary_example_does_not_change_the_cache(self):
        response_payload: list[dict[str, object]] = [
            {
                "meanings": [
                    {
                        "definitions": [
                            {
                                "definition": "clear and easy to understand",
                                "example": {"text": "a lucid explanation"},
                                "synonyms": [],
                            }
                        ],
                        "partOfSpeech": "adjective",
                    }
                ],
                "word": "Lucid",
            }
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cache = root / "fallback.jsonl"
            existing_payload: dict[str, object] = {}
            existing = {
                "http_status": 404,
                "normalized_term": "alpha",
                "payload": existing_payload,
                "payload_sha256": sha256_bytes(
                    canonical_json_bytes(existing_payload)
                ),
                "provider": "dictionaryapi-dev-v2",
                "request_url": "https://example.test/Alpha",
                "status": "not-found",
            }
            cache.write_bytes(canonical_json_bytes(existing))
            original = cache.read_bytes()

            with self.assertRaisesRegex(
                EnrichmentFetchError,
                "dictionaryapi-dev-v2.*lucid.*example must be a string or null",
            ):
                fetch_http_fallbacks(
                    _dictionary_config(),
                    ["Lucid"],
                    cache,
                    limit=1,
                    open_url=lambda *_args, **_kwargs: _Response(
                        canonical_json_bytes(response_payload)
                    ),
                    sleeper=lambda _seconds: None,
                    clock=lambda: 100.0,
                    rate_state_path=root / "rate-limit",
                )

            self.assertEqual(cache.read_bytes(), original)

    def test_retry_after_is_honored_before_retrying(self):
        headers = Message()
        headers["Retry-After"] = "7"
        responses = [
            HTTPError(
                "https://example.test/lucid",
                429,
                "rate limited",
                headers,
                io.BytesIO(b"{}"),
            ),
            _Response(b'{"entries": []}'),
        ]
        sleeps: list[float] = []

        def open_url(*_args, **_kwargs):
            response = responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response

        status, payload = _request_json(
            "https://example.test/lucid",
            open_url=open_url,
            sleeper=sleeps.append,
            clock=lambda: 0.0,
            retries=1,
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"entries": []})
        self.assertEqual(sleeps, [7.0])

    def test_retry_after_is_honored_for_a_service_unavailable_response(self):
        headers = Message()
        headers["Retry-After"] = "6"
        responses = [
            HTTPError(
                "https://example.test/lucid",
                503,
                "temporarily unavailable",
                headers,
                io.BytesIO(b"{}"),
            ),
            _Response(b'{"entries": []}'),
        ]
        sleeps: list[float] = []

        def open_url(*_args, **_kwargs):
            response = responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response

        status, payload = _request_json(
            "https://example.test/lucid",
            open_url=open_url,
            sleeper=sleeps.append,
            clock=lambda: 0.0,
            retries=1,
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"entries": []})
        self.assertEqual(sleeps, [6.0])

    def test_server_error_retry_still_observes_the_provider_interval(self):
        responses = [
            HTTPError(
                "https://example.test/lucid",
                500,
                "server error",
                Message(),
                io.BytesIO(b"{}"),
            ),
            _Response(b'{"entries": [], "word": "Lucid"}'),
        ]
        clock = _Clock()

        def open_url(*_args, **_kwargs):
            response = responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response

        with tempfile.TemporaryDirectory() as temporary_directory:
            fetch_http_fallbacks(
                _config(),
                ["Lucid"],
                Path(temporary_directory) / "fallback.jsonl",
                limit=1,
                open_url=open_url,
                sleeper=clock.sleep,
                clock=clock,
                rate_state_path=Path(temporary_directory) / "rate-limit",
                retries=1,
            )

        self.assertEqual(len(clock.sleeps), 2)
        self.assertAlmostEqual(clock.sleeps[0], 1.0)
        self.assertAlmostEqual(clock.sleeps[1], 2.6)
