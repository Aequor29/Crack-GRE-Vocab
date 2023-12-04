# vocab/urls.py

from django.urls import path
from .views import SessionCreateView,NewWordsView, WordResponseView, UserProgressView, ReviewWordsView , UpdateProgressView, UserProfileView
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('words/new', NewWordsView.as_view(), name='new-words'),
    path('words/response', WordResponseView.as_view(), name='word-response'),
    path('user/progress', UserProgressView.as_view(), name='user-progress'),
    path('review-words/', ReviewWordsView.as_view(), name='review_words'),
    path('update-progress', UpdateProgressView.as_view(), name='update_progress'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('session/create', SessionCreateView.as_view(), name='session-create')
    # Additional app-specific URL patterns...
]