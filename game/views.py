"""
game/views.py

V2 (pro) backend for the Gomoku Arena.

- StartGameView creates a real Game row in DB
- PlayerMoveView persists moves in DB
- AIMoveView uses the AI router (engine | gemini | openspiel)
- EndGameView ends a game with result
- DashboardView computes win%, streak, best streak so QuickProgress updates

NOTE:
Auth (CSRF / signup / login / logout / me) has been moved out of this file.
Use: game/views_session_auth.py + game/urls_auth_session.py for session auth endpoints.
"""
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated

from typing import Any, List, Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Game, Move
from .ai.ai_router import pick_ai_move


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _build_board(game: Game) -> List[List[str]]:
    size = int(game.board_size or 15)
    board = [["" for _ in range(size)] for _ in range(size)]
    for m in game.moves.all().order_by("move_number"):
        if 0 <= m.row < size and 0 <= m.col < size:
            board[m.row][m.col] = m.player
    return board


def _cell_occupied(game: Game, row: int, col: int) -> bool:
    return game.moves.filter(row=row, col=col).exists()


def _next_move_number(game: Game) -> int:
    last = game.moves.order_by("-move_number").first()
    return (last.move_number + 1) if last else 1


def _normalize_mode(mode: Optional[str]) -> str:
    mode = (mode or "engine").lower()
    if mode not in {"engine", "gemini", "openspiel"}:
        return "engine"
    return mode


def _normalize_difficulty(d: Optional[str]) -> str:
    d = (d or "standard").lower()
    if d not in {"easy", "standard", "challenge"}:
        return "standard"
    return d


def _normalize_result(r: Optional[str]) -> str:
    r = (r or "ongoing").lower()
    if r in {"win", "loss", "draw"}:
        return r
    return "ongoing"


class StartGameView(APIView):
    """
    POST /api/game/start/
    Body: { mode: "engine"|"gemini"|"openspiel", board_size: 15, ranked: true, difficulty: "easy"|"standard"|"challenge" }
    Returns: { id, mode, difficulty, board_size, ranked }
    """

    def post(self, request):
        mode = _normalize_mode(request.data.get("mode"))
        difficulty = _normalize_difficulty(request.data.get("difficulty"))
        board_size = _as_int(request.data.get("board_size"), 15)
        ranked = bool(request.data.get("ranked", False))

        game = Game.objects.create(
            user=request.user
            if getattr(request, "user", None) and request.user.is_authenticated
            else None,
            mode=mode,
            difficulty=difficulty,
            board_size=board_size,
            ranked=ranked,
            status="active",
            result="ongoing",
        )

        return Response(
            {
                "id": game.id,
                "mode": game.mode,
                "difficulty": game.difficulty,
                "board_size": game.board_size,
                "ranked": game.ranked,
            },
            status=status.HTTP_201_CREATED,
        )


class PlayerMoveView(APIView):
    """
    POST /api/game/<game_id>/moves/
    Body: { row, col, player? }  player defaults to "X"
    """

    def post(self, request, game_id: int):
        game = Game.objects.filter(id=game_id).first()
        if not game:
            return Response({"detail": "Game not found"}, status=status.HTTP_404_NOT_FOUND)
        if game.status != "active":
            return Response({"detail": "Game finished"}, status=status.HTTP_409_CONFLICT)

        row = _as_int(request.data.get("row"), -1)
        col = _as_int(request.data.get("col"), -1)
        player = (request.data.get("player") or "X").upper()[:1]

        if row < 0 or col < 0 or row >= game.board_size or col >= game.board_size:
            return Response({"detail": "Invalid cell"}, status=status.HTTP_400_BAD_REQUEST)

        if _cell_occupied(game, row, col):
            return Response({"detail": "Cell already occupied"}, status=status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                Move.objects.create(
                    game=game,
                    move_number=_next_move_number(game),
                    player=player,
                    row=row,
                    col=col,
                )
        except IntegrityError:
            return Response(
                {"detail": "Move rejected (duplicate)"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"ok": True, "move": {"row": row, "col": col, "player": player}})



class AIMoveView(APIView):
    """
    POST /api/game/ai/move/
    Body: { game_id, engine: "engine"|"gemini"|"openspiel", difficulty? }
    Returns: { move:{row,col,player}, meta:{} }
    """

    def post(self, request):
        data = request.data
        game_id = data.get("game_id")
        engine = data.get("engine") or data.get("mode") or "engine"
        difficulty = data.get("difficulty", "standard")

        # -----------------------
        # 1. Game validation
        # -----------------------
        game = Game.objects.filter(id=game_id).first()
        if not game:
            return Response(
                {"detail": "Game not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if game.status != "active":
            return Response(
                {"detail": "Game finished"},
                status=status.HTTP_409_CONFLICT
            )

        # -----------------------
        # 2. Build board (""|"X"|"O") -> (0|1|-1)
        # -----------------------
        raw_board = _build_board(game)
        board = []

        for row in raw_board:
            int_row = []
            for cell in row:
                if cell == "X":
                    int_row.append(1)     # Human
                elif cell == "O":
                    int_row.append(-1)    # AI
                else:
                    int_row.append(0)     # Empty
            board.append(int_row)

        # -----------------------
        # 3. Call AI engine
        # -----------------------
        try:
            row, col, meta = pick_ai_move(
                engine_id=engine,
                board=board,
                difficulty=difficulty,
            )
        except Exception as e:
            return Response(
                {
                    "detail": "AI engine crashed",
                    "engine": engine,
                    "difficulty": difficulty,
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        row = _as_int(row, -1)
        col = _as_int(col, -1)
        meta = meta or {}

        # -----------------------
        # 4. Validate AI move
        # -----------------------
        if row < 0 or col < 0 or row >= game.board_size or col >= game.board_size:
            return Response(
                {"detail": "AI returned invalid move", "meta": meta},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if _cell_occupied(game, row, col):
            return Response(
                {"detail": "AI selected an occupied cell", "meta": meta},
                status=status.HTTP_409_CONFLICT,
            )

        # -----------------------
        # 5. Persist move
        # -----------------------
        try:
            with transaction.atomic():
                Move.objects.create(
                    game=game,
                    move_number=_next_move_number(game),
                    player="O",
                    row=row,
                    col=col,
                )
        except IntegrityError:
            return Response(
                {"detail": "AI move rejected (duplicate)", "meta": meta},
                status=status.HTTP_409_CONFLICT,
            )

        # -----------------------
        # 6. Success
        # -----------------------
        return Response(
            {
                "move": {"row": row, "col": col, "player": "O"},
                "meta": meta,
            },
            status=status.HTTP_200_OK,
        )


class EndGameView(APIView):
    """
    POST /api/game/<game_id>/end/
    Body: { result: "win"|"loss"|"draw" }
    """

    def post(self, request, game_id: int):
        game = Game.objects.filter(id=game_id).first()
        if not game:
            return Response({"detail": "Game not found"}, status=status.HTTP_404_NOT_FOUND)

        result = _normalize_result(request.data.get("result"))
        game.result = result
        game.status = "finished"
        game.ended_at = timezone.now()
        game.save(update_fields=["result", "status", "ended_at"])

        return Response({"ok": True, "id": game.id, "result": game.result})

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        qs = Game.objects.filter(user=request.user).exclude(result="ongoing").order_by("-ended_at", "-created_at")

        total = qs.count()
        wins = qs.filter(result="win").count()
        losses = qs.filter(result="loss").count()
        draws = qs.filter(result="draw").count()
        win_rate = round((wins / total) * 100, 1) if total else 0.0

        # Current streak
        streak = 0
        for g in qs:
            if g.result == "win":
                streak += 1
            else:
                break

        # Best streak
        best_streak = 0
        current = 0
        for g in qs.reverse():  # oldest -> newest
            if g.result == "win":
                current += 1
                best_streak = max(best_streak, current)
            else:
                current = 0

        return Response({
            "games": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": win_rate,
            "streak": streak,
            "best_streak": best_streak,
        }, status=status.HTTP_200_OK)

""" class DetailedDashboardV2View(APIView):
    """
"""     GET /api/game/dashboard/detailed-v2/
    -> payload clean pour le dashboard graphique HvM.
    """ """

    permission_classes = []
    authentication_classes = []

    def get(self, request):
        try:
            user = get_current_user(request)
            payload = get_detailed_dashboard_v2(user)
            serializer = DetailedDashboardV2Serializer(payload)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            # log basique en DEV
            print("ERROR in DetailedDashboardV2View:", e)
            return Response(
                {"detail": "Internal error in detailed dashboard v2."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) """
from rest_framework.permissions import IsAuthenticated

class GameHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Game.objects
            .filter(user=request.user)
            .order_by("-created_at")[:20]
        )

        data = []
        for g in qs:
            moves_count = g.moves.count()
            data.append({
                "id": g.id,
                "date": g.created_at,
                "engine": g.mode,
                "difficulty": g.difficulty,
                "result": g.result,
                "moves": moves_count,
            })

        return Response(data, status=status.HTTP_200_OK)


from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.models import Q
import traceback

class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        try:
            scope = (request.query_params.get("scope") or "human").lower()
            period = (request.query_params.get("period") or "global").lower()
            limit = _as_int(request.query_params.get("limit"), 20)
            limit = max(1, min(limit, 200))

            # Pas de "AI users" dans ton modèle actuel → ai vide
            if scope == "ai":
                return Response([], status=status.HTTP_200_OK)

            # period start
            now = timezone.now()
            if period == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start = now - timedelta(days=7)
            elif period == "month":
                start = now - timedelta(days=30)
            else:
                start = None

            qs = Game.objects.exclude(result="ongoing").filter(user__isnull=False)

            if start:
                # ended_at peut être NULL dans tes games → fallback created_at
                qs = qs.filter(
                    Q(ended_at__gte=start) |
                    Q(ended_at__isnull=True, created_at__gte=start)
                )

            user_ids = list(qs.values_list("user_id", flat=True).distinct())

            User = get_user_model()
            users = {u.id: u for u in User.objects.filter(id__in=user_ids)}

            entries = []
            for uid in user_ids:
                u = users.get(uid)
                if not u:
                    continue

                user_qs = qs.filter(user_id=uid).order_by("ended_at", "created_at")

                games_in_period = user_qs.count()
                wins_in_period = user_qs.filter(result="win").count()
                losses = user_qs.filter(result="loss").count()

                wins_engine = user_qs.filter(result="win", mode="engine").count()
                wins_gemini = user_qs.filter(result="win", mode="gemini").count()

                # rating provisoire = winrate en %
                rating = int(round((wins_in_period / games_in_period) * 100)) if games_in_period else 0

                # badge simple
                if rating >= 90:
                    badge = "legend"
                elif rating >= 75:
                    badge = "gold"
                elif rating >= 60:
                    badge = "silver"
                else:
                    badge = "bronze"

                # best streak
                best_streak = 0
                cur = 0
                for g in user_qs:
                    if g.result == "win":
                        cur += 1
                        best_streak = max(best_streak, cur)
                    else:
                        cur = 0

                username = getattr(u, "username", None) or getattr(u, "email", None) or f"user_{uid}"

                entries.append({
                    "id": uid,
                    "username": username,
                    "player_type": "human",
                    "badge": badge,
                    "rating": rating,
                    "wins_engine": wins_engine,
                    "wins_gemini": wins_gemini,
                    "losses": losses,
                    "best_streak": best_streak,
                    "games_in_period": games_in_period,
                    "wins_in_period": wins_in_period,
                })

            entries.sort(key=lambda e: (e["wins_in_period"], e["rating"]), reverse=True)

            return Response(entries[:limit], status=status.HTTP_200_OK)

        except Exception as e:
            print("LEADERBOARD ERROR:", e)
            traceback.print_exc()
            return Response({"detail": "leaderboard error", "error": str(e)}, status=500)
