"""Read-only account queries for federated identity orchestration."""

from .models import GoogleIdentity, LearnerAccount


def get_google_identity_by_subject(subject: str) -> GoogleIdentity | None:
    """Return a Google identity and learner for one stable provider subject."""
    return (
        GoogleIdentity.objects.select_related("account")
        .filter(subject=subject)
        .first()
    )


def learner_account_has_google_identity(account: LearnerAccount) -> bool:
    """Return whether the learner already owns a Google sign-in identity."""
    return GoogleIdentity.objects.filter(account=account).exists()
