"""Architecture tests for the clean backend runtime contract."""

from pathlib import Path

from crackGreVocab.asgi import application as asgi_application
from crackGreVocab.wsgi import application as wsgi_application
from django.apps import apps
from django.conf import settings
from django.core import checks
from django.test import SimpleTestCase

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class RuntimeContractTests(SimpleTestCase):
    """Protect the clean foundation from retired runtime dependencies."""

    def test_first_party_api_application_is_installed(self):
        self.assertTrue(apps.is_installed("api"))
        self.assertEqual(apps.get_app_config("api").verbose_name, "Crack GRE Vocab API")

    def test_wsgi_and_asgi_entrypoints_are_callable(self):
        self.assertTrue(callable(wsgi_application))
        self.assertTrue(callable(asgi_application))

    def test_django_system_checks_have_no_findings(self):
        self.assertEqual(checks.run_checks(), [])

    def test_session_authentication_is_the_only_default(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
            ("rest_framework.authentication.SessionAuthentication",),
        )

    def test_retired_backend_dependencies_and_apps_are_absent(self):
        manifests = (
            BACKEND_ROOT / "requirements.in",
            BACKEND_ROOT / "requirements.txt",
        )
        runtime_contract = "\n".join(
            path.read_text(encoding="utf-8") for path in manifests
        ).casefold()
        settings_contract = "\n".join(settings.INSTALLED_APPS).casefold()

        for retired in ("mysql", "pymysql", "simplejwt", "pyjwt", "vocab_backend"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, runtime_contract)
                self.assertNotIn(retired, settings_contract)
