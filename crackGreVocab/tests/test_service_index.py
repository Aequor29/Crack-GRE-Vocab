"""Smoke tests for the database-independent API service index."""

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class ServiceIndexTests(SimpleTestCase):
    """Cover the service document's happy and unhappy paths."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("api:service-index")

    def test_get_returns_the_exact_public_service_document(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"service": "crack-gre-vocab-api"})

    def test_post_is_rejected(self):
        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, 405)
