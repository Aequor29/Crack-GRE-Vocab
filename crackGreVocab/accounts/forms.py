"""Admin forms for the email-based learner account."""

from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import LearnerAccount


class LearnerAccountCreationForm(UserCreationForm):
    """Create a learner account through Django admin."""

    class Meta(UserCreationForm.Meta):
        model = LearnerAccount
        fields = ("email", "display_name")


class LearnerAccountChangeForm(UserChangeForm):
    """Edit a learner account through Django admin."""

    class Meta(UserChangeForm.Meta):
        model = LearnerAccount
        fields = ("email", "display_name", "is_active", "is_staff")
