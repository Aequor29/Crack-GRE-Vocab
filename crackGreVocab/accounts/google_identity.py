"""Verified Google identity resolution and explicit account linking."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from .managers import LearnerAccountManager
from .models import GoogleIdentity, LearnerAccount


class InvalidGoogleClaims(ValueError):
    """Indicate that required verified Google identity claims are unusable."""


class GoogleLinkAuthenticationFailed(ValueError):
    """Indicate that password ownership confirmation failed."""


class GoogleIdentityConflict(ValueError):
    """Prevent two distinct external identities from merging silently."""


class GoogleSignInAction(StrEnum):
    """Describe a Google sign-in that cannot establish a learner session."""

    REQUIRE_PASSWORD_CONFIRMATION = "require-password-confirmation"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class VerifiedGoogleClaims:
    """Carry the small verified claim subset used by the account domain."""

    subject: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class GoogleSignInSuccess:
    """Carry the learner required by every successful Google sign-in."""

    account: LearnerAccount


type GoogleSignInResolution = GoogleSignInSuccess | GoogleSignInAction


@dataclass(frozen=True, slots=True)
class PendingGoogleLink:
    """Carry only the validated identity needed for password confirmation."""

    subject: str
    email: str


def parse_verified_google_claims(userinfo: Any) -> VerifiedGoogleClaims:
    """Validate Authlib's cryptographically verified Google ID-token claims."""
    if not isinstance(userinfo, dict):
        raise InvalidGoogleClaims

    subject = userinfo.get("sub")
    email = userinfo.get("email")
    if (
        not isinstance(subject, str)
        or not subject
        or subject != subject.strip()
        or not subject.isascii()
        or len(subject) > 255
        or not isinstance(email, str)
        or userinfo.get("email_verified") is not True
    ):
        raise InvalidGoogleClaims

    try:
        validate_email(email)
        normalized_email = LearnerAccountManager.normalize_identity(email)
    except (ValidationError, ValueError) as exc:
        raise InvalidGoogleClaims from exc

    provider_name = userinfo.get("name")
    display_name = provider_name.strip() if isinstance(provider_name, str) else ""
    if not display_name:
        display_name = normalized_email.partition("@")[0]

    return VerifiedGoogleClaims(
        subject=subject,
        email=normalized_email,
        display_name=display_name[:80],
    )


@transaction.atomic
def resolve_google_sign_in(
    claims: VerifiedGoogleClaims,
) -> GoogleSignInResolution:
    """Resolve a returning subject, new account, or confirmed-link requirement."""
    linked_identity = (
        GoogleIdentity.objects.select_related("account")
        .filter(subject=claims.subject)
        .first()
    )
    if linked_identity is not None:
        if not linked_identity.account.is_active:
            return GoogleSignInAction.CONFLICT
        return GoogleSignInSuccess(linked_identity.account)

    account = (
        LearnerAccount.objects.select_for_update()
        .filter(email=claims.email)
        .first()
    )
    if account is not None:
        has_google_identity = GoogleIdentity.objects.filter(account=account).exists()
        if (
            has_google_identity
            or not account.has_usable_password()
            or not account.is_active
        ):
            return GoogleSignInAction.CONFLICT
        return GoogleSignInAction.REQUIRE_PASSWORD_CONFIRMATION

    account = LearnerAccount.objects.create_user(
        email=claims.email,
        display_name=claims.display_name,
        password=None,
    )
    try:
        GoogleIdentity.objects.create(
            account=account,
            subject=claims.subject,
            email_at_link=claims.email,
        )
    except IntegrityError as exc:
        raise GoogleIdentityConflict from exc
    return GoogleSignInSuccess(account)


@transaction.atomic
def confirm_google_link_with_password(
    pending_link: PendingGoogleLink,
    password: str,
) -> LearnerAccount:
    """Link one pending Google subject after password-account ownership proof."""
    account = (
        LearnerAccount.objects.select_for_update()
        .filter(email=pending_link.email)
        .first()
    )
    if account is None or not account.is_active or not account.has_usable_password():
        raise GoogleLinkAuthenticationFailed
    if not account.check_password(password):
        raise GoogleLinkAuthenticationFailed

    subject_identity = GoogleIdentity.objects.filter(
        subject=pending_link.subject
    ).first()
    if subject_identity is not None:
        if subject_identity.account_id == account.pk:
            return account
        raise GoogleIdentityConflict
    if GoogleIdentity.objects.filter(account=account).exists():
        raise GoogleIdentityConflict

    try:
        GoogleIdentity.objects.create(
            account=account,
            subject=pending_link.subject,
            email_at_link=pending_link.email,
        )
    except IntegrityError as exc:
        raise GoogleIdentityConflict from exc
    return account
