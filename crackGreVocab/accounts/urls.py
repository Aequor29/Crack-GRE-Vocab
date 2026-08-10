"""Routes for clean-rebuild learner account sessions."""

from django.urls import path

from .google_views import (
    GoogleLinkCancelView,
    GoogleLinkConfirmView,
    GoogleSignInCallbackView,
    GoogleSignInStartView,
)
from .views import (
    CsrfTokenView,
    CurrentAccountView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    SignInView,
    SignOutView,
    SignUpView,
)

app_name = "accounts"

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("sign-up/", SignUpView.as_view(), name="sign-up"),
    path("sign-in/", SignInView.as_view(), name="sign-in"),
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("google/start/", GoogleSignInStartView.as_view(), name="google-start"),
    path(
        "google/callback/",
        GoogleSignInCallbackView.as_view(),
        name="google-callback",
    ),
    path(
        "google/link/confirm/",
        GoogleLinkConfirmView.as_view(),
        name="google-link-confirm",
    ),
    path(
        "google/link/cancel/",
        GoogleLinkCancelView.as_view(),
        name="google-link-cancel",
    ),
    path("sign-out/", SignOutView.as_view(), name="sign-out"),
    path("account/", CurrentAccountView.as_view(), name="account"),
]
