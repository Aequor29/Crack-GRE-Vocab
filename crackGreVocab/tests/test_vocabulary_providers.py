"""Sense-preserving provider parser tests."""

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from django.test import SimpleTestCase
from vocabulary.exceptions import SnapshotError
from vocabulary.normalization import canonical_json_bytes, sha256_bytes, sha256_file
from vocabulary.providers import (
    ProviderConfig,
    load_cached_candidates,
    load_http_cache,
    load_oewn_candidates,
    load_provider_registry,
    parse_dictionary_api_dev,
    parse_free_dictionary_api,
)


class ProviderParserTests(SimpleTestCase):
    def test_http_cache_requires_exact_canonical_status_metadata(self):
        payload: dict[str, object] = {"entries": []}
        valid = {
            "http_status": 200,
            "normalized_term": "lucid",
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "provider": "freedictionaryapi-v1",
            "request_url": "https://example.test/lucid",
            "status": "ok",
        }
        invalid_records = (
            {**valid, "unexpected": True},
            {**valid, "normalized_term": "Lucid"},
            {**valid, "http_status": 404},
            {**valid, "request_url": "not-a-url"},
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "fallback.jsonl"
            for record in invalid_records:
                with self.subTest(record=record):
                    cache_path.write_bytes(canonical_json_bytes(record))
                    with self.assertRaises(SnapshotError):
                        load_http_cache(cache_path)

    def test_not_found_cache_still_requires_a_registered_provider(self):
        payload: dict[str, object] = {}
        record = {
            "http_status": 404,
            "normalized_term": "lucid",
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "provider": "unregistered-provider",
            "request_url": "https://example.test/lucid",
            "status": "not-found",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "fallback.jsonl"
            cache_path.write_bytes(canonical_json_bytes(record))

            with self.assertRaisesRegex(SnapshotError, "unknown provider"):
                load_cached_candidates(cache_path, {})

    def test_cache_request_url_is_bound_to_provider_and_normalized_term(self):
        payload: dict[str, object] = {}
        base_record = {
            "http_status": 404,
            "normalized_term": "lucid",
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "provider": "freedictionaryapi-v1",
            "status": "not-found",
        }
        config = ProviderConfig(
            id="freedictionaryapi-v1",
            kind="http-json",
            priority=2,
            parser_version=1,
            base_url="https://example.test/definition/",
        )
        invalid_urls = (
            "https://example.test/definition/opaque",
            "https://example.test/definition/lucid?alternate=true",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "fallback.jsonl"
            for request_url in invalid_urls:
                with self.subTest(request_url=request_url):
                    cache_path.write_bytes(
                        canonical_json_bytes(
                            {**base_record, "request_url": request_url}
                        )
                    )
                    with self.assertRaisesRegex(
                        SnapshotError,
                        "does not match|term does not match",
                    ):
                        load_cached_candidates(
                            cache_path,
                            {config.id: config},
                        )

    def test_cached_parser_errors_identify_the_provider_and_term(self):
        payload = {
            "entries": [
                {
                    "language": {"code": "en", "name": "English"},
                    "partOfSpeech": "adjective",
                    "senses": [
                        {
                            "definition": "clear",
                            "examples": ["a lucid\u0000 explanation"],
                            "subsenses": [],
                        }
                    ],
                    "word": "lucid",
                }
            ],
            "word": "lucid",
        }
        record = {
            "http_status": 200,
            "normalized_term": "lucid",
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "provider": "freedictionaryapi-v1",
            "request_url": "https://example.test/definition/lucid",
            "status": "ok",
        }
        config = ProviderConfig(
            id="freedictionaryapi-v1",
            kind="http-json",
            priority=2,
            parser_version=1,
            base_url="https://example.test/definition/",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "fallback.jsonl"
            cache_path.write_bytes(canonical_json_bytes(record))

            with self.assertRaisesRegex(
                SnapshotError,
                "freedictionaryapi-v1.*lucid.*control characters",
            ):
                load_cached_candidates(cache_path, {config.id: config})

    def test_registry_rejects_unknown_parsers_and_nonpositive_limits(self):
        invalid_providers = (
            {
                "archive_sha256": "0" * 64,
                "archive_url": "https://example.test/oewn.zip",
                "id": "oewn-2025",
                "kind": "bulk-zip",
                "parser_version": 99,
                "priority": 1,
            },
            {
                "base_url": "https://example.test/",
                "id": "freedictionaryapi-v1",
                "kind": "http-json",
                "minimum_interval_seconds": 3.6,
                "parser_version": 1,
                "priority": 0,
                "rate_limit_per_hour": 1000,
            },
            {
                "base_url": "https://example.test/",
                "id": "freedictionaryapi-v1",
                "kind": "http-json",
                "minimum_interval_seconds": 3.6,
                "parser_version": 1,
                "priority": 1,
                "rate_limit_per_hour": 0,
            },
            {
                "archive_sha256": "0" * 64,
                "archive_url": "https://example.test/oewn.zip",
                "id": "oewn-2025",
                "kind": "bulk-zip",
                "parser_version": 1,
                "priority": 2,
            },
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            registry_path = Path(temporary_directory) / "providers.json"
            for provider in invalid_providers:
                with self.subTest(provider=provider):
                    registry_path.write_text(
                        json.dumps({"providers": [provider], "schema_version": 1}),
                        encoding="utf-8",
                    )
                    with self.assertRaises(SnapshotError):
                        load_provider_registry(registry_path)

    def test_oewn_keeps_plain_and_attributed_examples_on_the_same_sense(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "oewn.zip"
            entries = {
                "lucid": {
                    "a": {
                        "pronunciation": [{"value": "ˈluːsɪd"}],
                        "sense": [{"id": "lucid%5:00", "synset": "0001-a"}],
                    }
                }
            }
            synsets = {
                "0001-a": {
                    "definition": ["transparently clear"],
                    "example": [
                        "a lucid explanation",
                        {
                            "source": "Public-domain fixture",
                            "text": "Her account remained lucid.",
                        },
                    ],
                    "members": ["lucid", "clear"],
                    "partOfSpeech": "s",
                }
            }
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("entries-l.json", json.dumps(entries))
                archive.writestr("adj.test.json", json.dumps(synsets))
            config = ProviderConfig(
                id="oewn-2025",
                kind="bulk-zip",
                priority=1,
                parser_version=1,
                version="2025",
                archive_url="https://example.test/oewn.zip",
                archive_sha256=sha256_file(archive_path),
            )

            candidate = load_oewn_candidates(
                archive_path,
                config,
                {"lucid"},
            )["lucid"][0]

        self.assertEqual(candidate.provider_sense_id, "lucid%5:00")
        self.assertEqual(
            [example.text for example in candidate.examples],
            ["a lucid explanation", "Her account remained lucid."],
        )
        self.assertEqual(
            candidate.examples[1].provenance["source"],
            "Public-domain fixture",
        )

    def test_oewn_rejects_a_snapshot_with_the_wrong_checksum(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "oewn.zip"
            archive_path.write_bytes(b"not the pinned archive")
            config = ProviderConfig(
                id="oewn-2025",
                kind="bulk-zip",
                priority=1,
                parser_version=1,
                archive_sha256="0" * 64,
            )

            with self.assertRaisesRegex(SnapshotError, "checksum mismatch"):
                load_oewn_candidates(archive_path, config, {"lucid"})

    def test_oewn_missing_snapshot_is_reported_as_a_domain_error(self):
        config = ProviderConfig(
            id="oewn-2025",
            kind="bulk-zip",
            priority=1,
            parser_version=1,
            archive_sha256="0" * 64,
        )

        with self.assertRaisesRegex(SnapshotError, "cannot read OEWN archive"):
            load_oewn_candidates(Path("missing-oewn.zip"), config, {"lucid"})

    def test_free_dictionary_prefers_examples_then_same_sense_quotes(self):
        payload: dict[str, Any] = {
            "entries": [
                {
                    "partOfSpeech": "  verb  ",
                    "pronunciations": [{"text": "  /dʒɒt/  "}],
                    "senses": [
                        {
                            "definition": "write briefly",
                            "examples": ["Jot the address down."],
                            "quotes": [
                                {
                                    "reference": "Public-domain fixture",
                                    "text": "She jotted one final note.",
                                }
                            ],
                            "synonyms": ["note"],
                        }
                    ],
                }
            ],
            "source": {"url": "https://example.test/source"},
            "word": "Jot",
        }
        record = {
            "normalized_term": "jot",
            "payload": payload,
            "payload_sha256": "a" * 64,
            "request_url": "https://example.test/jot",
        }
        config = ProviderConfig(
            id="freedictionaryapi-v1",
            kind="http-json",
            priority=2,
            parser_version=1,
        )

        candidate = parse_free_dictionary_api(record, config)[0]

        self.assertEqual(candidate.part_of_speech, "verb")
        self.assertEqual(candidate.pronunciation, "/dʒɒt/")
        self.assertEqual(
            [example.text for example in candidate.examples],
            ["Jot the address down.", "She jotted one final note."],
        )
        self.assertEqual(candidate.examples[0].provenance["kind"], "example")
        self.assertEqual(candidate.examples[1].provenance["kind"], "sourced-quote")
        self.assertEqual(
            candidate.examples[1].provenance["reference"],
            "Public-domain fixture",
        )
        payload["entries"][0]["partOfSpeech"] = "x" * 33
        with self.assertRaisesRegex(SnapshotError, "part_of_speech"):
            parse_free_dictionary_api(record, config)
        payload["entries"][0]["partOfSpeech"] = "verb"
        payload["entries"][0]["senses"][0]["definition"] = "<b>unsafe</b>"
        with self.assertRaisesRegex(SnapshotError, "provider definition"):
            parse_free_dictionary_api(record, config)

    def test_free_dictionary_headword_is_bound_to_the_normalized_term(self):
        config = ProviderConfig(
            id="freedictionaryapi-v1",
            kind="http-json",
            priority=2,
            parser_version=1,
        )
        invalid_payloads: tuple[tuple[dict[str, Any], str], ...] = (
            ({"entries": []}, "headword must be a string"),
            (
                {"entries": [], "word": "opaque"},
                "headword does not match normalized term",
            ),
        )

        for payload, message in invalid_payloads:
            with self.subTest(payload=payload):
                record = {
                    "normalized_term": "lucid",
                    "payload": payload,
                    "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
                    "request_url": "https://example.test/Lucid",
                }

                with self.assertRaisesRegex(SnapshotError, message):
                    parse_free_dictionary_api(record, config)

    def test_dictionary_api_dev_never_borrows_an_example_between_definitions(self):
        payload: list[dict[str, Any]] = [
            {
                "meanings": [
                    {
                        "definitions": [
                            {
                                "definition": "clear and easy to understand",
                                "example": "She gave a lucid explanation.",
                                "synonyms": ["clear"],
                            },
                            {
                                "definition": "bright or luminous",
                                "synonyms": ["bright"],
                            },
                        ],
                        "partOfSpeech": "  adjective  ",
                    }
                ],
                "phonetic": "  /ˈluːsɪd/  ",
                "word": "lucid",
            }
        ]
        record = {
            "normalized_term": "lucid",
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "request_url": "https://example.test/lucid",
        }
        config = ProviderConfig(
            id="dictionaryapi-dev-v2",
            kind="http-json",
            priority=3,
            parser_version=1,
        )

        candidates = parse_dictionary_api_dev(record, config)

        self.assertEqual(candidates[0].part_of_speech, "adjective")
        self.assertEqual(candidates[0].pronunciation, "/ˈluːsɪd/")
        self.assertEqual(
            [example.text for example in candidates[0].examples],
            ["She gave a lucid explanation."],
        )
        self.assertEqual(candidates[1].examples, ())

    def test_dictionary_api_dev_binds_every_entry_headword(self):
        config = ProviderConfig(
            id="dictionaryapi-dev-v2",
            kind="http-json",
            priority=3,
            parser_version=1,
        )
        invalid_payloads: tuple[tuple[list[dict[str, Any]], str], ...] = (
            ([], "must contain a headword entry"),
            (
                [{"meanings": [], "word": "Lucid"}, {"meanings": []}],
                "entry 1 headword must be a string",
            ),
            (
                [
                    {"meanings": [], "word": "Lucid"},
                    {"meanings": [], "word": "opaque"},
                ],
                "entry 1 headword does not match normalized term",
            ),
        )

        for payload, message in invalid_payloads:
            with self.subTest(payload=payload):
                record = {
                    "normalized_term": "lucid",
                    "payload": payload,
                    "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
                    "request_url": "https://example.test/Lucid",
                }

                with self.assertRaisesRegex(SnapshotError, message):
                    parse_dictionary_api_dev(record, config)

    def test_dictionary_api_dev_rejects_a_non_string_example(self):
        payload: list[dict[str, Any]] = [
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
                "word": "lucid",
            }
        ]
        record = {
            "normalized_term": "lucid",
            "payload": payload,
            "payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
            "request_url": "https://example.test/Lucid",
        }
        config = ProviderConfig(
            id="dictionaryapi-dev-v2",
            kind="http-json",
            priority=3,
            parser_version=1,
        )

        with self.assertRaisesRegex(
            SnapshotError,
            "example must be a string or null",
        ):
            parse_dictionary_api_dev(record, config)
