# game/urls.py
from django.urls import path
from .views import HealthView, AIMoveView

urlpatterns = [
    path("health/", HealthView.as_view()),
    path("ai/move/", AIMoveView.as_view()),
]
