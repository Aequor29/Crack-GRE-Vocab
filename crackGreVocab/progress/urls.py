from django.urls import path

from .views import LearningInsightsView, LearningProgressSummaryView

app_name = "progress"

urlpatterns = [
    path("summary/", LearningProgressSummaryView.as_view(), name="summary"),
    path("insights/", LearningInsightsView.as_view(), name="insights"),
]
