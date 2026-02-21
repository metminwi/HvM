from django.urls import path
from .views_session_auth import (
    CSRFView,
    SignupSessionView,
    LoginSessionView,
    LogoutSessionView,
    MeSessionView,
    ProfileSessionView,
    ChangePasswordSessionView,
)

urlpatterns = [
    path("csrf/", CSRFView.as_view(), name="csrf"),
    path("signup/", SignupSessionView.as_view(), name="session-signup"),
    path("login/", LoginSessionView.as_view(), name="session-login"),
    path("logout/", LogoutSessionView.as_view(), name="session-logout"),
    path("me/", MeSessionView.as_view(), name="session-me"),
    path("profile/", ProfileSessionView.as_view(), name="auth_profile"),
    path("password/change/", ChangePasswordSessionView.as_view(), name="auth_password_change"),
]
