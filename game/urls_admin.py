from django.urls import path
from .views_admin import (
    AdminOverviewView,
    AdminAdvancedStatsView,
    AdminPlayersStatsView,
    AdminFeedbackListView,
    AdminFeedbackUpdateView,
)

urlpatterns = [
    path("stats/overview/", AdminOverviewView.as_view(), name="admin_overview"),
    path("stats/advanced/", AdminAdvancedStatsView.as_view(), name="admin-advanced"),
    path("stats/players/", AdminPlayersStatsView.as_view(), name="admin-players"),
    path("feedback/", AdminFeedbackListView.as_view(), name="admin-feedback-list"),
    path("feedback/<int:feedback_id>/", AdminFeedbackUpdateView.as_view(), name="admin-feedback-update"),
]
