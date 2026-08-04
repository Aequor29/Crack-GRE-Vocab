"""Focused tests for the database-aware readiness contract."""

from unittest.mock import patch

from django.db import DatabaseError, InterfaceError
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class ReadinessTests(TestCase):
    """Cover the ready response and its safe database failure state."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("api:readiness")

    def test_get_reports_ready_when_postgresql_answers(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ready", "database": "available"},
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    @patch("api.views.connection.cursor")
    def test_get_reports_generic_unavailable_when_postgresql_fails(self, cursor):
        for error_type in (DatabaseError, InterfaceError):
            with self.subTest(error_type=error_type.__name__):
                cursor.side_effect = error_type("secret-host.example.invalid")

                response = self.client.get(self.url)

                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json(),
                    {"status": "unavailable", "database": "unavailable"},
                )
                self.assertNotContains(
                    response,
                    "secret-host.example.invalid",
                    status_code=503,
                )
                self.assertEqual(response.headers["Cache-Control"], "no-store")
