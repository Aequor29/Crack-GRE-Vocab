"""Public API coverage for learner password recovery."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

LearnerAccount = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_RESET_FRONTEND_URL=("http://127.0.0.1:3000/reset-password/confirm"),
    SECURE_SSL_REDIRECT=False,
)
class PasswordRecoveryApiTests(TestCase):
    """Exercise recovery through its CSRF-protected HTTP boundary."""

    origin = "http://127.0.0.1:3000"
    original_password = "durable-recall-river-927"

    def setUp(self) -> None:
        self.client = Client(enforce_csrf_checks=True)

    def csrf_token(self, client: Client | None = None) -> str:
        """Return a masked CSRF token from the public auth endpoint."""
        active_client = client or self.client
        response = active_client.get(
            reverse("accounts:csrf"),
            HTTP_ORIGIN=self.origin,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def request_password_reset(self, email: str):
        """Submit a password-reset request through the public API."""
        return self.client.post(
            reverse("accounts:password-reset"),
            data=json.dumps({"email": email}),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def password_reset_parameters(self) -> dict[str, str]:
        """Read the opaque confirmation parameters from the delivered link."""
        reset_url = next(
            line
            for line in mail.outbox[-1].body.splitlines()
            if line.startswith("http")
        )
        return {
            key: values[0]
            for key, values in parse_qs(urlparse(reset_url).query).items()
        }

    def confirm_password_reset(self, payload: dict[str, str]):
        """Submit a password-reset confirmation through the public API."""
        return self.client.post(
            reverse("accounts:password-reset-confirm"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def sign_in(self, client: Client, password: str) -> None:
        """Establish a learner session through the public sign-in endpoint."""
        response = client.post(
            reverse("accounts:sign-in"),
            data=json.dumps(
                {"email": "learner@example.com", "password": password}
            ),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(client),
        )
        self.assertEqual(response.status_code, 200)

    def test_request_is_non_enumerating_and_emails_only_recoverable_account(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )
        LearnerAccount.objects.create_user(
            email="inactive@example.com",
            display_name="Inactive learner",
            password=self.original_password,
            is_active=False,
        )
        LearnerAccount.objects.create_user(
            email="google-only@example.com",
            display_name="Google-only learner",
            password=None,
        )

        known_response = self.request_password_reset("LEARNER@example.com")
        unknown_response = self.request_password_reset("unknown@example.com")
        inactive_response = self.request_password_reset("inactive@example.com")
        unusable_password_response = self.request_password_reset(
            "google-only@example.com"
        )

        self.assertEqual(known_response.status_code, 202)
        self.assertEqual(unknown_response.status_code, 202)
        self.assertEqual(known_response.json(), unknown_response.json())
        self.assertEqual(known_response.json(), inactive_response.json())
        self.assertEqual(known_response.json(), unusable_password_response.json())
        self.assertEqual(
            known_response.json(),
            {
                "detail": (
                    "If an account can be recovered, a password reset link has "
                    "been sent."
                )
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["learner@example.com"])

        reset_url = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith("http")
        )
        parsed_url = urlparse(reset_url)
        self.assertEqual(parsed_url.path, "/reset-password/confirm")
        self.assertEqual(parsed_url.netloc, "127.0.0.1:3000")
        self.assertEqual(set(parse_qs(parsed_url.query)), {"token", "uid"})

    def test_delivery_failure_does_not_reveal_account_existence(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )

        with self.assertLogs("accounts.password_recovery", level="ERROR") as logs:
            with patch(
                "accounts.password_recovery.send_mail",
                side_effect=OSError("mail sink unavailable"),
            ):
                known_response = self.request_password_reset("learner@example.com")
        unknown_response = self.request_password_reset("unknown@example.com")

        self.assertEqual(known_response.status_code, 202)
        self.assertEqual(known_response.json(), unknown_response.json())
        self.assertIn("Password reset delivery failed", logs.output[0])

    def test_unexpected_delivery_defect_reaches_normal_error_reporting(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )

        with patch(
            "accounts.password_recovery.send_mail",
            side_effect=RuntimeError("application defect"),
        ):
            with self.assertRaisesMessage(RuntimeError, "application defect"):
                self.request_password_reset("learner@example.com")

    def test_valid_confirmation_changes_password_once(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )
        self.request_password_reset("learner@example.com")
        reset_parameters = self.password_reset_parameters()
        new_password = "focused-review-summit-482"

        confirmed = self.confirm_password_reset(
            {**reset_parameters, "password": new_password}
        )

        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(
            confirmed.json(),
            {"detail": "Password reset complete. Sign in with your new password."},
        )

        old_password_signin = self.client.post(
            reverse("accounts:sign-in"),
            data=json.dumps(
                {
                    "email": "learner@example.com",
                    "password": self.original_password,
                }
            ),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        new_password_signin = self.client.post(
            reverse("accounts:sign-in"),
            data=json.dumps({"email": "learner@example.com", "password": new_password}),
            content_type="application/json",
            HTTP_ORIGIN=self.origin,
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        replayed = self.confirm_password_reset(
            {**reset_parameters, "password": "another-strong-password-193"}
        )

        self.assertEqual(old_password_signin.status_code, 401)
        self.assertEqual(new_password_signin.status_code, 200)
        self.assertEqual(replayed.status_code, 400)
        self.assertEqual(
            replayed.json(),
            {"detail": "This password reset link is invalid or has expired."},
        )

    def test_confirmation_expires_at_thirty_minutes(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )
        issued_at = datetime(2026, 8, 10, 3, 30, 0)
        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now",
            return_value=issued_at,
        ):
            self.request_password_reset("learner@example.com")
        reset_parameters = self.password_reset_parameters()

        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now",
            return_value=issued_at + timedelta(minutes=30),
        ):
            expired = self.confirm_password_reset(
                {**reset_parameters, "password": "focused-review-summit-482"}
            )
        malformed = self.confirm_password_reset(
            {
                "uid": reset_parameters["uid"],
                "token": "invalid-token",
                "password": "focused-review-summit-482",
            }
        )

        self.assertEqual(expired.status_code, 400)
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(expired.json(), malformed.json())
        self.assertEqual(
            expired.json(),
            {"detail": "This password reset link is invalid or has expired."},
        )

    def test_successful_reset_invalidates_every_existing_session(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )
        first_session = Client(enforce_csrf_checks=True)
        second_session = Client(enforce_csrf_checks=True)
        self.sign_in(first_session, self.original_password)
        self.sign_in(second_session, self.original_password)
        self.assertEqual(
            first_session.get(reverse("accounts:account")).status_code,
            200,
        )
        self.assertEqual(
            second_session.get(reverse("accounts:account")).status_code,
            200,
        )

        self.request_password_reset("learner@example.com")
        confirmed = self.confirm_password_reset(
            {
                **self.password_reset_parameters(),
                "password": "focused-review-summit-482",
            }
        )

        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(
            first_session.get(reverse("accounts:account")).status_code,
            403,
        )
        self.assertEqual(
            second_session.get(reverse("accounts:account")).status_code,
            403,
        )

    def test_weak_password_is_rejected_without_consuming_the_token(self):
        LearnerAccount.objects.create_user(
            email="learner@example.com",
            display_name="Learner",
            password=self.original_password,
        )
        self.request_password_reset("learner@example.com")
        reset_parameters = self.password_reset_parameters()

        rejected = self.confirm_password_reset(
            {**reset_parameters, "password": "password"}
        )
        accepted = self.confirm_password_reset(
            {**reset_parameters, "password": "focused-review-summit-482"}
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertIn("password", rejected.json())
        self.assertEqual(accepted.status_code, 200)
