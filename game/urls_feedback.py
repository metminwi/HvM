from django.urls import path
from .views_feedback import FeedbackCreateView

urlpatterns = [
    path("", FeedbackCreateView.as_view(), name="feedback-create"),
]
