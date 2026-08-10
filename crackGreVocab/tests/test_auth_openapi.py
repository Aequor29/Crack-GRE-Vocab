"""OpenAPI coverage for the generated learner-account boundary."""

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class AccountOpenApiTests(SimpleTestCase):
    """Keep auth paths and status contracts visible to the frontend."""

    def test_schema_publishes_the_account_session_contract(self):
        response = Client().get(
            reverse("api:schema"),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        expected = {
            "/api/auth/csrf/": ("get", {"200"}),
            "/api/auth/sign-up/": ("post", {"201", "400", "403", "415"}),
            "/api/auth/sign-in/": ("post", {"200", "400", "401", "403", "415"}),
            "/api/auth/password-reset/": (
                "post",
                {"202", "400", "403", "415"},
            ),
            "/api/auth/password-reset/confirm/": (
                "post",
                {"200", "400", "403", "415"},
            ),
            "/api/auth/google/link/confirm/": (
                "post",
                {"200", "400", "401", "403", "409", "415"},
            ),
            "/api/auth/google/link/cancel/": ("post", {"204", "403"}),
            "/api/auth/sign-out/": ("post", {"204", "403"}),
            "/api/auth/account/": ("get", {"200", "403"}),
        }

        for path, (method, statuses) in expected.items():
            self.assertEqual(set(paths[path][method]["responses"]), statuses)

        for path in (
            "/api/auth/sign-up/",
            "/api/auth/sign-in/",
            "/api/auth/password-reset/",
            "/api/auth/password-reset/confirm/",
            "/api/auth/google/link/confirm/",
            "/api/auth/google/link/cancel/",
            "/api/auth/sign-out/",
        ):
            csrf_header = paths[path]["post"]["parameters"][0]
            self.assertEqual(csrf_header["name"], "X-CSRFToken")
            self.assertEqual(csrf_header["in"], "header")
            self.assertTrue(csrf_header["required"])
