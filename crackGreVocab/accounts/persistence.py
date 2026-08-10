"""Database writes and row locks for learner identity workflows."""

from .models import GoogleIdentity, LearnerAccount


def lock_learner_account_by_email(email: str) -> LearnerAccount | None:
    """Lock and return the learner with the canonical email, when present."""
    return LearnerAccount.objects.select_for_update().filter(email=email).first()


def create_google_only_learner(
    *,
    email: str,
    display_name: str,
) -> LearnerAccount:
    """Persist a learner whose initial usable sign-in method is Google."""
    return LearnerAccount.objects.create_user(
        email=email,
        display_name=display_name,
        password=None,
    )


def create_google_identity(
    *,
    account: LearnerAccount,
    subject: str,
    verified_email: str,
) -> GoogleIdentity:
    """Persist one stable Google subject for one learner account."""
    return GoogleIdentity.objects.create(
        account=account,
        subject=subject,
        email_at_link=verified_email,
    )
