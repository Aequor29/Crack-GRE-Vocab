"""URL configuration for the clean Django foundation."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("accounts.urls")),
    path("api/study/", include("study.urls")),
    path("api/", include("api.urls")),
    path("admin/", admin.site.urls),
]
