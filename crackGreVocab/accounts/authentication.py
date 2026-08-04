"""Session authentication that also protects anonymous unsafe requests."""

from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


class CsrfEnforcedSessionAuthentication(SessionAuthentication):
    """Require valid CSRF proof before any unsafe session API request."""

    def authenticate(self, request: Request):
        self.enforce_csrf(request)
        return super().authenticate(request)
