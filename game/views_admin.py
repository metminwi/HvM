from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Max, F, Value, FloatField, ExpressionWrapper, Case, When
from django.core.exceptions import FieldError
from django.utils import timezone
from datetime import timedelta
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ParseError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Game, Move, Feedback
from .serializers import FeedbackAdminSerializer, FeedbackAdminUpdateSerializer

User = get_user_model()


class AdminAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]
    renderer_classes = [JSONRenderer]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if response is not None and response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ):
            detail = None
            if isinstance(response.data, dict):
                detail = response.data.get("detail")
            if not isinstance(detail, str):
                detail = (
                    "Authentication credentials were not provided."
                    if response.status_code == status.HTTP_401_UNAUTHORIZED
                    else "You do not have permission to perform this action."
                )
            response.data = {"detail": detail}
        return response

    @staticmethod
    def _parse_int_query_param(request, key: str, default: int) -> int:
        raw_value = request.query_params.get(key)
        if raw_value in (None, ""):
            return default
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise ParseError(f"Invalid query param '{key}': expected an integer.")

    @staticmethod
    def _parse_optional_int_query_param(request, key: str):
        raw_value = request.query_params.get(key)
        if raw_value in (None, ""):
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise ParseError(f"Invalid query param '{key}': expected an integer.")

    @staticmethod
    def _parse_optional_bool_query_param(request, key: str):
        raw_value = request.query_params.get(key)
        if raw_value in (None, ""):
            return None

        value = str(raw_value).strip().lower()
        if value in ("1", "true", "t", "yes", "y", "on"):
            return True
        if value in ("0", "false", "f", "no", "n", "off"):
            return False
        raise ParseError(
            f"Invalid query param '{key}': expected a boolean (true/false)."
        )


class AdminOverviewView(AdminAPIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        users_total = User.objects.count()
        users_active_7d = User.objects.filter(
            Q(last_login__gte=d7) | (Q(last_login__isnull=True) & Q(date_joined__gte=d7))
        ).count()
        users_active_30d = User.objects.filter(
            Q(last_login__gte=d30) | (Q(last_login__isnull=True) & Q(date_joined__gte=d30))
        ).count()

        games_total = Game.objects.count()
        games_last_7d = Game.objects.filter(created_at__gte=d7).count()
        try:
            games_active = Game.objects.filter(status="active").count()
            games_finished = Game.objects.filter(status="finished").count()
        except (FieldError, ValueError):
            try:
                games_active = Game.objects.filter(result="ongoing").count()
                games_finished = Game.objects.exclude(result="ongoing").count()
            except (FieldError, ValueError):
                games_active = 0
                games_finished = 0

        moves_total = Move.objects.count()

        feedback_total = Feedback.objects.count()
        feedback_new = 0
        for status_value in ("new", "open", "pending"):
            try:
                feedback_new = Feedback.objects.filter(status=status_value).count()
                break
            except (FieldError, ValueError):
                continue

        return Response({
            "kpis": {
                "users_total": int(users_total),
                "users_active_7d": int(users_active_7d),
                "users_active_30d": int(users_active_30d),
                "games_total": int(games_total),
                "games_last_7d": int(games_last_7d),
                "games_active": int(games_active),
                "games_finished": int(games_finished),
                "moves_total": int(moves_total),
                "feedback_total": int(feedback_total),
                "feedback_new": int(feedback_new),
            }
        })


# Backward-compatible alias for older imports.
AdminOverviewStatsView = AdminOverviewView


class AdminPlayersStatsView(AdminAPIView):
    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        is_staff = self._parse_optional_bool_query_param(request, "is_staff")
        is_active = self._parse_optional_bool_query_param(request, "is_active")
        min_games = self._parse_optional_int_query_param(request, "min_games")
        sort = (request.query_params.get("sort") or "").strip()
        order = (request.query_params.get("order") or "desc").strip().lower()

        if min_games is not None and min_games < 0:
            raise ParseError("Invalid query param 'min_games': must be >= 0.")

        allowed_sort = {"", "games", "win_rate", "last_game_at"}
        if sort not in allowed_sort:
            raise ParseError(
                "Invalid query param 'sort': expected one of games, win_rate, last_game_at."
            )
        if order not in ("asc", "desc"):
            raise ParseError("Invalid query param 'order': expected 'asc' or 'desc'.")

        # simple pagination
        page = self._parse_int_query_param(request, "page", 1)
        page_size = self._parse_int_query_param(request, "page_size", 25)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        offset = (page - 1) * page_size

        qs = (
            User.objects
            .annotate(
                games=Count("game", distinct=True),
                wins=Count("game", filter=Q(game__result="win"), distinct=True),
                losses=Count("game", filter=Q(game__result="loss"), distinct=True),
                draws=Count("game", filter=Q(game__result="draw"), distinct=True),
                last_game_at=Max("game__created_at"),
            )
            .annotate(
                win_rate=Case(
                    When(games=0, then=Value(0.0)),
                    default=ExpressionWrapper(
                        Value(100.0) * F("wins") / F("games"),
                        output_field=FloatField(),
                    ),
                    output_field=FloatField(),
                )
            )
        )

        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
        if is_staff is not None:
            qs = qs.filter(is_staff=is_staff)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if min_games is not None:
            qs = qs.filter(games__gte=min_games)

        if sort == "":
            qs = qs.order_by("-games", "-last_game_at")
        else:
            prefix = "" if order == "asc" else "-"
            if sort == "games":
                qs = qs.order_by(f"{prefix}games", f"{prefix}last_game_at")
            elif sort == "win_rate":
                qs = qs.order_by(f"{prefix}win_rate", f"{prefix}games", f"{prefix}last_game_at")
            elif sort == "last_game_at":
                qs = qs.order_by(f"{prefix}last_game_at", f"{prefix}games")

        total = qs.count()
        rows = qs[offset: offset + page_size]

        data = []
        for u in rows:
            games = u.games or 0
            wins = u.wins or 0
            win_rate = round(float(u.win_rate or 0.0), 1)
            data.append({
                "id": u.id,
                "username": getattr(u, "username", ""),
                "email": getattr(u, "email", ""),
                "games": games,
                "wins": wins,
                "losses": u.losses or 0,
                "draws": u.draws or 0,
                "win_rate": win_rate,
                "last_game_at": u.last_game_at,
                "is_staff": u.is_staff,
                "is_active": u.is_active,
            })

        return Response({
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": data,
        })


class AdminAdvancedStatsView(AdminAPIView):
    def get(self, request):
        by_engine_rows = (
            Game.objects
            .values("mode")
            .annotate(
                total=Count("id"),
                finished=Count("id", filter=Q(status="finished")),
                win=Count("id", filter=Q(result="win")),
                loss=Count("id", filter=Q(result="loss")),
                draw=Count("id", filter=Q(result="draw")),
            )
            .order_by("mode")
        )

        by_difficulty_rows = (
            Game.objects
            .values("difficulty")
            .annotate(
                total=Count("id"),
                finished=Count("id", filter=Q(status="finished")),
                win=Count("id", filter=Q(result="win")),
                loss=Count("id", filter=Q(result="loss")),
                draw=Count("id", filter=Q(result="draw")),
            )
            .order_by("difficulty")
        )

        matrix_rows = (
            Game.objects
            .values("mode", "difficulty")
            .annotate(count=Count("id"))
            .order_by("mode", "difficulty")
        )

        games_by_engine = {}
        for row in by_engine_rows:
            mode = row["mode"] or "unknown"
            games_by_engine[mode] = {
                "total": int(row["total"]),
                "finished": int(row["finished"]),
                "win": int(row["win"]),
                "loss": int(row["loss"]),
                "draw": int(row["draw"]),
            }

        games_by_difficulty = {}
        for row in by_difficulty_rows:
            difficulty = row["difficulty"] or "unknown"
            games_by_difficulty[difficulty] = {
                "total": int(row["total"]),
                "finished": int(row["finished"]),
                "win": int(row["win"]),
                "loss": int(row["loss"]),
                "draw": int(row["draw"]),
            }

        engine_difficulty_matrix = {}
        for row in matrix_rows:
            mode = row["mode"] or "unknown"
            difficulty = row["difficulty"] or "unknown"
            if mode not in engine_difficulty_matrix:
                engine_difficulty_matrix[mode] = {}
            engine_difficulty_matrix[mode][difficulty] = int(row["count"])

        return Response({
            "games_by_engine": games_by_engine,
            "games_by_difficulty": games_by_difficulty,
            "engine_difficulty_matrix": engine_difficulty_matrix,
        })


class AdminFeedbackListView(AdminAPIView):
    def get(self, request):
        status_filter = request.query_params.get("status")
        type_filter = request.query_params.get("type")

        qs = Feedback.objects.all().select_related("user", "game")

        if status_filter:
            qs = qs.filter(status=status_filter)
        if type_filter:
            qs = qs.filter(type=type_filter)

        # simple pagination
        page = self._parse_int_query_param(request, "page", 1)
        page_size = self._parse_int_query_param(request, "page_size", 25)
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        offset = (page - 1) * page_size

        total = qs.count()
        items = qs[offset: offset + page_size]
        return Response({
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": FeedbackAdminSerializer(items, many=True).data,
        })


class AdminFeedbackUpdateView(AdminAPIView):
    def patch(self, request, feedback_id: int):
        fb = Feedback.objects.filter(id=feedback_id).first()
        if not fb:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        ser = FeedbackAdminUpdateSerializer(fb, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ser.save()
        return Response(FeedbackAdminSerializer(fb).data, status=status.HTTP_200_OK)
