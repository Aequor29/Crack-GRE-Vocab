"""Google OpenID Connect client configuration for learner authentication."""

from authlib.integrations.django_client import OAuth
from django.conf import settings

GOOGLE_OPENID_CONFIGURATION_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)


class GoogleOAuthUnavailable(RuntimeError):
    """Indicate that fresh Google client credentials are not configured."""


def get_google_oauth_client():
    """Return a Google OIDC client that verifies state, nonce, and ID tokens."""
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise GoogleOAuthUnavailable

    oauth_registry = OAuth()
    return oauth_registry.register(
        name="google",
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        server_metadata_url=GOOGLE_OPENID_CONFIGURATION_URL,
        client_kwargs={
            "code_challenge_method": "S256",
            "scope": "openid email profile",
        },
    )
