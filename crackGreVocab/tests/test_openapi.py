"""Contract and local-origin tests for the typed API boundary."""

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CORS_ALLOWED_ORIGINS=(
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ),
)
class OpenApiBoundaryTests(SimpleTestCase):
    """Cover schema publication and the deliberately narrow CORS policy."""

    def setUp(self):
        self.client = Client()

    def test_schema_publishes_the_readiness_responses(self):
        response = self.client.get(
            reverse("api:schema"),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        operation = response.json()["paths"]["/api/readiness/"]["get"]
        self.assertEqual(operation["operationId"], "readiness_retrieve")
        self.assertTrue({"200", "503"}.issubset(operation["responses"]))
        for status in ("200", "503"):
            self.assertEqual(
                operation["responses"][status]["content"]["application/json"][
                    "schema"
                ]["$ref"],
                "#/components/schemas/Readiness",
            )

    def test_cors_allows_only_configured_local_origins(self):
        url = reverse("api:service-index")

        allowed = self.client.get(url, HTTP_ORIGIN="http://localhost:3000")
        unlisted = self.client.get(url, HTTP_ORIGIN="https://example.com")

        self.assertEqual(
            allowed.headers["Access-Control-Allow-Origin"],
            "http://localhost:3000",
        )
        self.assertNotIn("Access-Control-Allow-Origin", unlisted.headers)
