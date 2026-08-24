"""HTTP boundaries for Google sign-in and confirmed account linking."""

from urllib.parse import urlencode

from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.views import View
from drf_spectacular.utils import extend_schema
from joserfc.errors import JoseError
from requests import RequestException
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_409_CONFLICT,
)

from .google_identity import (
    GoogleIdentityConflict,
    GoogleLinkAuthenticationFailed,
    GoogleSignInAction,
    GoogleSignInSuccess,
    InvalidGoogleClaims,
    PendingGoogleLink,
    VerifiedGoogleClaims,
    confirm_google_link_with_password,
    parse_verified_google_claims,
    resolve_google_sign_in,
)
from .google_oauth import GoogleOAuthUnavailable, get_google_oauth_client
from .serializers import (
    ApiMessageSerializer,
    GoogleLinkConfirmSerializer,
    LearnerAccountSerializer,
)
from .views import CSRF_HEADER_PARAMETER, AccountApiView

PENDING_GOOGLE_LINK_SESSION_KEY = "pending_google_link"


def _google_frontend_redirect(path: str, status_name: str) -> HttpResponseRedirect:
    query = urlencode({"google": status_name})
    response = HttpResponseRedirect(
        f"{settings.GOOGLE_OAUTH_FRONTEND_ORIGIN}{path}?{query}"
    )
    response["Cache-Control"] = "no-store"
    return response


def _store_pending_google_link(
    request: HttpRequest,
    claims: VerifiedGoogleClaims,
) -> None:
    request.session[PENDING_GOOGLE_LINK_SESSION_KEY] = {
        "email": claims.email,
        "issued_at": int(timezone.now().timestamp()),
        "subject": claims.subject,
    }


def _clear_pending_google_link(request: HttpRequest) -> None:
    request.session.pop(PENDING_GOOGLE_LINK_SESSION_KEY, None)


def _read_pending_google_link(request: HttpRequest) -> PendingGoogleLink:
    pending = request.session.get(PENDING_GOOGLE_LINK_SESSION_KEY)
    if not isinstance(pending, dict):
        raise InvalidGoogleClaims

    issued_at = pending.get("issued_at")
    subject = pending.get("subject")
    email = pending.get("email")
    if (
        not isinstance(issued_at, int)
        or not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or not email
    ):
        _clear_pending_google_link(request)
        raise InvalidGoogleClaims
    age_seconds = int(timezone.now().timestamp()) - issued_at
    if age_seconds < 0 or age_seconds >= settings.GOOGLE_OAUTH_PENDING_LINK_MAX_AGE:
        _clear_pending_google_link(request)
        raise InvalidGoogleClaims

    return PendingGoogleLink(subject=subject, email=email)


class GoogleSignInStartView(View):
    """Redirect a learner to Google's state- and nonce-protected OIDC flow."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> HttpResponse:
        """Start Google authorization or return a safe unavailable state."""
        _clear_pending_google_link(request)
        try:
            google_client = get_google_oauth_client()
            response = google_client.authorize_redirect(
                request,
                settings.GOOGLE_OAUTH_CALLBACK_URL,
            )
            response["Cache-Control"] = "no-store"
            return response
        except GoogleOAuthUnavailable:
            return _google_frontend_redirect("/sign-in", "unavailable")
        except (JoseError, OAuthError, RequestException):
            return _google_frontend_redirect("/sign-in", "provider-error")


class GoogleSignInCallbackView(View):
    """Accept verified Google claims without persisting provider credentials."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest) -> HttpResponse:
        """Resolve verified callback claims into sign-in, linking, or conflict."""
        try:
            token = get_google_oauth_client().authorize_access_token(request)
            userinfo = token.get("userinfo") if isinstance(token, dict) else None
            claims = parse_verified_google_claims(userinfo)
            resolution = resolve_google_sign_in(claims)
        except OAuthError as exc:
            status_name = (
                "cancelled" if exc.error == "access_denied" else "provider-error"
            )
            return _google_frontend_redirect("/sign-in", status_name)
        except GoogleOAuthUnavailable:
            return _google_frontend_redirect("/sign-in", "unavailable")
        except (JoseError, RequestException):
            return _google_frontend_redirect("/sign-in", "provider-error")
        except (InvalidGoogleClaims, GoogleIdentityConflict):
            return _google_frontend_redirect("/sign-in", "provider-error")

        if isinstance(resolution, GoogleSignInSuccess):
            _clear_pending_google_link(request)
            login(
                request,
                resolution.account,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            return _google_frontend_redirect("/account", "connected")

        if resolution is GoogleSignInAction.CONFLICT:
            _clear_pending_google_link(request)
            return _google_frontend_redirect("/sign-in", "conflict")

        _store_pending_google_link(request, claims)
        return _google_frontend_redirect("/sign-in", "link-required")


class GoogleLinkConfirmView(AccountApiView):
    """Link a pending Google subject after explicit password confirmation."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_google_link_confirm_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=GoogleLinkConfirmSerializer,
        responses={
            200: LearnerAccountSerializer,
            400: ApiMessageSerializer,
            401: ApiMessageSerializer,
            403: ApiMessageSerializer,
            409: ApiMessageSerializer,
            415: ApiMessageSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        """Confirm the pending link and establish the learner session."""
        serializer = GoogleLinkConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            pending_link = _read_pending_google_link(request._request)
            account = confirm_google_link_with_password(
                pending_link,
                serializer.validated_data["password"],
            )
        except InvalidGoogleClaims:
            return Response(
                {"detail": "Start Google sign-in again before linking."},
                status=HTTP_400_BAD_REQUEST,
            )
        except GoogleLinkAuthenticationFailed:
            return Response(
                {"detail": "Enter the current password for this account."},
                status=HTTP_401_UNAUTHORIZED,
            )
        except GoogleIdentityConflict:
            _clear_pending_google_link(request._request)
            return Response(
                {"detail": "This Google identity cannot be linked to that account."},
                status=HTTP_409_CONFLICT,
            )

        _clear_pending_google_link(request._request)
        login(
            request._request,
            account,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return Response(
            LearnerAccountSerializer(account).data,
            status=HTTP_200_OK,
        )


class GoogleLinkCancelView(AccountApiView):
    """Discard one pending Google link without changing account data."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_google_link_cancel_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=None,
        responses={204: None, 403: ApiMessageSerializer},
    )
    def post(self, request: Request) -> Response:
        """Cancel the pending link without touching either identity."""
        _clear_pending_google_link(request._request)
        return Response(status=HTTP_204_NO_CONTENT)
