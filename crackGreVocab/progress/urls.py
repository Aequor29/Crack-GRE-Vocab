from django.urls import path

from .views import LearningProgressSummaryView

app_name = "progress"

urlpatterns = [
    path("summary/", LearningProgressSummaryView.as_view(), name="summary"),
]
