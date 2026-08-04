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
