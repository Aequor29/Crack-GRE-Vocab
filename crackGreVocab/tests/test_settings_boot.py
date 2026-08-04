"""Isolated startup tests for development and production settings."""

from unittest import TestCase

from dotenv import dotenv_values

from .helpers import BACKEND_ROOT, run_settings_script

BOOT_SCRIPT = """
from crackGreVocab import settings
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
print("booted")
"""


class SettingsBootTests(TestCase):
    """Verify valid settings boot and invalid settings fail early."""

    def assert_boots(self, **kwargs):
        result = run_settings_script(BOOT_SCRIPT, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "booted")

    def assert_rejected(self, expected_message: str, **kwargs):
        result = run_settings_script(BOOT_SCRIPT, **kwargs)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn(expected_message, result.stderr)

    def test_minimal_development_settings_boot_with_local_defaults(self):
        self.assert_boots(
            overrides={"DEBUG": "true"},
            unset=("ALLOWED_HOSTS",),
        )

    def test_production_settings_boot_with_secure_defaults(self):
        script = """
from crackGreVocab import settings
assert settings.DEBUG is False
assert settings.SESSION_COOKIE_SECURE is True
assert settings.CSRF_COOKIE_SECURE is True
assert settings.SECURE_SSL_REDIRECT is True
assert settings.SECURE_PROXY_SSL_HEADER is None
print("secure")
"""
        result = run_settings_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "secure")

    def test_example_environment_is_a_bootable_contract(self):
        values = {
            key: value
            for key, value in dotenv_values(BACKEND_ROOT / ".env.example").items()
            if value is not None
        }
        self.assert_boots(overrides=values, unset=("ALLOWED_HOSTS",))

    def test_both_postgresql_url_schemes_boot(self):
        for value in (
            "postgres://user:password@localhost:5432/app",
            "postgresql://user:password@localhost:5432/app",
        ):
            with self.subTest(value=value):
                self.assert_boots(overrides={"DATABASE_URL": value})

    def test_required_and_typed_settings_fail_closed(self):
        cases = (
            ({"SECRET_KEY": ""}, "SECRET_KEY is missing"),
            ({"DATABASE_URL": ""}, "DATABASE_URL is missing"),
            ({"DATABASE_URL": "mysql://localhost/app"}, "must use PostgreSQL"),
            (
                {"DATABASE_URL": "postgresql://localhost"},
                "must include a database name",
            ),
            (
                {"DATABASE_URL": "postgresql:app"},
                "must be a valid PostgreSQL URL",
            ),
            (
                {"DATABASE_URL": "postgresql:/app"},
                "must be a valid PostgreSQL URL",
            ),
            (
                {"DATABASE_URL": "postgresql://localhost:bad/app"},
                "must be a valid PostgreSQL URL",
            ),
            (
                {"DATABASE_URL": "postgresql://[broken/app"},
                "must be a valid PostgreSQL URL",
            ),
            ({"DEBUG": "sometimes"}, "DEBUG must be one of"),
            ({"ALLOWED_HOSTS": ""}, "ALLOWED_HOSTS must contain"),
            (
                {"SECURE_SSL_REDIRECT": "sometimes"},
                "SECURE_SSL_REDIRECT must be one of",
            ),
            (
                {"TRUST_X_FORWARDED_PROTO": "sometimes"},
                "TRUST_X_FORWARDED_PROTO must be one of",
            ),
            (
                {"SECURE_HSTS_INCLUDE_SUBDOMAINS": "sometimes"},
                "SECURE_HSTS_INCLUDE_SUBDOMAINS must be one of",
            ),
        )
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                self.assert_rejected(message, overrides=overrides)
