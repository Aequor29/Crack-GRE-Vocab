from django.urls import path

from .views import (
    ActiveStudySessionView,
    StudySessionAnswerView,
    StudySessionCollectionView,
)

app_name = "study"

urlpatterns = [
    path("sessions/", StudySessionCollectionView.as_view(), name="session-list"),
    path(
        "sessions/active/",
        ActiveStudySessionView.as_view(),
        name="active-session",
    ),
    path(
        "sessions/<uuid:session_id>/items/<uuid:item_id>/answer/",
        StudySessionAnswerView.as_view(),
        name="session-answer",
    ),
]
