from django.urls import path

from .views import ActiveStudySessionView, StudySessionCollectionView

app_name = "study"

urlpatterns = [
    path("sessions/", StudySessionCollectionView.as_view(), name="session-list"),
    path(
        "sessions/active/",
        ActiveStudySessionView.as_view(),
        name="active-session",
    ),
]
