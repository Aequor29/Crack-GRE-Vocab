"""Public boundary coverage for Google OIDC sign-in and confirmed linking."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from accounts.google_oauth import get_google_oauth_client
from accounts.models import GoogleIdentity
from authlib.integrations.base_client import OAuthError
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from requests import ConnectionError as ProviderConnectionError

LearnerAccount = get_user_model()


@override_settings(
    GOOGLE_OAUTH_CALLBACK_URL=(
        "http://127.0.0.1:8000/api/auth/google/callback/"
    ),
    GOOGLE_OAUTH_CLIENT_ID="fresh-local-client-id",
    GOOGLE_OAUTH_CLIENT_SECRET="fresh-local-client-secret",
    GOOGLE_OAUTH_ENABLED=True,
    GOOGLE_OAUTH_FRONTEND_ORIGIN="http://127.0.0.1:3000",
    SECURE_SSL_REDIRECT=False,
)
class GoogleAuthenticationApiTests(TestCase):
    """Exercise the provider, account, session, and conflict boundaries."""

    origin = "http://127.0.0.1:3000"
    password = "durable-recall-river-927"

    def setUp(self) -> None:
        self.client = Client(enforce_csrf_checks=True)
        self.google_client = Mock()
        self.google_client.authorize_redirect.return_value = HttpResponseRedirect(
            "https://accounts.google.test/authorize"
        )

    def csrf_token(self) -> str:
        """Return one masked CSRF token from the public account API."""
        response = self.client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN=self.origin,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def provider_claims(
        self,
        *,
        subject: str = "google-subject-1",
        email: str = "learner@example.com",
        email_verified: bool = True,
        name: str = "Ada Learner",
    ) -> dict[str, object]:
        """Return the verified-claim shape produced by the OIDC client seam."""
        return {
            "email": email,
            "email_verified": email_verified,
            "name": name,
            "sub": subject,
        }

    def provider_callback(self, claims: dict[str, object]):
        """Complete the callback with mocked cryptographically verified claims."""
        self.google_client.authorize_access_token.return_value = {
            "userinfo": claims,
        }
        with patch(
            "accounts.google_views.get_google_oauth_client",
            return_value=self.google_client,
        ):
            return self.client.get(
                reverse("accounts:google-callback"),
                {"code": "provider-code", "state": "provider-state"},
            )

    def post_confirmation(self, password: str):
        """Submit explicit password-account ownership confirmation."""
        return self.client.post(
            reverse("accounts:google-link-confirm"),
            data=json.dumps({"password": password}),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def test_start_returns_the_provider_authorization_redirect(self):
        with patch(
            "accounts.google_views.get_google_oauth_client",
            return_value=self.google_client,
        ):
            response = self.client.get(reverse("accounts:google-start"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://accounts.google.test/authorize",
        )
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_oidc_client_enables_openid_nonce_and_pkce(self):
        google_client = get_google_oauth_client()

        self.assertEqual(google_client.client_id, "fresh-local-client-id")
        self.assertEqual(
            google_client.client_kwargs,
            {
                "code_challenge_method": "S256",
                "scope": "openid email profile",
            },
        )

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="",
        GOOGLE_OAUTH_CLIENT_SECRET="",
        GOOGLE_OAUTH_ENABLED=False,
    )
    def test_start_reports_when_fresh_provider_credentials_are_not_configured(self):
        response = self.client.get(reverse("accounts:google-start"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:3000/sign-in?google=unavailable",
        )

    def test_provider_transport_failure_returns_a_safe_provider_error(self):
        self.google_client.authorize_redirect.side_effect = ProviderConnectionError(
            "provider unavailable"
        )
        with patch(
            "accounts.google_views.get_google_oauth_client",
            return_value=self.google_client,
        ):
            response = self.client.get(reverse("accounts:google-start"))

        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:3000/sign-in?google=provider-error",
        )

    def test_unexpected_start_failure_reaches_normal_error_reporting(self):
        self.google_client.authorize_redirect.side_effect = RuntimeError(
            "application defect"
        )
        with patch(
            "accounts.google_views.get_google_oauth_client",
            return_value=self.google_client,
        ):
            with self.assertRaisesMessage(RuntimeError, "application defect"):
                self.client.get(reverse("accounts:google-start"))

    def test_new_verified_google_identity_creates_and_signs_in_account(self):
        response = self.provider_callback(self.provider_claims())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:3000/account?google=connected",
        )
        account = LearnerAccount.objects.get(email="learner@example.com")
        self.assertFalse(account.has_usable_password())
        self.assertEqual(account.display_name, "Ada Learner")
        self.assertEqual(
            GoogleIdentity.objects.get(account=account).subject,
            "google-subject-1",
        )
        self.assertEqual(
            self.client.get(reverse("accounts:account")).json()["id"],
            account.pk,
        )

    def test_returning_subject_signs_in_without_relinking_changed_email(self):
        account = LearnerAccount.objects.create_user(
            email="original@example.com",
            display_name="Original name",
            password=None,
        )
        GoogleIdentity.objects.create(
            account=account,
            subject="google-subject-1",
            email_at_link="original@example.com",
        )

        response = self.provider_callback(
            self.provider_claims(email="changed@example.com", name="Changed name")
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(LearnerAccount.objects.count(), 1)
        account.refresh_from_db()
        self.assertEqual(account.email, "original@example.com")
        self.assertEqual(
            self.client.get(reverse("accounts:account")).json()["id"],
            account.pk,
        )

    def test_inactive_google_linked_account_cannot_sign_in(self):
        account = LearnerAccount.objects.create_user(
            email="inactive@example.com",
            display_name="Inactive learner",
            password=None,
            is_active=False,
        )
        GoogleIdentity.objects.create(
            account=account,
            subject="google-subject-1",
            email_at_link=account.email,
        )

        response = self.provider_callback(
            self.provider_claims(email="inactive@example.com")
        )

        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:3000/sign-in?google=conflict",
        )
        self.assertEqual(
            self.client.get(reverse("accounts:account")).status_code,
            403,
        )

    def test_matching_password_account_requires_explicit_password_confirmation(self):
        account = LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Password learner",
            password=self.password,
        )

        callback = self.provider_callback(self.provider_claims())

        self.assertEqual(
            callback["Location"],
            "http://127.0.0.1:3000/sign-in?google=link-required",
        )
        self.assertFalse(GoogleIdentity.objects.filter(account=account).exists())
        self.assertEqual(
            self.client.get(reverse("accounts:account")).status_code,
            403,
        )

        rejected = self.post_confirmation("wrong-password")
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(
            rejected.json(),
            {"detail": "Enter the current password for this account."},
        )
        self.assertFalse(GoogleIdentity.objects.filter(account=account).exists())

        confirmed = self.post_confirmation(self.password)
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["id"], account.pk)
        self.assertTrue(GoogleIdentity.objects.filter(account=account).exists())
        self.assertEqual(
            self.client.get(reverse("accounts:account")).json()["id"],
            account.pk,
        )

    def test_distinct_google_identity_on_matching_email_never_merges(self):
        account = LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Existing Google learner",
            password=None,
        )
        GoogleIdentity.objects.create(
            account=account,
            subject="already-linked-subject",
            email_at_link=account.email,
        )

        response = self.provider_callback(
            self.provider_claims(subject="different-google-subject")
        )

        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:3000/sign-in?google=conflict",
        )
        self.assertEqual(GoogleIdentity.objects.count(), 1)
        self.assertEqual(LearnerAccount.objects.count(), 1)
        self.assertEqual(
            self.client.get(reverse("accounts:account")).status_code,
            403,
        )

    def test_unverified_or_incomplete_claims_fail_without_account_creation(self):
        for claims in (
            self.provider_claims(email_verified=False),
            {"email": "learner@example.com", "email_verified": True},
        ):
            with self.subTest(claims=claims):
                response = self.provider_callback(claims)
                self.assertEqual(
                    response["Location"],
                    "http://127.0.0.1:3000/sign-in?google=provider-error",
                )

        self.assertEqual(LearnerAccount.objects.count(), 0)
        self.assertEqual(GoogleIdentity.objects.count(), 0)

    def test_cancellation_and_provider_failure_have_distinct_safe_redirects(self):
        for error, expected_status in (
            (
                OAuthError(error="access_denied", description="user cancelled"),
                "cancelled",
            ),
            (
                OAuthError(error="invalid_state", description="sensitive detail"),
                "provider-error",
            ),
        ):
            with self.subTest(error=error.error):
                self.google_client.authorize_access_token.side_effect = error
                with patch(
                    "accounts.google_views.get_google_oauth_client",
                    return_value=self.google_client,
                ):
                    response = self.client.get(
                        reverse("accounts:google-callback"),
                        {"error": error.error},
                    )

                query = parse_qs(urlparse(response["Location"]).query)
                self.assertEqual(query, {"google": [expected_status]})

        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_callback_transport_failure_returns_a_safe_provider_error(self):
        self.google_client.authorize_access_token.side_effect = (
            ProviderConnectionError("provider unavailable")
        )
        with patch(
            "accounts.google_views.get_google_oauth_client",
            return_value=self.google_client,
        ):
            response = self.client.get(reverse("accounts:google-callback"))

        self.assertEqual(
            response["Location"],
            "http://127.0.0.1:3000/sign-in?google=provider-error",
        )
        self.assertEqual(LearnerAccount.objects.count(), 0)

    def test_pending_link_can_be_cancelled_and_cannot_then_be_confirmed(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Password learner",
            password=self.password,
        )
        self.provider_callback(self.provider_claims())

        cancelled = self.client.post(
            reverse("accounts:google-link-cancel"),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        confirmed = self.post_confirmation(self.password)

        self.assertEqual(cancelled.status_code, 204)
        self.assertEqual(confirmed.status_code, 400)
        self.assertEqual(
            confirmed.json(),
            {"detail": "Start Google sign-in again before linking."},
        )
        self.assertEqual(GoogleIdentity.objects.count(), 0)

    def test_pending_link_expires_before_password_confirmation(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Password learner",
            password=self.password,
        )
        issued_at = datetime(2026, 8, 10, 4, 0, tzinfo=UTC)
        with patch("accounts.google_views.timezone.now", return_value=issued_at):
            self.provider_callback(self.provider_claims())

        with patch(
            "accounts.google_views.timezone.now",
            return_value=issued_at + timedelta(minutes=10),
        ):
            confirmed = self.post_confirmation(self.password)

        self.assertEqual(confirmed.status_code, 400)
        self.assertEqual(
            confirmed.json(),
            {"detail": "Start Google sign-in again before linking."},
        )
        self.assertEqual(GoogleIdentity.objects.count(), 0)
