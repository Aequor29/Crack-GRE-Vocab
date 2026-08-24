"""Password-recovery delivery for clean-rebuild learner accounts."""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import LearnerAccount

logger = logging.getLogger(__name__)


class StrictPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """Reject a token once its configured lifetime has elapsed exactly."""

    def check_token(self, user, token):
        """Return whether a signed token is valid and strictly within its lifetime."""
        if not super().check_token(user, token):
            return False

        timestamp_base36, _ = token.split("-")
        timestamp = int(timestamp_base36, 36)
        age_seconds = self._num_seconds(self._now()) - timestamp
        return age_seconds < settings.PASSWORD_RESET_TIMEOUT


password_reset_token_generator = StrictPasswordResetTokenGenerator()


class InvalidPasswordReset(ValueError):
    """Indicate that a reset identity or token cannot be accepted."""


class PasswordResetValidationError(ValueError):
    """Carry password-policy messages across the recovery service boundary."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("The replacement password did not pass validation.")
        self.messages = messages


def send_password_reset_email(account: LearnerAccount) -> None:
    """Send one short-lived reset link to a recoverable learner account."""
    query = urlencode(
        {
            "uid": urlsafe_base64_encode(force_bytes(account.pk)),
            "token": password_reset_token_generator.make_token(account),
        }
    )
    reset_url = f"{settings.PASSWORD_RESET_FRONTEND_URL}?{query}"
    send_mail(
        subject="Reset your Crack GRE Vocab password",
        message=(
            "Use this link within 30 minutes to reset your password:\n\n"
            f"{reset_url}\n\n"
            "If you did not request this change, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[account.email],
    )


def deliver_password_reset_if_recoverable(email: str) -> None:
    """Deliver recovery when possible without exposing lookup or mail failures."""
    account = LearnerAccount.objects.filter(email=email, is_active=True).first()
    if account is None or not account.has_usable_password():
        return

    try:
        send_password_reset_email(account)
    except OSError:
        logger.exception(
            "Password reset delivery failed.",
            extra={"learner_account_id": account.pk},
        )


def reset_learner_password(*, uid: str, token: str, password: str) -> None:
    """Atomically accept one valid reset token and replace the password."""
    try:
        account_id = force_str(urlsafe_base64_decode(uid))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError) as exc:
        raise InvalidPasswordReset from exc

    with transaction.atomic():
        try:
            account = LearnerAccount.objects.select_for_update().get(pk=account_id)
        except (LearnerAccount.DoesNotExist, ValueError) as exc:
            raise InvalidPasswordReset from exc

        if not password_reset_token_generator.check_token(account, token):
            raise InvalidPasswordReset

        try:
            password_validation.validate_password(password, account)
        except DjangoValidationError as exc:
            raise PasswordResetValidationError(list(exc.messages)) from exc

        account.set_password(password)
        account.save(update_fields=("password",))
