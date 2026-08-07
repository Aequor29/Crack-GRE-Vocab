"""OpenAPI description for the stricter session authentication class."""

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CsrfEnforcedSessionScheme(OpenApiAuthenticationExtension):
    """Publish the normal Django session cookie authentication scheme."""

    target_class = "accounts.authentication.CsrfEnforcedSessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
