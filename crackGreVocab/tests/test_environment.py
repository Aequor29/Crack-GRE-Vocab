"""Unit tests for the fail-closed environment parsing contract."""

import os
from unittest import TestCase
from unittest.mock import patch

from crackGreVocab.config import (
    env_bool,
    env_list,
    postgres_database_url,
    required_env,
)
from django.core.exceptions import ImproperlyConfigured


class RequiredEnvironmentTests(TestCase):
    """Exercise successful and rejected required settings."""

    @patch.dict(os.environ, {"VALUE": "  configured  "}, clear=True)
    def test_required_env_returns_a_trimmed_value(self):
        self.assertEqual(required_env("VALUE"), "configured")

    def test_required_env_rejects_missing_and_blank_values(self):
        for environment in ({}, {"VALUE": ""}, {"VALUE": "   "}):
            with self.subTest(environment=environment):
                with (
                    patch.dict(os.environ, environment, clear=True),
                    self.assertRaisesRegex(
                        ImproperlyConfigured,
                        "Required environment variable VALUE is missing",
                    ),
                ):
                    required_env("VALUE")


class BooleanEnvironmentTests(TestCase):
    """Exercise every supported spelling and malformed booleans."""

    def test_env_bool_accepts_supported_true_values(self):
        for value in ("1", "true", "TRUE", " yes ", "on"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"FLAG": value}, clear=True
            ):
                self.assertIs(env_bool("FLAG", default=False), True)

    def test_env_bool_accepts_supported_false_values(self):
        for value in ("0", "false", "FALSE", " no ", "off"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"FLAG": value}, clear=True
            ):
                self.assertIs(env_bool("FLAG", default=True), False)

    @patch.dict(os.environ, {}, clear=True)
    def test_env_bool_uses_the_explicit_default_when_unset(self):
        self.assertIs(env_bool("FLAG", default=True), True)
        self.assertIs(env_bool("FLAG", default=False), False)

    def test_env_bool_rejects_blank_and_unknown_values(self):
        for value in ("", "   ", "sometimes", "2"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"FLAG": value}, clear=True
            ), self.assertRaisesRegex(ImproperlyConfigured, "FLAG must be one of"):
                env_bool("FLAG", default=False)


class ListEnvironmentTests(TestCase):
    """Exercise list normalization, defaults, and explicit empty values."""

    @patch.dict(
        os.environ,
        {"HOSTS": "localhost, api.example.com  127.0.0.1"},
        clear=True,
    )
    def test_env_list_accepts_commas_and_whitespace(self):
        self.assertEqual(
            env_list("HOSTS"),
            ["localhost", "api.example.com", "127.0.0.1"],
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_env_list_returns_an_independent_copy_of_the_default(self):
        default = ["localhost"]
        result = env_list("HOSTS", default=default)
        result.append("127.0.0.1")
        self.assertEqual(default, ["localhost"])

    @patch.dict(os.environ, {"HOSTS": "  "}, clear=True)
    def test_env_list_preserves_an_explicit_empty_list(self):
        self.assertEqual(env_list("HOSTS", default=("localhost",)), [])


class PostgreSQLUrlTests(TestCase):
    """Exercise accepted PostgreSQL URL forms and invalid database contracts."""

    def test_postgres_database_url_accepts_supported_schemes(self):
        values = (
            "postgres://user:password@localhost:5432/app",
            "postgresql://user:password@localhost:5432/app",
            "postgresql:///app",
        )
        for value in values:
            with self.subTest(value=value), patch.dict(
                os.environ, {"DATABASE_URL": value}, clear=True
            ):
                self.assertEqual(postgres_database_url(), value)

    def test_postgres_database_url_rejects_other_or_malformed_urls(self):
        cases = (
            ("mysql://localhost/app", "must use PostgreSQL"),
            ("sqlite:///db.sqlite3", "must use PostgreSQL"),
            ("not-a-url", "must use PostgreSQL"),
            ("postgresql://localhost", "must include a database name"),
            ("postgresql:app", "must be a valid PostgreSQL URL"),
            ("postgresql:/app", "must be a valid PostgreSQL URL"),
            (
                "postgresql://localhost:bad/app",
                "must be a valid PostgreSQL URL",
            ),
            ("postgresql://[broken/app", "must be a valid PostgreSQL URL"),
        )
        for value, message in cases:
            with self.subTest(value=value), patch.dict(
                os.environ, {"DATABASE_URL": value}, clear=True
            ), self.assertRaisesRegex(ImproperlyConfigured, message):
                postgres_database_url()
