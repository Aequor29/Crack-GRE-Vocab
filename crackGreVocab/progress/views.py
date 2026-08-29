"""Authenticated Learning Progress HTTP endpoint."""

from django.db import InterfaceError, OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    ValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_409_CONFLICT,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from rest_framework.views import APIView

from .serializers import (
    LearningInsightsSerializer,
    LearningProgressSummarySerializer,
    ProgressErrorSerializer,
    ProgressTimezoneQuerySerializer,
)
from .services import (
    ProgressUnavailable,
    build_learning_insights,
    build_learning_progress_summary,
)


class _ProgressAPIView(APIView):
    http_method_names = ["get", "head", "options"]
    permission_classes = (IsAuthenticated,)
    renderer_classes = (JSONRenderer,)

    def handle_exception(self, exc):
        """Add stable codes to framework-owned Progress API failures."""
        response = super().handle_exception(exc)
        if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            code = "authentication_required"
        elif isinstance(exc, ValidationError):
            code = "validation_error"
        else:
            return response
        response.data = {"code": code, **response.data}
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        """Prevent browser or intermediary caching of learner progress."""
        finalized = super().finalize_response(request, response, *args, **kwargs)
        finalized["Cache-Control"] = "no-store"
        return finalized


class LearningProgressSummaryView(_ProgressAPIView):
    """Return current, read-only Learning Progress for one learner."""

    @extend_schema(
        operation_id="progress_summary_retrieve",
        parameters=[ProgressTimezoneQuerySerializer],
        responses={
            200: LearningProgressSummarySerializer,
            400: ProgressErrorSerializer,
            403: ProgressErrorSerializer,
            409: ProgressErrorSerializer,
            503: ProgressErrorSerializer,
        },
    )
    def get(self, request) -> Response:
        """Build the snapshot using the learner's requested IANA timezone."""
        query = ProgressTimezoneQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            summary = build_learning_progress_summary(
                learner=request.user,
                timezone_name=query.validated_data["timezone"],
            )
        except ProgressUnavailable as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=HTTP_409_CONFLICT,
            )
        except InterfaceError, OperationalError:
            return Response(
                {
                    "code": "progress_temporarily_unavailable",
                    "detail": "Learning Progress could not be loaded.",
                    "retryable": True,
                },
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            LearningProgressSummarySerializer(summary).data,
            status=HTTP_200_OK,
        )

class LearningInsightsView(_ProgressAPIView):
    """Return historical recall and consistency insights for one learner."""

    @extend_schema(
        operation_id="progress_insights_retrieve",
        parameters=[ProgressTimezoneQuerySerializer],
        responses={
            200: LearningInsightsSerializer,
            400: ProgressErrorSerializer,
            403: ProgressErrorSerializer,
            409: ProgressErrorSerializer,
            503: ProgressErrorSerializer,
        },
    )
    def get(self, request) -> Response:
        """Build insights using the learner's requested IANA timezone."""
        query = ProgressTimezoneQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            insights = build_learning_insights(
                learner=request.user,
                timezone_name=query.validated_data["timezone"],
            )
        except ProgressUnavailable as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=HTTP_409_CONFLICT,
            )
        except (InterfaceError, OperationalError):
            return Response(
                {
                    "code": "progress_temporarily_unavailable",
                    "detail": "Learning insights could not be loaded.",
                    "retryable": True,
                },
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            LearningInsightsSerializer(insights).data,
            status=HTTP_200_OK,
        )
