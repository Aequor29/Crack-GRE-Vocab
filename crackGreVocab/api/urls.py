"""Routes for the foundational API service document."""

from django.urls import path

from .views import ServiceIndexView

app_name = "api"

urlpatterns = [
    path("", ServiceIndexView.as_view(), name="service-index"),
]
