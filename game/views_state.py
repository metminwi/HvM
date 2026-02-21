from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Game
from .serializers import GameStateSerializer

class GameStateView(APIView):
    # Autorise non-auth si game.user est null (parties guest)
    permission_classes = [permissions.AllowAny]

    def get(self, request, game_id: int):
        game = Game.objects.filter(id=game_id).prefetch_related("moves").first()
        if not game:
            return Response({"detail": "Game not found"}, status=status.HTTP_404_NOT_FOUND)

        # Si la partie appartient à un user, seul lui (ou admin) peut la lire
        if game.user_id:
            if not request.user.is_authenticated:
                return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
            if request.user.id != game.user_id and not request.user.is_staff:
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        return Response(GameStateSerializer(game).data, status=status.HTTP_200_OK)
