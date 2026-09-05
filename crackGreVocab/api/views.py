"""API identification and database readiness endpoints."""

from django.db import Error, connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView

from .serializers import ReadinessSerializer, ServiceIndexSerializer


class ServiceIndexView(APIView):
    """Return the API service identity."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer,)
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        operation_id="service_index_retrieve",
        responses={200: ServiceIndexSerializer},
    )
    def get(self, request: Request) -> Response:
        """Return the stable, non-readiness service document."""
        return Response({"service": "crack-gre-vocab-api"})


class ReadinessView(APIView):
    """Report whether the local application can reach PostgreSQL."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer,)
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        operation_id="readiness_retrieve",
        responses={
            200: ReadinessSerializer,
            503: ReadinessSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        """Return the database readiness status."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Error:
            response = Response(
                {"status": "unavailable", "database": "unavailable"},
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )
        else:
            response = Response({"status": "ready", "database": "available"})

        response["Cache-Control"] = "no-store"
        return response
