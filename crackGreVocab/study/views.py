"""Authenticated Study Session planning and resume endpoints."""

from django.db import DatabaseError
from drf_spectacular.utils import extend_schema
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

from .selectors import get_active_session
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
    StudyAnswerUnavailable,
    StudyPlanningUnavailable,
    plan_study_session,
    record_recall_answer,
)


class StudyApiView(APIView):
    parser_classes = (JSONParser,)
    renderer_classes = (JSONRenderer,)
    permission_classes = (IsAuthenticated,)

    def finalize_response(self, request, response, *args, **kwargs):
        finalized = super().finalize_response(request, response, *args, **kwargs)
        finalized["Cache-Control"] = "no-store"
        return finalized


class StudySessionCollectionView(StudyApiView):
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="study_session_create",
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
        serializer = CreateStudySessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            planned = plan_study_session(
                learner=request.user,
                new_word_target=serializer.validated_data["new_word_target"],
            )
        except StudyPlanningUnavailable as exc:
            return Response({"detail": str(exc)}, status=HTTP_409_CONFLICT)
        except DatabaseError:
            return Response(
                {"detail": "The Study Session could not be persisted."},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            StudySessionSerializer(planned.session).data,
            status=HTTP_201_CREATED if planned.created else HTTP_200_OK,
        )


class ActiveStudySessionView(StudyApiView):
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        operation_id="study_session_active_retrieve",
        responses={
            200: StudySessionSerializer,
            403: StudyPlanningErrorSerializer,
            404: StudyPlanningErrorSerializer,
        },
    )
    def get(self, request) -> Response:
        session = get_active_session(learner=request.user)
        if session is None:
            return Response(
                {"detail": "No active Study Session exists."},
                status=HTTP_404_NOT_FOUND,
            )
        return Response(StudySessionSerializer(session).data, status=HTTP_200_OK)


class StudySessionAnswerView(StudyApiView):
    http_method_names = ["post", "options"]

    @extend_schema(
        operation_id="study_session_answer_create",
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
        except StudyAnswerUnavailable:
            return Response(
                {
                    "code": "study_temporarily_unavailable",
                    "detail": "The Recall Outcome could not be scheduled safely.",
                    "retryable": True,
                },
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DatabaseError:
            return Response(
                {
                    "code": "study_temporarily_unavailable",
                    "detail": "The Recall Outcome could not be persisted.",
                    "retryable": True,
                },
                status=HTTP_503_SERVICE_UNAVAILABLE,
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
