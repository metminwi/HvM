from django.urls import path
from game.views_pvp_queue import QueueJoinView, QueueLeaveView, QueueStatusView
from game.views_pvp_game import (
    PvPGameStateView,
    PvPGameMoveView,
    PvPGameResignView,
    PvPHeadToHeadView,
    PvPRematchRequestView,
    PvPRematchAcceptView,
)
from game.views_pvp_private import (
    CreateInviteView,
    JoinInviteView,
    PvPPrivateLookupView,
)

urlpatterns = [
    path("queue/join/", QueueJoinView.as_view(), name="pvp-queue-join"),
    path("queue/leave/", QueueLeaveView.as_view(), name="pvp-queue-leave"),
    path("queue/status/", QueueStatusView.as_view(), name="pvp-queue-status"),
    path("games/<int:game_id>/state/", PvPGameStateView.as_view(), name="pvp-game-state"),
    path("games/<int:game_id>/headtohead/", PvPHeadToHeadView.as_view(), name="pvp-game-headtohead"),
    path("games/<int:game_id>/move/", PvPGameMoveView.as_view(), name="pvp-game-move"),
    path("games/<int:game_id>/resign/", PvPGameResignView.as_view(), name="pvp-game-resign"),
    path("games/<int:game_id>/rematch/request/", PvPRematchRequestView.as_view(), name="pvp-game-rematch-request"),
    path("games/<int:game_id>/rematch/accept/", PvPRematchAcceptView.as_view(), name="pvp-game-rematch-accept"),
    path("private/create/", CreateInviteView.as_view(), name="pvp-private-create"),
    path("private/join/", JoinInviteView.as_view(), name="pvp-private-join"),
    path("private/lookup/", PvPPrivateLookupView.as_view(), name="pvp-private-lookup"),
]
