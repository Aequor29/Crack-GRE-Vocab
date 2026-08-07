"""Focused model and API coverage for clean-rebuild learner accounts."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

LearnerAccount = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    CORS_ALLOWED_ORIGINS=(
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ),
    CSRF_TRUSTED_ORIGINS=(
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ),
)
class LearnerAccountApiTests(TestCase):
    """Cover the useful session lifecycle and its important failure paths."""

    origin = "http://127.0.0.1:3000"
    valid_password = "durable-recall-river-927"

    def setUp(self) -> None:
        self.client = Client(enforce_csrf_checks=True)

    def csrf_token(self, client: Client | None = None) -> str:
        active_client = client or self.client
        response = active_client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN=self.origin,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def post_json(
        self,
        url_name: str,
        payload: dict[str, str] | None,
        *,
        client: Client | None = None,
        csrf_token: str | None = None,
    ):
        active_client = client or self.client
        headers = {"HTTP_ORIGIN": self.origin}
        if csrf_token is not None:
            headers["HTTP_X_CSRFTOKEN"] = csrf_token
        return active_client.post(
            reverse(url_name),
            data=json.dumps(payload) if payload is not None else "",
            content_type="application/json",
            **headers,
        )

    def create_account(self, email: str = "learner@example.com"):
        return LearnerAccount.objects.create_user(
            email=email,
            display_name="Learner",
            password=self.valid_password,
        )

    def test_signup_refresh_signout_and_signin_lifecycle(self):
        token = self.csrf_token()
        signup = self.post_json(
            "accounts:sign-up",
            {
                "email": "  Learner@Example.COM ",
                "display_name": "  Ada Learner  ",
                "password": self.valid_password,
            },
            csrf_token=token,
        )

        self.assertEqual(signup.status_code, 201)
        self.assertEqual(
            signup.json(),
            {
                "id": signup.json()["id"],
                "email": "learner@example.com",
                "display_name": "Ada Learner",
            },
        )
        self.assertNotIn("password", signup.json())
        account = LearnerAccount.objects.get()
        self.assertTrue(account.check_password(self.valid_password))
        self.assertNotEqual(account.password, self.valid_password)

        session_cookie = signup.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(session_cookie["httponly"])
        self.assertEqual(session_cookie["samesite"], "Lax")

        refreshed_client = Client(enforce_csrf_checks=True)
        refreshed_client.cookies[settings.SESSION_COOKIE_NAME] = session_cookie.value
        current = refreshed_client.get(reverse("accounts:account"))
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["email"], "learner@example.com")

        signout_token = self.csrf_token(refreshed_client)
        signout = self.post_json(
            "accounts:sign-out",
            None,
            client=refreshed_client,
            csrf_token=signout_token,
        )
        self.assertEqual(signout.status_code, 204)
        self.assertEqual(
            refreshed_client.get(reverse("accounts:account")).status_code,
            403,
        )

        signin_token = self.csrf_token(refreshed_client)
        signin = self.post_json(
            "accounts:sign-in",
            {"email": "LEARNER@example.com", "password": self.valid_password},
            client=refreshed_client,
            csrf_token=signin_token,
        )
        self.assertEqual(signin.status_code, 200)
        self.assertEqual(signin.json()["display_name"], "Ada Learner")
        self.assertEqual(
            refreshed_client.get(reverse("accounts:account")).status_code,
            200,
        )

    def test_anonymous_account_mutations_require_csrf(self):
        signup = self.post_json(
            "accounts:sign-up",
            {
                "email": "learner@example.com",
                "display_name": "Learner",
                "password": self.valid_password,
            },
        )
        signin = self.post_json(
            "accounts:sign-in",
            {"email": "learner@example.com", "password": self.valid_password},
        )

        self.assertEqual(signup.status_code, 403)
        self.assertEqual(signin.status_code, 403)
        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_hostile_origin_cannot_use_a_valid_csrf_token(self):
        token = self.csrf_token()
        response = self.client.post(
            reverse("accounts:sign-up"),
            data=json.dumps(
                {
                    "email": "learner@example.com",
                    "display_name": "Learner",
                    "password": self.valid_password,
                }
            ),
            content_type="application/json",
            HTTP_ORIGIN="https://hostile.example",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_signup_rejects_weak_password_and_case_variant_duplicate(self):
        token = self.csrf_token()
        weak = self.post_json(
            "accounts:sign-up",
            {
                "email": "learner@example.com",
                "display_name": "Learner",
                "password": "password",
            },
            csrf_token=token,
        )
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.json())

        self.create_account("Existing@Example.com")
        duplicate = self.post_json(
            "accounts:sign-up",
            {
                "email": "existing@example.COM",
                "display_name": "Second learner",
                "password": self.valid_password,
            },
            csrf_token=token,
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(
            duplicate.json()["email"],
            ["An account with this email already exists."],
        )

    def test_signup_rejects_oversized_email_and_malformed_json(self):
        token = self.csrf_token()
        oversized = self.post_json(
            "accounts:sign-up",
            {
                "email": f"{'a' * 243}@example.com",
                "display_name": "Learner",
                "password": self.valid_password,
            },
            csrf_token=token,
        )
        expanding_email = f"a@{'.'.join(['ß' * 50] * 4)}.com"
        self.assertLessEqual(len(expanding_email), 254)
        self.assertGreater(len(expanding_email.casefold()), 254)
        expanding = self.post_json(
            "accounts:sign-up",
            {
                "email": expanding_email,
                "display_name": "Learner",
                "password": self.valid_password,
            },
            csrf_token=token,
        )
        malformed = self.client.post(
            reverse("accounts:sign-up"),
            data="{",
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(oversized.status_code, 400)
        self.assertIn("email", oversized.json())
        self.assertEqual(expanding.status_code, 400)
        self.assertIn("email", expanding.json())
        self.assertEqual(malformed.status_code, 400)
        self.assertIn("detail", malformed.json())
        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_signup_rejects_non_json_content(self):
        token = self.csrf_token()
        response = self.client.post(
            reverse("accounts:sign-up"),
            data="email=learner@example.com",
            content_type="text/plain",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("detail", response.json())
        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_signup_handles_a_unique_email_race_as_validation(self):
        token = self.csrf_token()
        with patch(
            "accounts.serializers.LearnerAccount.objects.create_user",
            side_effect=IntegrityError,
        ):
            response = self.post_json(
                "accounts:sign-up",
                {
                    "email": "learner@example.com",
                    "display_name": "Learner",
                    "password": self.valid_password,
                },
                csrf_token=token,
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["email"],
            ["An account with this email already exists."],
        )

    def test_database_rejects_case_variant_email_outside_the_manager(self):
        self.create_account()

        with self.assertRaises(IntegrityError), transaction.atomic():
            LearnerAccount.objects.bulk_create(
                [
                    LearnerAccount(
                        email="LEARNER@EXAMPLE.COM",
                        display_name="Second learner",
                        password="not-a-usable-login",
                    )
                ]
            )

    def test_shared_account_validation_rejects_email_expanded_by_casefold(self):
        expanding_email = f"a@{'.'.join(['ß' * 50] * 4)}.com"
        account = LearnerAccount(
            email=expanding_email,
            display_name="Learner",
        )

        with self.assertRaises(ValidationError) as validation:
            account.full_clean(exclude=("password",))
        self.assertIn("email", validation.exception.message_dict)

        with self.assertRaisesMessage(ValueError, "at most 254 characters"):
            LearnerAccount.objects.create_user(
                email=expanding_email,
                display_name="Learner",
                password=self.valid_password,
            )
        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_signin_uses_one_generic_error_for_bad_credentials(self):
        self.create_account()
        token = self.csrf_token()

        wrong_password = self.post_json(
            "accounts:sign-in",
            {"email": "learner@example.com", "password": "not-the-password"},
            csrf_token=token,
        )
        unknown_email = self.post_json(
            "accounts:sign-in",
            {"email": "unknown@example.com", "password": "not-the-password"},
            csrf_token=token,
        )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_email.status_code, 401)
        self.assertEqual(wrong_password.json(), unknown_email.json())
        self.assertEqual(
            wrong_password.json(),
            {"detail": "Email or password is incorrect."},
        )

    def test_anonymous_and_expired_sessions_cannot_read_the_account(self):
        self.assertEqual(self.client.get(reverse("accounts:account")).status_code, 403)

        account = self.create_account()
        self.client.force_login(account)
        session = self.client.session
        session.set_expiry(timedelta(seconds=-1))
        session.save()

        self.assertEqual(self.client.get(reverse("accounts:account")).status_code, 403)

    def test_auth_cors_allows_credentials_only_for_an_exact_origin(self):
        allowed = self.client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN=self.origin,
        )
        unlisted = self.client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN="https://example.com",
        )

        self.assertEqual(
            allowed.headers["Access-Control-Allow-Origin"],
            self.origin,
        )
        self.assertEqual(allowed.headers["Access-Control-Allow-Credentials"], "true")
        self.assertNotIn("Access-Control-Allow-Origin", unlisted.headers)
