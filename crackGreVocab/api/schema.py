"""Shared OpenAPI declarations for session-authenticated endpoints."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

CSRF_HEADER_PARAMETER = OpenApiParameter(
    name="X-CSRFToken",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=True,
    description="Masked token from GET /api/auth/csrf/.",
)
