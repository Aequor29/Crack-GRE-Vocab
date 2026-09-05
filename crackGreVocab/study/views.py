"""Authenticated Study Session planning and resume endpoints."""

from accounts.authentication import CsrfRejected
from api.schema import CSRF_HEADER_PARAMETER
from django.db import InterfaceError, OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    ParseError,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from rest_framework.views import APIView

from .serializers import (
    CreateStudySessionSerializer,
    RecordRecallAnswerSerializer,
    StudyAnswerResponseSerializer,
    StudyPlanningErrorSerializer,
    StudySessionSerializer,
    StudyValidationErrorSerializer,
)
from .services import (
    StudyAnswerConflict,
    StudyAnswerNotFound,
    StudyPlanningUnavailable,
    plan_study_session,
    record_recall_answer,
    resume_active_study_session,
)


def _database_temporarily_unavailable(detail: str) -> Response:
    """Return the stable response for an expected transient database failure."""
    return Response(
        {
            "code": "study_temporarily_unavailable",
            "detail": detail,
            "retryable": True,
        },
        status=HTTP_503_SERVICE_UNAVAILABLE,
    )


class StudyApiView(APIView):
    """Base class for authenticated, JSON-only, non-cacheable Study APIs."""

    parser_classes = (JSONParser,)
    renderer_classes = (JSONRenderer,)
    permission_classes = (IsAuthenticated,)

    def handle_exception(self, exc):
        """Add stable codes to framework-owned Study API failures."""
        response = super().handle_exception(exc)
        if isinstance(exc, CsrfRejected):
            code = "csrf_failed"
        elif isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            code = "authentication_required"
        elif isinstance(exc, ValidationError):
            code = "validation_error"
        elif isinstance(exc, ParseError):
            code = "invalid_json"
        elif isinstance(exc, UnsupportedMediaType):
            code = "unsupported_media_type"
        else:
            return response
        response.data = {"code": code, **response.data}
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        """Attach no-store caching to every Study API response."""
        finalized = super().finalize_response(request, response, *args, **kwargs)
        finalized["Cache-Control"] = "no-store"
        return finalized


class StudySessionCollectionView(StudyApiView):
    """Create a new Study Session or resume the learner's active session."""

    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="study_session_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=CreateStudySessionSerializer,
        responses={
            200: StudySessionSerializer,
            201: StudySessionSerializer,
            400: StudyValidationErrorSerializer,
            403: StudyPlanningErrorSerializer,
            409: StudyPlanningErrorSerializer,
            415: StudyPlanningErrorSerializer,
            503: StudyPlanningErrorSerializer,
        },
    )
    def post(self, request) -> Response:
        """Plan a bounded Study Session for the authenticated learner."""
        serializer = CreateStudySessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            planned = plan_study_session(
                learner=request.user,
                new_word_target=serializer.validated_data["new_word_target"],
                timezone_name=serializer.validated_data["timezone"],
            )
        except StudyPlanningUnavailable as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=HTTP_409_CONFLICT,
            )
        except InterfaceError, OperationalError:
            return _database_temporarily_unavailable(
                "The Study Session could not be persisted."
            )

        return Response(
            StudySessionSerializer(planned.session).data,
            status=HTTP_201_CREATED if planned.created else HTTP_200_OK,
        )


class ActiveStudySessionView(StudyApiView):
    """Expose the authenticated learner's resumable Study Session."""

    http_method_names = ["get", "head", "options"]

    @extend_schema(
        operation_id="study_session_active_retrieve",
        responses={
            200: StudySessionSerializer,
            403: StudyPlanningErrorSerializer,
            404: StudyPlanningErrorSerializer,
            503: StudyPlanningErrorSerializer,
        },
    )
    def get(self, request) -> Response:
        """Return the active Study Session or a not-found response."""
        try:
            session = resume_active_study_session(learner=request.user)
        except InterfaceError, OperationalError:
            return _database_temporarily_unavailable(
                "The Study Session could not be loaded."
            )
        if session is None:
            return Response(
                {
                    "code": "study_session_not_found",
                    "detail": "No active Study Session exists.",
                },
                status=HTTP_404_NOT_FOUND,
            )
        return Response(StudySessionSerializer(session).data, status=HTTP_200_OK)


class StudySessionAnswerView(StudyApiView):
    """Accept one idempotent self-grade for the current study item."""

    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="study_session_answer_create",
        parameters=[CSRF_HEADER_PARAMETER],
        request=RecordRecallAnswerSerializer,
        responses={
            200: StudyAnswerResponseSerializer,
            201: StudyAnswerResponseSerializer,
            400: StudyValidationErrorSerializer,
            403: StudyPlanningErrorSerializer,
            404: StudyPlanningErrorSerializer,
            409: StudyPlanningErrorSerializer,
            415: StudyPlanningErrorSerializer,
            503: StudyPlanningErrorSerializer,
        },
    )
    def post(self, request, session_id, item_id) -> Response:
        """Persist a recall answer and return authoritative study progress."""
        serializer = RecordRecallAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recorded = record_recall_answer(
                learner=request.user,
                session_id=session_id,
                item_id=item_id,
                request_id=serializer.validated_data["client_request_id"],
                rating=serializer.validated_data["rating"],
            )
        except StudyAnswerNotFound as exc:
            return Response(
                {"code": "study_item_not_found", "detail": str(exc)},
                status=HTTP_404_NOT_FOUND,
            )
        except StudyAnswerConflict as exc:
            payload: dict[str, object] = {"code": exc.code, "detail": exc.detail}
            if exc.current_item_id is not None:
                payload["current_item_id"] = exc.current_item_id
            return Response(payload, status=HTTP_409_CONFLICT)
        except InterfaceError, OperationalError:
            return _database_temporarily_unavailable(
                "The Recall Outcome could not be persisted."
            )

        response = StudyAnswerResponseSerializer(
            {
                "answer": recorded.answer,
                "outcome": recorded.outcome,
                "session": recorded.session,
                "replayed": not recorded.created,
            }
        )
        return Response(
            response.data,
            status=HTTP_201_CREATED if recorded.created else HTTP_200_OK,
        )
