from django.shortcuts import render

# Create your views here.
# game/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ai import best_move

class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})

class AIMoveView(APIView):
    """
    POST /api/game/ai/move/
    Body JSON:
    {
      "board": [["","",""],["","",""],["","",""]],
      "difficulty": "pro" | "basic"   # optionnel
      "human_symbol": "X", "ai_symbol": "O"  # optionnel
    }
    """
    def post(self, request):
        body = request.data or {}
        board = body.get("board")
        if not board or not isinstance(board, list):
            return Response({"error": "board required"}, status=status.HTTP_400_BAD_REQUEST)

        difficulty = body.get("difficulty", "basic")
        depth = 2 if difficulty != "pro" else 4

        # Normaliser : remplace None par ""
        n = len(board)
        norm = []
        for r in range(n):
            row = []
            for c in range(len(board[r])):
                v = board[r][c]
                row.append("" if v in (None, ".", " ") else str(v))
            norm.append(row)

        move = best_move(norm, depth=depth)
        if move is None:
            return Response({"move": None})
        r, c = move
        return Response({"move": {"row": r, "col": c}, "depth": depth})
