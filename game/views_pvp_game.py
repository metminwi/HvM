from __future__ import annotations

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.renderers import JSONRenderer

from game.models import PvPGame, PvPMove, RematchRequest
from game.serializers import PvPGameStateSerializer, PvPHeadToHeadSerializer
from game.services.ws_notify import notify_game, notify_user
from game.services.pvp_rules import check_winner_board


class JsonAPIView(APIView):
    renderer_classes = [JSONRenderer]


def _role_for_user(game: PvPGame, user) -> str | None:
    if user.id == game.p1_id:
        return "X"
    if user.id == game.p2_id:
        return "O"
    return None


def _build_pvp_board(game: PvPGame) -> list[list[str]]:
    n = game.board_size
    board = [["" for _ in range(n)] for _ in range(n)]
    for m in PvPMove.objects.filter(game=game).order_by("move_number"):
        board[m.row][m.col] = m.player
    return board


class PvPGameStateView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, game_id: int):
        game = PvPGame.objects.filter(id=game_id).first()
        if not game:
            return Response({"detail": "Game not found"}, status=404)

        role = _role_for_user(game, request.user)
        if role is None and not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=403)

        moves = list(
            PvPMove.objects.filter(game=game)
            .order_by("move_number")
            .values("move_number", "player", "row", "col", "created_at")
        )

        payload = {
            "id": game.id,
            "status": game.status,
            "result": game.result,
            "winning_line": game.winning_line or [],
            "turn": game.turn,
            "board_size": game.board_size,
            "moves": moves,
            "me": {
                "id": request.user.id,
                "username": request.user.username,
            },
            "p1": {
                "id": game.p1_id,
                "username": game.p1.username,
            },
            "p2": (
                {
                    "id": game.p2_id,
                    "username": game.p2.username,
                }
                if game.p2_id
                else None
            ),
            "p1_username": game.p1.username,
            "p2_username": game.p2.username if game.p2_id else None,
            "your_symbol": role,
        }
        return Response(PvPGameStateSerializer(payload).data, status=200)


class PvPGameMoveView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, game_id: int):
        user = request.user
        row = request.data.get("row")
        col = request.data.get("col")

        # validate ints
        try:
            row = int(row)
            col = int(col)
        except (TypeError, ValueError):
            return Response({"detail": "row and col must be integers"}, status=400)

        with transaction.atomic():
            game = (
                PvPGame.objects.select_for_update()
                .filter(id=game_id)
                .first()
            )
            if not game:
                return Response({"detail": "Game not found"}, status=404)

            if game.status != PvPGame.Status.ACTIVE:
                return Response({"detail": "Game already ended"}, status=409)

            # bounds
            if row < 0 or col < 0 or row >= game.board_size or col >= game.board_size:
                return Response({"detail": "Out of bounds"}, status=400)

            role = _role_for_user(game, user)
            if role is None:
                return Response({"detail": "Not a participant"}, status=403)

            if game.turn != role:
                return Response({"detail": "Not your turn"}, status=409)

            # occupied check
            if PvPMove.objects.filter(game=game, row=row, col=col).exists():
                return Response({"detail": "Cell already occupied"}, status=409)

            move_number = PvPMove.objects.filter(game=game).count() + 1

            try:
                move = PvPMove.objects.create(
                    game=game,
                    move_number=move_number,
                    player=role,
                    row=row,
                    col=col,
                )
            except IntegrityError:
                return Response({"detail": "Move rejected (duplicate)"}, status=409)

            # Build board AFTER saving move
            board = _build_pvp_board(game)

            verdict = check_winner_board(board, win_len=5, last_move=(row, col))
            winner = verdict.get("winner")  # "X"|"O"|None
            winning_line = verdict.get("winning_line") or []
            draw_flag = bool(verdict.get("draw"))

            ended_payload = None

            if winner or draw_flag:
                game.status = PvPGame.Status.FINISHED
                game.ended_at = timezone.now()

                if winner == "X":
                    game.result = PvPGame.Result.P1_WIN
                elif winner == "O":
                    game.result = PvPGame.Result.P2_WIN
                else:
                    game.result = PvPGame.Result.DRAW

                game.winning_line = winning_line if winner else []
                game.last_move_at = timezone.now()
                game.save(update_fields=["status", "result", "winning_line", "ended_at", "last_move_at"])

                ended_payload = {
                    "type": "game.ended",
                    "game_id": game.id,
                    "result": game.result,
                    "reason": "win" if winner else "draw",
                    "winner": winner,
                    "winning_line": game.winning_line or [],
                }
            else:
                # Switch turn only if not ended
                game.turn = "O" if role == "X" else "X"
                game.last_move_at = timezone.now()
                game.save(update_fields=["turn", "last_move_at"])

        # ---------------- WS broadcasts (outside txn) ----------------

        notify_game(
            game.id,
            {
                "type": "game.move",
                "game_id": game.id,
                "move": {
                    "move_number": move.move_number,
                    "player": role,
                    "row": row,
                    "col": col,
                },
            },
        )

        if ended_payload:
            notify_game(game.id, ended_payload)
        else:
            notify_game(
                game.id,
                {
                    "type": "game.turn",
                    "game_id": game.id,
                    "turn": game.turn,
                },
            )

        # REST response should also include winning_line when ended
        resp = {
            "ok": True,
            "move": {"player": role, "row": row, "col": col},
            "turn": game.turn,
            "status": game.status,
            "result": game.result,
        }

        if ended_payload:
            resp["winner"] = winner
            resp["winning_line"] = game.winning_line or []

        return Response(resp, status=200)


class PvPHeadToHeadView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, game_id: int):
        game = PvPGame.objects.filter(id=game_id).first()
        if not game:
            return Response({"detail": "Game not found"}, status=404)

        role = _role_for_user(game, request.user)
        if role is None and not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=403)

        if game.p2_id is None:
            payload = {"total_games": 0, "p1_wins": 0, "p2_wins": 0, "draws": 0}
            return Response(PvPHeadToHeadSerializer(payload).data, status=200)

        h2h_qs = PvPGame.objects.filter(
            Q(p1_id=game.p1_id, p2_id=game.p2_id) | Q(p1_id=game.p2_id, p2_id=game.p1_id),
            status=PvPGame.Status.FINISHED,
        )

        p1_wins = h2h_qs.filter(
            Q(p1_id=game.p1_id, result=PvPGame.Result.P1_WIN)
            | Q(p2_id=game.p1_id, result=PvPGame.Result.P2_WIN)
        ).count()
        p2_wins = h2h_qs.filter(
            Q(p1_id=game.p2_id, result=PvPGame.Result.P1_WIN)
            | Q(p2_id=game.p2_id, result=PvPGame.Result.P2_WIN)
        ).count()

        payload = {
            "total_games": h2h_qs.count(),
            "p1_wins": p1_wins,
            "p2_wins": p2_wins,
            "draws": h2h_qs.filter(result=PvPGame.Result.DRAW).count(),
        }
        return Response(PvPHeadToHeadSerializer(payload).data, status=200)


class PvPGameResignView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, game_id: int):
        game = PvPGame.objects.filter(id=game_id).first()
        if not game:
            return Response({"detail": "Game not found"}, status=404)

        role = _role_for_user(game, request.user)
        if role is None and not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=403)

        if game.status != PvPGame.Status.ACTIVE:
            return Response({"detail": "Game not active"}, status=409)

        # Determine winner on resign
        winner = "O" if role == "X" else "X"
        game.status = PvPGame.Status.FINISHED
        game.ended_at = timezone.now()
        game.result = PvPGame.Result.P2_WIN if role == "X" else PvPGame.Result.P1_WIN
        game.winning_line = []
        game.save(update_fields=["status", "ended_at", "result", "winning_line"])

        notify_game(
            game.id,
            {
                "type": "game.ended",
                "game_id": game.id,
                "result": game.result,
                "reason": "resign",
                "by": role,
                "winner": winner,
                "winning_line": [],
            },
        )

        return Response(
            {"ok": True, "result": game.result, "winner": winner, "winning_line": []},
            status=200,
        )


class PvPRematchRequestView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, game_id: int):
        with transaction.atomic():
            game = PvPGame.objects.select_for_update().filter(id=game_id).first()
            if not game:
                return Response({"detail": "Game not found"}, status=404)

            role = _role_for_user(game, request.user)
            if role is None:
                return Response({"detail": "Forbidden"}, status=403)

            if game.status != PvPGame.Status.FINISHED:
                return Response({"detail": "Rematch available only for finished games"}, status=409)

            rematch = (
                RematchRequest.objects.select_for_update()
                .filter(game=game, status=RematchRequest.Status.PENDING)
                .first()
            )

            if rematch:
                rematch.requester = request.user
                rematch.new_game = None
                rematch.save(update_fields=["requester", "new_game"])
            else:
                rematch = RematchRequest.objects.create(
                    game=game,
                    requester=request.user,
                    status=RematchRequest.Status.PENDING,
                )

        opponent_id = game.p2_id if request.user.id == game.p1_id else game.p1_id
        notify_user(
            opponent_id,
            {
                "type": "game.rematch.requested",
                "game_id": game.id,
                "requester_id": request.user.id,
            },
        )

        return Response({"ok": True, "status": rematch.status}, status=200)


class PvPRematchAcceptView(JsonAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, game_id: int):
        with transaction.atomic():
            game = PvPGame.objects.select_for_update().filter(id=game_id).first()
            if not game:
                return Response({"detail": "Game not found"}, status=404)

            role = _role_for_user(game, request.user)
            if role is None:
                return Response({"detail": "Forbidden"}, status=403)

            if game.status != PvPGame.Status.FINISHED:
                return Response({"detail": "Rematch available only for finished games"}, status=409)

            rematch = (
                RematchRequest.objects.select_for_update()
                .filter(game=game, status=RematchRequest.Status.PENDING)
                .first()
            )
            if not rematch:
                return Response({"detail": "No pending rematch request"}, status=409)

            if rematch.requester_id == request.user.id:
                return Response({"detail": "Requester cannot accept own rematch request"}, status=409)

            new_game = PvPGame.objects.create(
                p1_id=game.p2_id,
                p2_id=game.p1_id,
                mode=game.mode,
                status=PvPGame.Status.ACTIVE,
                result=PvPGame.Result.ONGOING,
                board_size=game.board_size,
                turn="X",
                turn_timeout_sec=game.turn_timeout_sec,
                time_control=game.time_control,
            )

            rematch.status = RematchRequest.Status.ACCEPTED
            rematch.new_game = new_game
            rematch.save(update_fields=["status", "new_game"])

        payload = {
            "type": "game.rematch.accepted",
            "old_game_id": game.id,
            "new_game_id": new_game.id,
        }
        notify_user(game.p1_id, payload)
        notify_user(game.p2_id, payload)

        return Response({"ok": True, "new_game_id": new_game.id}, status=200)
