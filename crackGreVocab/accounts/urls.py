"""Routes for clean-rebuild learner account sessions."""

from django.urls import path

from .views import (
    CsrfTokenView,
    CurrentAccountView,
    SignInView,
    SignOutView,
    SignUpView,
)

app_name = "accounts"

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="csrf"),
    path("sign-up/", SignUpView.as_view(), name="sign-up"),
    path("sign-in/", SignInView.as_view(), name="sign-in"),
    path("sign-out/", SignOutView.as_view(), name="sign-out"),
    path("account/", CurrentAccountView.as_view(), name="account"),
]
