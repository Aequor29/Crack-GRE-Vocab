"""Administrative configuration for learner accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import LearnerAccountChangeForm, LearnerAccountCreationForm
from .models import LearnerAccount


@admin.register(LearnerAccount)
class LearnerAccountAdmin(UserAdmin):
    """Expose only clean-rebuild learner identity fields in admin."""

    add_form = LearnerAccountCreationForm
    form = LearnerAccountChangeForm
    model = LearnerAccount
    ordering = ("email",)
    list_display = ("email", "display_name", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "display_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Learner", {"fields": ("display_name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")
