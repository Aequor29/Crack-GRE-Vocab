"""Django settings for Crack GRE Vocab."""

from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from .config import (
    env_bool,
    env_list,
    env_string,
    http_url,
    optional_env_string,
    postgres_database_url,
    required_env,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

DEBUG = env_bool("DEBUG", default=False)
SECRET_KEY = required_env("SECRET_KEY")

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    default=("localhost", "127.0.0.1") if DEBUG else (),
)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must contain at least one hostname when DEBUG is false."
    )

try:
    database = dj_database_url.parse(
        postgres_database_url(),
        conn_max_age=0 if DEBUG else 60,
        conn_health_checks=True,
    )
except ValueError as exc:
    raise ImproperlyConfigured(
        "DATABASE_URL must be a valid PostgreSQL URL."
    ) from exc

DATABASES = {"default": database}

INSTALLED_APPS = [
    "accounts.apps.AccountsConfig",
    "api.apps.ApiConfig",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "vocabulary.apps.VocabularyConfig",
    "study.apps.StudyConfig",
    "progress.apps.ProgressConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "crackGreVocab.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "crackGreVocab.wsgi.application"
ASGI_APPLICATION = "crackGreVocab.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "accounts.LearnerAccount"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.CsrfEnforcedSessionAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Crack GRE Vocab API",
    "DESCRIPTION": "Local API contract for the Milestone 1 cold rebuild.",
    "VERSION": "0.1.0",
    "OAS_VERSION": "3.0.3",
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    default=(
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    if DEBUG
    else (),
)
CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=CORS_ALLOWED_ORIGINS if DEBUG else (),
)

PASSWORD_RESET_TIMEOUT = 30 * 60
PASSWORD_RESET_FRONTEND_URL = http_url(
    "PASSWORD_RESET_FRONTEND_URL",
    default=(
        "http://localhost:3000/reset-password/confirm" if DEBUG else None
    ),
)
EMAIL_BACKEND = env_string(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend" if DEBUG else None
    ),
)
DEFAULT_FROM_EMAIL = env_string(
    "DEFAULT_FROM_EMAIL",
    default=("Crack GRE Vocab <no-reply@localhost>" if DEBUG else None),
)

GOOGLE_OAUTH_CLIENT_ID = optional_env_string("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = optional_env_string("GOOGLE_OAUTH_CLIENT_SECRET")
if bool(GOOGLE_OAUTH_CLIENT_ID) != bool(GOOGLE_OAUTH_CLIENT_SECRET):
    raise ImproperlyConfigured(
        "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be configured "
        "together."
    )
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID)
if not DEBUG and not GOOGLE_OAUTH_ENABLED:
    raise ImproperlyConfigured(
        "Google OAuth credentials must be configured when DEBUG is false."
    )
if GOOGLE_OAUTH_ENABLED:
    GOOGLE_OAUTH_CALLBACK_URL = http_url(
        "GOOGLE_OAUTH_CALLBACK_URL",
        default=(
            "http://localhost:8000/api/auth/google/callback/" if DEBUG else None
        ),
    )
    GOOGLE_OAUTH_FRONTEND_ORIGIN = http_url(
        "GOOGLE_OAUTH_FRONTEND_ORIGIN",
        default="http://localhost:3000" if DEBUG else None,
    )
    if not DEBUG and (
        not GOOGLE_OAUTH_CALLBACK_URL.startswith("https://")
        or not GOOGLE_OAUTH_FRONTEND_ORIGIN.startswith("https://")
    ):
        raise ImproperlyConfigured(
            "Hosted Google OAuth callback and frontend URLs must use HTTPS."
        )
else:
    GOOGLE_OAUTH_CALLBACK_URL = ""
    GOOGLE_OAUTH_FRONTEND_ORIGIN = http_url(
        "GOOGLE_OAUTH_FRONTEND_ORIGIN",
        default="http://localhost:3000",
    )
GOOGLE_OAUTH_PENDING_LINK_MAX_AGE = 10 * 60

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env_bool("TRUST_X_FORWARDED_PROTO", default=False)
    else None
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 0 if DEBUG else 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
