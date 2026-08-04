"""Foundational API views that do not depend on product data."""

from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class ServiceIndexView(APIView):
    """Identify the local API process without claiming database readiness."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    renderer_classes = (JSONRenderer,)
    http_method_names = ["get", "head", "options"]

    def get(self, request: Request) -> Response:
        """Return the stable, non-readiness service document."""
        return Response({"service": "crack-gre-vocab-api"})
