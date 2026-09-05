"""Service identity, readiness, and API schema routes."""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from .views import ReadinessView, ServiceIndexView

app_name = "api"

urlpatterns = [
    path("", ServiceIndexView.as_view(), name="service-index"),
    path("readiness/", ReadinessView.as_view(), name="readiness"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]
