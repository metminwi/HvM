"""
game/urls.py

API routes consumed by the Next.js frontend (apiFetch).

Auth is handled by session-based endpoints in:
- game/urls_auth_session.py  -> /api/game/auth/...
- game/views_session_auth.py
"""

from django.urls import path, include

from .views import (
    AIMoveView,
    DashboardView,
    EndGameView,
    PlayerMoveView,
    StartGameView,
    GameHistoryView,
    LeaderboardView,
)
from .views_state import GameStateView

urlpatterns = [
    # ✅ Session auth (CSRF / signup / login / logout / me)
    path("auth/", include("game.urls_auth_session")),

    

    # ✅ Gameplay
    path("start/", StartGameView.as_view(), name="start_game"),
    path("<int:game_id>/moves/", PlayerMoveView.as_view(), name="player_move"),
    path("<int:game_id>/end/", EndGameView.as_view(), name="end_game"),

    # ✅ Single AI endpoint (engine | gemini | openspiel chosen by body.engine)
    path("ai/move/", AIMoveView.as_view(), name="ai_move"),
    # feedback user
    path("feedback/", include("game.urls_feedback")),

    # admin analytics + feedback admin
    path("admin/", include("game.urls_admin")),

    path("<int:game_id>/state/", GameStateView.as_view(), name="game_state"),

    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("games/history/", GameHistoryView.as_view(), name="game_history"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    # ✅ PVP
    path("pvp/", include("game.urls_pvp")),


]
