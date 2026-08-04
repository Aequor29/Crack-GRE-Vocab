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
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from rest_framework.views import APIView

from .serializers import (
    ApiErrorSerializer,
    AuthValidationErrorSerializer,
    CsrfTokenSerializer,
    LearnerAccountSerializer,
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
            403: ApiErrorSerializer,
            415: ApiErrorSerializer,
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
            401: ApiErrorSerializer,
            403: ApiErrorSerializer,
            415: ApiErrorSerializer,
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


class SignOutView(AccountApiView):
    """End the current session without exposing whether it existed."""

    permission_classes = (AllowAny,)
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="auth_sign_out_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=None,
        responses={204: None, 403: ApiErrorSerializer},
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
            403: ApiErrorSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        return Response(LearnerAccountSerializer(request.user).data)
