"""Django-session endpoints for clean-rebuild learner accounts."""

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from rest_framework.views import APIView

from .password_recovery import (
    InvalidPasswordReset,
    PasswordResetValidationError,
    deliver_password_reset_if_recoverable,
    reset_learner_password,
)
from .serializers import (
    ApiMessageSerializer,
    AuthValidationErrorSerializer,
    CsrfTokenSerializer,
    LearnerAccountSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetStartSerializer,
    SignInSerializer,
    SignUpSerializer,
)

CSRF_HEADER_PARAMETER = OpenApiParameter(
    name="X-CSRFToken",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description="Masked token from GET /api/auth/csrf/.",
)


class AccountApiView(APIView):
    """Use JSON only and avoid cached identity/session responses."""

    parser_classes = (JSONParser,)
    renderer_classes = (JSONRenderer,)

    def finalize_response(self, request: Request, response: Response, *args, **kwargs):
        finalized = super().finalize_response(request, response, *args, **kwargs)
        finalized["Cache-Control"] = "no-store"
        return finalized


class CsrfTokenView(AccountApiView):
    """Issue the masked token required by session-backed mutations."""

    permission_classes = (AllowAny,)
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        operation_id="auth_csrf_retrieve",
        responses={200: CsrfTokenSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request._request)})


class SignUpView(AccountApiView):
    """Create and immediately sign in a new learner."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_sign_up_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=SignUpSerializer,
        responses={
            201: LearnerAccountSerializer,
            400: AuthValidationErrorSerializer,
            403: ApiMessageSerializer,
            415: ApiMessageSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = SignUpSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        account = serializer.save()
        login(
            request._request,
            account,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return Response(
            LearnerAccountSerializer(account).data,
            status=HTTP_201_CREATED,
        )


class SignInView(AccountApiView):
    """Create a Django session from an email and password."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_sign_in_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=SignInSerializer,
        responses={
            200: LearnerAccountSerializer,
            400: AuthValidationErrorSerializer,
            401: ApiMessageSerializer,
            403: ApiMessageSerializer,
            415: ApiMessageSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = SignInSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        account = authenticate(
            request=request._request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if account is None:
            return Response(
                {"detail": "Email or password is incorrect."},
                status=HTTP_401_UNAUTHORIZED,
            )

        login(request._request, account)
        return Response(LearnerAccountSerializer(account).data, status=HTTP_200_OK)


class PasswordResetRequestView(AccountApiView):
    """Send recovery instructions without revealing account existence."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_password_reset_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=PasswordResetStartSerializer,
        responses={
            202: ApiMessageSerializer,
            400: AuthValidationErrorSerializer,
            403: ApiMessageSerializer,
            415: ApiMessageSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        deliver_password_reset_if_recoverable(serializer.validated_data["email"])

        return Response(
            {
                "detail": (
                    "If an account can be recovered, a password reset link has "
                    "been sent."
                )
            },
            status=HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(AccountApiView):
    """Replace a password after validating one short-lived reset token."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_password_reset_confirm_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=PasswordResetConfirmSerializer,
        responses={
            200: ApiMessageSerializer,
            400: AuthValidationErrorSerializer,
            403: ApiMessageSerializer,
            415: ApiMessageSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        try:
            reset_learner_password(**serializer.validated_data)
        except PasswordResetValidationError as exc:
            return Response(
                {"password": exc.messages},
                status=HTTP_400_BAD_REQUEST,
            )
        except InvalidPasswordReset:
            return Response(
                {"detail": "This password reset link is invalid or has expired."},
                status=HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Password reset complete. Sign in with your new password."},
            status=HTTP_200_OK,
        )


class SignOutView(AccountApiView):
    """End the current session without exposing whether it existed."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_sign_out_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=None,
        responses={204: None, 403: ApiMessageSerializer},
    )
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=HTTP_204_NO_CONTENT)


class CurrentAccountView(AccountApiView):
    """Return the learner represented by the current server session."""

    permission_classes = (IsAuthenticated,)
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        operation_id="auth_account_retrieve",
        responses={
            200: LearnerAccountSerializer,
            403: ApiMessageSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        return Response(LearnerAccountSerializer(request.user).data)
