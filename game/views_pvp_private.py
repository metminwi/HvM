from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from game.models import PvPGame
from game.services.ws_notify import notify_game, notify_lobby


class JsonAPIView(APIView):
    renderer_classes = [JSONRenderer]


class PvPPrivateCreateView(JsonAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        mode = (request.data.get("mode") or PvPGame.Mode.CASUAL).strip().lower()
        board_size = request.data.get("board_size", 15)

        if mode not in (PvPGame.Mode.CASUAL, PvPGame.Mode.RANKED):
            return Response({"detail": "Invalid mode"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            board_size = int(board_size)
        except (TypeError, ValueError):
            return Response({"detail": "board_size must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        if board_size <= 0:
            return Response({"detail": "board_size must be > 0"}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        game = PvPGame.objects.create(
            p1=request.user,
            p2=None,
            mode=mode,
            status=PvPGame.Status.WAITING,
            result=PvPGame.Result.ONGOING,
            board_size=board_size,
            turn="X",
            is_private=True,
            invite_code=PvPGame.generate_unique_invite_code(),
            invite_created_at=now,
            invite_expires_at=now + timedelta(minutes=30),
            invite_used_at=None,
        )
        return Response(
            {"game_id": game.id, "invite_code": game.invite_code},
            status=status.HTTP_201_CREATED,
        )


class PvPPrivateJoinView(JsonAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invite_code = (request.data.get("code") or "").strip().upper()
        if not invite_code:
            return Response({"code": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            game = (
                PvPGame.objects.select_for_update()
                .filter(
                    invite_code=invite_code,
                    is_private=True,
                    status__in=[PvPGame.Status.WAITING, PvPGame.Status.ACTIVE],
                )
                .first()
            )
            if not game:
                return Response({"detail": "Invite not found"}, status=status.HTTP_404_NOT_FOUND)
            if game.invite_expires_at and game.invite_expires_at <= timezone.now():
                return Response({"detail": "Invite has expired"}, status=status.HTTP_404_NOT_FOUND)

            if game.p2_id is None and request.user.id != game.p1_id:
                game.p2 = request.user
                game.status = PvPGame.Status.ACTIVE
                game.result = PvPGame.Result.ONGOING
                game.invite_used_at = timezone.now()
                game.save(update_fields=["p2", "status", "result", "invite_used_at"])

                payload = {
                    "type": "private.matched",
                    "game_id": game.id,
                    "status": game.status,
                    "turn": game.turn,
                    "p2_username": game.p2.username,
                }
                transaction.on_commit(lambda: notify_lobby(payload))
                transaction.on_commit(lambda: notify_game(game.id, payload))
            elif game.p2_id is not None and request.user.id not in (game.p1_id, game.p2_id):
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        return Response({"game_id": game.id}, status=status.HTTP_200_OK)


class PvPPrivateLookupView(JsonAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invite_code = (request.query_params.get("code") or "").strip().upper()
        if not invite_code:
            return Response({"detail": "code is required"}, status=status.HTTP_400_BAD_REQUEST)

        game = PvPGame.objects.filter(invite_code=invite_code, is_private=True).select_related("p1").first()
        if not game:
            return Response({"exists": False, "status": None, "host_username": None}, status=status.HTTP_200_OK)

        return Response(
            {
                "exists": True,
                "status": game.status,
                "host_username": game.p1.username,
            },
            status=status.HTTP_200_OK,
        )


# Aliases with expected naming used by URL wiring.
CreateInviteView = PvPPrivateCreateView
JoinInviteView = PvPPrivateJoinView
