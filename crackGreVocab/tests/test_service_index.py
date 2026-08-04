"""Contract tests for the database-independent API service index."""

from api.views import ServiceIndexView
from django.test import Client, SimpleTestCase, override_settings
from django.urls import resolve, reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class ServiceIndexTests(SimpleTestCase):
    """Cover successful and rejected requests without allowing database access."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("api:service-index")

    def test_route_resolves_to_the_service_index(self):
        match = resolve(self.url)
        self.assertIs(match.func.view_class, ServiceIndexView)
        self.assertEqual(self.url, "/api/")

    def test_view_does_not_depend_on_authentication(self):
        self.assertEqual(ServiceIndexView.authentication_classes, ())

    def test_get_returns_the_exact_public_service_document(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"service": "crack-gre-vocab-api"})

    def test_query_parameters_are_not_reflected(self):
        response = self.client.get(self.url, {"secret": "do-not-reflect"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"service": "crack-gre-vocab-api"})
        self.assertNotIn(b"do-not-reflect", response.content)

    def test_head_returns_headers_without_a_body(self):
        response = self.client.head(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_options_returns_api_metadata_and_the_allow_contract(self):
        response = self.client.options(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.headers["Allow"], "GET, HEAD, OPTIONS")
        self.assertEqual(response.json()["renders"], ["application/json"])

    def test_mutating_methods_are_rejected_with_a_stable_allow_contract(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.url,
                    data=b'{"malformed":',
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "GET, HEAD, OPTIONS")
                self.assertEqual(
                    response.json(),
                    {"detail": f'Method "{method.upper()}" not allowed.'},
                )

    def test_unsupported_response_format_is_rejected_as_json(self):
        response = self.client.get(self.url, HTTP_ACCEPT="text/html")

        self.assertEqual(response.status_code, 406)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertIn("detail", response.json())

    def test_missing_slash_redirects_to_the_canonical_route(self):
        response = self.client.get("/api")

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "/api/")

    def test_unknown_api_route_returns_not_found(self):
        response = self.client.get("/api/unknown/")

        self.assertEqual(response.status_code, 404)
