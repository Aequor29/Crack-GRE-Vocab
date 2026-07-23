"""Tests for strict environment parsing."""

import os
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
