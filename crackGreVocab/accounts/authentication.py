"""Session authentication that also protects anonymous unsafe requests."""

from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request


class CsrfRejected(PermissionDenied):
    """Identify CSRF rejection without exposing framework prose as a contract."""

    default_detail = "CSRF validation failed."
    default_code = "csrf_failed"


class CsrfEnforcedSessionAuthentication(SessionAuthentication):
    """Require valid CSRF proof before any unsafe session API request."""

    def authenticate(self, request: Request):
        self.enforce_csrf(request)
        return super().authenticate(request)

    def enforce_csrf(self, request: Request) -> None:
        """Require Django's CSRF proof and raise a machine-identifiable error."""
        try:
            super().enforce_csrf(request)
        except PermissionDenied as exc:
            raise CsrfRejected from exc
