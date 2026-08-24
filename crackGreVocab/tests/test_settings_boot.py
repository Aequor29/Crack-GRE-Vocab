"""Isolated smoke tests for Django settings startup."""

from unittest import TestCase

from dotenv import dotenv_values

from .helpers import BACKEND_ROOT, run_settings_script

BOOT_SCRIPT = """
from crackGreVocab import settings
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
print("booted")
"""


class SettingsBootTests(TestCase):
    """Smoke-test one supported boot and one rejected database contract."""

    def test_example_environment_is_a_bootable_contract(self):
        values = {
            key: value
            for key, value in dotenv_values(BACKEND_ROOT / ".env.example").items()
            if value is not None
        }
        result = run_settings_script(BOOT_SCRIPT, overrides=values)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "booted")

    def test_non_postgresql_database_is_rejected(self):
        result = run_settings_script(
            BOOT_SCRIPT,
            overrides={"DATABASE_URL": "mysql://localhost/app"},
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("DATABASE_URL must use PostgreSQL", result.stderr)

    def test_google_credentials_must_be_configured_as_a_pair(self):
        result = run_settings_script(
            BOOT_SCRIPT,
            overrides={
                "GOOGLE_OAUTH_CLIENT_ID": "client-id-only",
                "GOOGLE_OAUTH_CLIENT_SECRET": "",
            },
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET",
            result.stderr,
        )

    def test_enabled_google_oauth_requires_explicit_hosted_callback(self):
        result = run_settings_script(
            BOOT_SCRIPT,
            overrides={
                "GOOGLE_OAUTH_CALLBACK_URL": "",
                "GOOGLE_OAUTH_CLIENT_ID": "fresh-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "fresh-client-secret",
            },
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("GOOGLE_OAUTH_CALLBACK_URL", result.stderr)

    def test_enabled_google_oauth_requires_https_when_hosted(self):
        result = run_settings_script(
            BOOT_SCRIPT,
            overrides={
                "GOOGLE_OAUTH_CALLBACK_URL": (
                    "http://api.example.com/api/auth/google/callback/"
                ),
                "GOOGLE_OAUTH_CLIENT_ID": "fresh-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "fresh-client-secret",
                "GOOGLE_OAUTH_FRONTEND_ORIGIN": "http://app.example.com",
            },
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("must use HTTPS", result.stderr)

    def test_hosted_google_oauth_cannot_be_disabled(self):
        result = run_settings_script(
            BOOT_SCRIPT,
            overrides={
                "GOOGLE_OAUTH_CLIENT_ID": "",
                "GOOGLE_OAUTH_CLIENT_SECRET": "",
            },
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("must be configured when DEBUG is false", result.stderr)
