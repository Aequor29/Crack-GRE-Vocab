"""Verified Google identity resolution and explicit account linking."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from .managers import LearnerAccountManager
from .models import LearnerAccount
from .persistence import (
    create_google_identity,
    create_google_only_learner,
    lock_learner_account_by_email,
)
from .selectors import (
    get_google_identity_by_subject,
    learner_account_has_google_identity,
)


class InvalidGoogleClaims(ValueError):
    """Indicate that required verified Google identity claims are unusable."""


class GoogleLinkAuthenticationFailed(ValueError):
    """Indicate that password ownership confirmation failed."""


class GoogleIdentityConflict(ValueError):
    """Prevent two distinct external identities from merging silently."""


class GoogleSignInAction(StrEnum):
    """Describe the safe next action for one verified Google identity."""

    SIGN_IN = "sign-in"
    REQUIRE_PASSWORD_CONFIRMATION = "require-password-confirmation"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class VerifiedGoogleClaims:
    """Carry the small verified claim subset used by the account domain."""

    subject: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class GoogleSignInResolution:
    """Return either a signed-in account or an explicit next action."""

    action: GoogleSignInAction
    account: LearnerAccount | None = None


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
    linked_identity = get_google_identity_by_subject(claims.subject)
    if linked_identity is not None:
        if not linked_identity.account.is_active:
            return GoogleSignInResolution(GoogleSignInAction.CONFLICT)
        return GoogleSignInResolution(
            GoogleSignInAction.SIGN_IN,
            linked_identity.account,
        )

    account = lock_learner_account_by_email(claims.email)
    if account is not None:
        has_google_identity = learner_account_has_google_identity(account)
        if (
            has_google_identity
            or not account.has_usable_password()
            or not account.is_active
        ):
            return GoogleSignInResolution(GoogleSignInAction.CONFLICT)
        return GoogleSignInResolution(
            GoogleSignInAction.REQUIRE_PASSWORD_CONFIRMATION
        )

    account = create_google_only_learner(
        email=claims.email,
        display_name=claims.display_name,
    )
    try:
        create_google_identity(
            account=account,
            subject=claims.subject,
            verified_email=claims.email,
        )
    except IntegrityError as exc:
        raise GoogleIdentityConflict from exc
    return GoogleSignInResolution(GoogleSignInAction.SIGN_IN, account)


@transaction.atomic
def confirm_google_link_with_password(
    claims: VerifiedGoogleClaims,
    password: str,
) -> LearnerAccount:
    """Link one pending Google subject after password-account ownership proof."""
    account = lock_learner_account_by_email(claims.email)
    if account is None or not account.is_active or not account.has_usable_password():
        raise GoogleLinkAuthenticationFailed
    if not account.check_password(password):
        raise GoogleLinkAuthenticationFailed

    subject_identity = get_google_identity_by_subject(claims.subject)
    if subject_identity is not None:
        if subject_identity.account_id == account.pk:
            return account
        raise GoogleIdentityConflict
    if learner_account_has_google_identity(account):
        raise GoogleIdentityConflict

    try:
        create_google_identity(
            account=account,
            subject=claims.subject,
            verified_email=claims.email,
        )
    except IntegrityError as exc:
        raise GoogleIdentityConflict from exc
    return account
