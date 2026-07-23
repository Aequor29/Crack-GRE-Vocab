"""Tests for strict environment parsing."""

import os
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from .config import env_bool, env_list, required_env


class EnvironmentConfigurationTests(TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_required_env_rejects_missing_value(self):
        with self.assertRaisesRegex(
            ImproperlyConfigured,
            "Required environment variable SECRET_KEY is missing.",
        ):
            required_env("SECRET_KEY")

    @patch.dict(os.environ, {"DEBUG": "false"}, clear=True)
    def test_env_bool_parses_false_explicitly(self):
        self.assertIs(env_bool("DEBUG", default=True), False)

    @patch.dict(os.environ, {"DEBUG": "not-a-boolean"}, clear=True)
    def test_env_bool_rejects_unknown_values(self):
        with self.assertRaises(ImproperlyConfigured):
            env_bool("DEBUG", default=False)

    @patch.dict(
        os.environ,
        {"ALLOWED_HOSTS": "localhost, api.example.com 127.0.0.1"},
        clear=True,
    )
    def test_env_list_accepts_commas_and_whitespace(self):
        self.assertEqual(
            env_list("ALLOWED_HOSTS"),
            ["localhost", "api.example.com", "127.0.0.1"],
        )


class ProductionSettingsTests(TestCase):
    base_environment = {
        "ALLOWED_HOSTS": "api.example.com",
        "CORS_ALLOWED_ORIGINS": "https://app.example.com",
        "CSRF_TRUSTED_ORIGINS": "https://app.example.com",
        "DATABASE_URL": "postgresql://user:password@localhost:5432/app",
        "DEBUG": "false",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": "false",
        "SECRET_KEY": "test-only-secret",
        "TRUST_X_FORWARDED_PROTO": "false",
    }

    def import_settings(self, *, environment=None, expression="DEBUG"):
        process_environment = {
            **os.environ,
            **self.base_environment,
            **(environment or {}),
        }
        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from crackGreVocab import settings; "
                    f"print(repr(settings.{expression}))"
                ),
            ],
            capture_output=True,
            check=False,
            env=process_environment,
            text=True,
        )

    def test_production_requires_cors_origins(self):
        result = self.import_settings(environment={"CORS_ALLOWED_ORIGINS": ""})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CORS_ALLOWED_ORIGINS must contain", result.stderr)

    def test_production_requires_csrf_origins(self):
        result = self.import_settings(environment={"CSRF_TRUSTED_ORIGINS": ""})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CSRF_TRUSTED_ORIGINS must contain", result.stderr)

    def test_non_postgresql_database_is_rejected(self):
        result = self.import_settings(
            environment={"DATABASE_URL": "sqlite:///db.sqlite3"}
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL must use PostgreSQL", result.stderr)

    def test_forwarded_proto_is_not_trusted_by_default(self):
        result = self.import_settings(expression="SECURE_PROXY_SSL_HEADER")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "None")

    def test_forwarded_proto_requires_explicit_opt_in(self):
        result = self.import_settings(
            environment={"TRUST_X_FORWARDED_PROTO": "true"},
            expression="SECURE_PROXY_SSL_HEADER",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "('HTTP_X_FORWARDED_PROTO', 'https')",
        )

    def test_hsts_subdomains_are_opt_in(self):
        result = self.import_settings(expression="SECURE_HSTS_INCLUDE_SUBDOMAINS")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")
