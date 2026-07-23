"""Characterization tests for the JWT flow pending the session-auth migration."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import UserCreate


class LegacyJwtContractTests(SimpleTestCase):
    def test_access_and_refresh_routes_remain_available(self):
        self.assertIs(resolve("/vocab/token/").func.view_class, TokenObtainPairView)
        self.assertIs(
            resolve("/vocab/token/refresh/").func.view_class,
            TokenRefreshView,
        )

    @patch("vocab_backend.views.RefreshToken.for_user")
    @patch("vocab_backend.views.User.objects")
    def test_signup_returns_the_legacy_token_pair(self, user_objects, for_user):
        user_objects.filter.return_value.exists.return_value = False
        user_objects.create_user.return_value = SimpleNamespace(
            id=7,
            username="learner",
        )
        refresh = MagicMock()
        refresh.__str__.return_value = "refresh-token"
        refresh.access_token.__str__.return_value = "access-token"
        for_user.return_value = refresh
        request = APIRequestFactory().post(
            "/vocab/signup/",
            {
                "email": "learner@example.com",
                "password": "test-password",
                "username": "learner",
            },
            format="json",
        )

        response = UserCreate.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["refresh"], "refresh-token")
        self.assertEqual(response.data["access"], "access-token")
