from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Game, Move, Stats, PlayerProfile,Feedback,Game
import uuid

User = get_user_model()


def generate_username_from_email(email: str) -> str:
    base = email.split("@")[0][:20]
    candidate = base

    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}_{uuid.uuid4().hex[:4]}"

    return candidate


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    profile_type = serializers.CharField(required=False)
    main_goal = serializers.CharField(required=False)
    daily_training_minutes = serializers.IntegerField(required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "profile_type",
            "main_goal",
            "daily_training_minutes",
        )

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data.get("email")

        username = generate_username_from_email(email)

        user = User(
            username=username,
            email=email,
            profile_type=validated_data.get("profile_type", "adult"),
            main_goal=validated_data.get("main_goal", "think-better"),
            daily_training_minutes=validated_data.get("daily_training_minutes", 10),
        )

        user.set_password(password)
        user.save()
        return user

class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "profile_type",
            "main_goal",
            "daily_training_minutes",
            "premium",
            "is_staff",
            "is_superuser",
            "date_joined",
            "created_at",
        )

class GameStartSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Game.MODE_CHOICES)
    board_size = serializers.IntegerField(default=15)

    def create(self, validated_data):
        request = self.context.get("request")
        user = None
        if request and request.user.is_authenticated:
            user = request.user
        else:
            user = User.objects.order_by("-id").first()

        return Game.objects.create(
            player=user,
            mode=validated_data["mode"],
            board_size=validated_data.get("board_size", 15),
            result="ongoing",
        )



class GameStartResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ("id", "mode", "board_size", "result", "started_at")


class MoveCreateSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    col = serializers.IntegerField()
    player = serializers.ChoiceField(choices=[("X", "Human"), ("O", "AI")])

    def create(self, validated_data):
        game: Game = self.context["game"]
        move_number = game.moves.count() + 1
        return Move.objects.create(
            game=game,
            move_number=move_number,
            row=validated_data["row"],
            col=validated_data["col"],
            player=validated_data["player"],
        )


class GameEndSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=Game.RESULT_CHOICES)
    duration_sec = serializers.IntegerField(required=False, allow_null=True)

    def update(self, instance: Game, validated_data):
        from django.utils import timezone

        instance.result = validated_data["result"]
        if not instance.ended_at:
          instance.ended_at = timezone.now()
        instance.save()
        return instance



class DashboardSerializer(serializers.Serializer):
    games_played = serializers.IntegerField()
    wins_engine = serializers.IntegerField()
    wins_gemini = serializers.IntegerField()
    losses = serializers.IntegerField()
    draws = serializers.IntegerField()
    best_streak = serializers.IntegerField()
    current_streak = serializers.IntegerField()
    winrate = serializers.FloatField()

# game/serializers.py

class LeaderboardEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="display_name")

    # Stats globales (via Stats)
    games_played = serializers.SerializerMethodField()
    wins_engine = serializers.SerializerMethodField()
    wins_gemini = serializers.SerializerMethodField()
    losses = serializers.SerializerMethodField()
    best_streak = serializers.SerializerMethodField()

    # Stats filtrées par période (annotées dans la queryset)
    games_in_period = serializers.IntegerField(read_only=True)
    wins_in_period = serializers.IntegerField(read_only=True)

    # Badge calculé à partir du rating
    badge = serializers.SerializerMethodField()

    class Meta:
        model = PlayerProfile
        fields = [
            "id",
            "username",
            "player_type",
            "rating",
            "skill_tier",
            "badge",
            "games_played",
            "wins_engine",
            "wins_gemini",
            "losses",
            "best_streak",
            "games_in_period",
            "wins_in_period",
        ]

    def _get_stats(self, obj: PlayerProfile) -> Stats | None:
        if not obj.user_id:
            return None
        try:
            return obj.user.stats
        except Stats.DoesNotExist:
            return None

    def get_games_played(self, obj):
        stats = self._get_stats(obj)
        return stats.games_played if stats else 0

    def get_wins_engine(self, obj):
        stats = self._get_stats(obj)
        return stats.wins_engine if stats else 0

    def get_wins_gemini(self, obj):
        stats = self._get_stats(obj)
        return stats.wins_gemini if stats else 0

    def get_losses(self, obj):
        stats = self._get_stats(obj)
        return stats.losses if stats else 0

    def get_best_streak(self, obj):
        stats = self._get_stats(obj)
        return stats.best_streak if stats else 0

    def get_badge(self, obj):
        """
        Mappe le rating vers un badge symbolique.
        """
        rating = obj.rating or 0
        if rating >= 2200:
            return "legend"
        elif rating >= 1900:
            return "gold"
        elif rating >= 1600:
            return "silver"
        else:
            return "bronze"
# game/serializers.py

class RecentGameV2Serializer(serializers.Serializer):
    id = serializers.IntegerField()
    mode = serializers.ChoiceField(choices=["engine", "gemini"])
    result = serializers.ChoiceField(choices=["win", "lose", "draw"])
    duration_sec = serializers.FloatField(allow_null=True)
    avg_eval_score = serializers.FloatField(allow_null=True)
    avg_depth = serializers.FloatField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)


class DetailedDashboardV2Serializer(serializers.Serializer):
    games_played = serializers.IntegerField()
    wins_engine = serializers.IntegerField()
    wins_gemini = serializers.IntegerField()
    losses = serializers.IntegerField()
    draws = serializers.IntegerField()
    best_streak = serializers.IntegerField()
    current_streak = serializers.IntegerField()

    winrate = serializers.FloatField()
    avg_duration_sec = serializers.FloatField(allow_null=True)
    avg_eval_score = serializers.FloatField(allow_null=True)
    avg_depth = serializers.FloatField(allow_null=True)

    engine_winrate = serializers.FloatField()
    gemini_winrate = serializers.FloatField()

    recent_games = RecentGameV2Serializer(many=True)



class FeedbackCreateSerializer(serializers.ModelSerializer):
    game_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Feedback
        fields = ["type", "rating", "message", "engine", "page", "game_id"]

    def validate_rating(self, v):
        if v is None:
            return v
        if v < 1 or v > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return v

    def validate(self, attrs):
        # si type=rating, on veut idéalement rating
        if attrs.get("type") == Feedback.FeedbackType.RATING and attrs.get("rating") is None:
            raise serializers.ValidationError({"rating": "Rating is required when type=rating."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        game_id = validated_data.pop("game_id", None)

        game = None
        if game_id:
            game = Game.objects.filter(id=game_id).first()

        fb = Feedback.objects.create(
            user=request.user if request.user.is_authenticated else None,
            game=game,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255] or None,
            **validated_data,
        )
        return fb


class FeedbackAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    game_ref = serializers.IntegerField(source="game.id", read_only=True)

    class Meta:
        model = Feedback
        fields = [
            "id", "created_at", "type", "status", "rating", "message",
            "engine", "page", "user_agent",
            "username", "email", "game_ref",
        ]


class FeedbackAdminUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=Feedback.FeedbackStatus.choices,
        required=False,
    )
    type = serializers.ChoiceField(
        choices=Feedback.FeedbackType.choices,
        required=False,
    )
    rating = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(required=False)

    def validate_rating(self, value):
        if value is None:
            return value
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    class Meta:
        model = Feedback
        fields = ["status", "type", "rating", "message"]



class MoveStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Move
        fields = ["move_number", "player", "row", "col", "created_at"]

class GameStateSerializer(serializers.ModelSerializer):
    moves = MoveStateSerializer(many=True, read_only=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "mode",
            "difficulty",
            "board_size",
            "ranked",
            "status",
            "result",
            "created_at",
            "ended_at",
            "moves",
        ]


class PvPMoveStateSerializer(serializers.Serializer):
    move_number = serializers.IntegerField()
    player = serializers.CharField()
    row = serializers.IntegerField()
    col = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class PvPUserRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class PvPGameStateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    result = serializers.CharField()
    winning_line = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField(), min_length=2, max_length=2),
        allow_empty=True,
    )
    turn = serializers.CharField()
    board_size = serializers.IntegerField()
    moves = PvPMoveStateSerializer(many=True)
    me = PvPUserRefSerializer()
    p1 = PvPUserRefSerializer()
    p2 = PvPUserRefSerializer(allow_null=True)
    p1_username = serializers.CharField()
    p2_username = serializers.CharField(allow_null=True)
    your_symbol = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Guardrail: never expose "finished" unless DB indicates it.
        if data.get("status") == "finished" and data.get("result") == "ongoing":
            data["status"] = "active"
        return data


class PvPHeadToHeadSerializer(serializers.Serializer):
    total_games = serializers.IntegerField()
    p1_wins = serializers.IntegerField()
    p2_wins = serializers.IntegerField()
    draws = serializers.IntegerField()
class ProfileUpdateSerializer(serializers.ModelSerializer):
    # On évite de toucher username/email si tu veux garder ça stable.
    # Si tu veux autoriser email plus tard, on le fera proprement.
    class Meta:
        model = User
        fields = (
            "profile_type",
            "main_goal",
            "daily_training_minutes",
        )
    def validate_daily_training_minutes(self, v):
        if v is None:
            return v
        if v < 1 or v > 180:
            raise serializers.ValidationError("daily_training_minutes must be between 1 and 180.")
        return v
