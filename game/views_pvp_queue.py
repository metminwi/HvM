from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.renderers import JSONRenderer

from game.models import MatchQueueEntry, PlayerRating
from game.services.matchmaking import try_match


class JsonAPIView(APIView):
    renderer_classes = [JSONRenderer]


class QueueJoinView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mode = (request.data.get("mode") or "casual").lower()
        if mode not in ("casual", "ranked"):
            return Response({"detail": "Invalid mode"}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure rating exists for ranked and snapshot it
        elo = 1200
        if mode == "ranked":
            rating, _ = PlayerRating.objects.get_or_create(user=request.user)
            elo = rating.elo_ranked

        # Cancel any existing waiting entry for this user+mode (simple rule)
        MatchQueueEntry.objects.filter(
            user=request.user,
            mode=mode,
            status=MatchQueueEntry.Status.WAITING,
        ).update(status=MatchQueueEntry.Status.CANCELLED)

        entry = MatchQueueEntry.objects.create(
            user=request.user,
            mode=mode,
            status=MatchQueueEntry.Status.WAITING,
            elo_snapshot=elo,
            preferences=request.data.get("preferences") or None,
        )

        # Try match immediately
        result = try_match(entry.id)

        if result.matched:
            return Response(
                {
                    "status": "matched",
                    "entry_id": entry.id,
                    "game_id": result.game_id,
                    "role": result.role,
                    "opponent_user_id": result.opponent_user_id,
                },
                status=status.HTTP_200_OK,
            )

        # Still waiting: return position + estimate
        position = (
            MatchQueueEntry.objects.filter(mode=mode, status=MatchQueueEntry.Status.WAITING, created_at__lte=entry.created_at)
            .count()
        )
        estimated_wait_sec = min(30, 5 + position * 3)  # heuristic MVP

        return Response(
            {
                "status": "waiting",
                "entry_id": entry.id,
                "position": position,
                "estimated_wait_sec": estimated_wait_sec,
            },
            status=status.HTTP_200_OK,
        )


class QueueLeaveView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mode = (request.data.get("mode") or "casual").lower()
        if mode not in ("casual", "ranked"):
            return Response({"detail": "Invalid mode"}, status=status.HTTP_400_BAD_REQUEST)

        updated = MatchQueueEntry.objects.filter(
            user=request.user,
            mode=mode,
            status=MatchQueueEntry.Status.WAITING,
        ).update(status=MatchQueueEntry.Status.CANCELLED)

        return Response({"ok": True, "cancelled": updated}, status=status.HTTP_200_OK)


class QueueStatusView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mode = (request.query_params.get("mode") or "casual").lower()
        if mode not in ("casual", "ranked"):
            return Response({"detail": "Invalid mode"}, status=status.HTTP_400_BAD_REQUEST)

        entry = (
            MatchQueueEntry.objects
            .filter(user=request.user, mode=mode)
            .order_by("-created_at")
            .first()
        )

        if not entry:
            return Response({"status": "idle"}, status=status.HTTP_200_OK)

        if entry.status == MatchQueueEntry.Status.WAITING:
            position = (
                MatchQueueEntry.objects.filter(mode=mode, status=MatchQueueEntry.Status.WAITING, created_at__lte=entry.created_at)
                .count()
            )
            estimated_wait_sec = min(30, 5 + position * 3)
            return Response(
                {
                    "status": "waiting",
                    "entry_id": entry.id,
                    "position": position,
                    "estimated_wait_sec": estimated_wait_sec,
                    "elo_snapshot": entry.elo_snapshot,
                    "created_at": entry.created_at,
                },
                status=status.HTTP_200_OK,
            )

        if entry.status == MatchQueueEntry.Status.MATCHED:
           return Response({
            "status": "matched",
            "entry_id": entry.id,
            "game_id": entry.matched_game_id,
            }, status=200)


        return Response(
            {"status": entry.status, "entry_id": entry.id},
            status=status.HTTP_200_OK,
        )
