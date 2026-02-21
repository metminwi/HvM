from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
import secrets
import string

from django.utils import timezone
# ==========================
# CUSTOM USER (HvM player)
# ==========================

class User(AbstractUser):
    """
    Custom user aligned with your `users` table + cognitive onboarding fields.
    """

    # AbstractUser already provides:
    # - username (unique)
    # - password
    # - email
    # - first_name, last_name, etc.

    avatar = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="URL or path to avatar image.",
    )
    premium = models.BooleanField(default=False)

    class ProfileType(models.TextChoices):
        CHILD = "child", "Child (8–12)"
        TEEN = "teen", "Teen (13–17)"
        ADULT = "adult", "Adult"
        EDUCATOR = "educator", "Educator / Parent"

    profile_type = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        default=ProfileType.ADULT,
    )

    class MainGoal(models.TextChoices):
        THINK_BETTER = "think-better", "Think better"
        SCHOOL = "school", "School & exams"
        CAREER = "career", "Career & decisions"
        FAMILY = "family", "Family & learning"

    main_goal = models.CharField(
        max_length=30,
        choices=MainGoal.choices,
        default=MainGoal.THINK_BETTER,
    )

    DAILY_CHOICES = (
        (5, "5 minutes"),
        (10, "10 minutes"),
        (20, "20 minutes"),
    )

    daily_training_minutes = models.PositiveSmallIntegerField(
        choices=DAILY_CHOICES,
        default=10,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"  # pour matcher ta table SQL existante
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return self.username or self.email


# ==========================
# GAME & MOVES
# ==========================

""" class Game(models.Model):
    # ✅ remets ces deux constantes de choix
    MODE_CHOICES = [
        ("engine", "Engine"),
        ("gemini", "Gemini"),
    ]

    RESULT_CHOICES = [
        ("win", "Win"),
        ("lose", "Lose"),
        ("draw", "Draw"),
        ("ongoing", "Ongoing"),
    ]

    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="games",
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    result = models.CharField(
        max_length=10,
        choices=RESULT_CHOICES,
        default="ongoing",
    )
    board_size = models.IntegerField(default=15)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    ranked = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Game #{self.id} ({self.mode})"

    class Meta:
        db_table = "games"
        indexes = [
            models.Index(fields=["player"]),
            models.Index(fields=["mode"]),
        ]

    def __str__(self):
        return f"Game #{self.pk} ({self.mode}) - {self.player}" 
 """

""" class Move(models.Model):
    PLAYER_CHOICES = [
        ("X", "Human"),
        ("O", "AI"),
    ]

    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="moves"
    )
    move_number = models.IntegerField()
    row = models.IntegerField()
    col = models.IntegerField()
    player = models.CharField(max_length=1, choices=PLAYER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    # 🔥 Nouveau : score Minimax vu du point de vue de l’IA
    eval_score = models.IntegerField(
        null=True, blank=True,
        help_text="Évaluation Minimax après ce coup (score côté IA)."
    )
    eval_depth = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Profondeur maximale utilisée pour ce coup."
    )

    class Meta:
        unique_together = ("game", "move_number")  """



# ==========================
# SKINS
# ==========================

class Skin(models.Model):
    class Category(models.TextChoices):
        BOARD = "board", "Board"
        STONE = "stone", "Stone"
        EFFECT = "effect", "Effect"

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=30, choices=Category.choices)
    description = models.TextField(blank=True)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "skins"

    def __str__(self):
        return self.name


class UserSkin(models.Model):
    class Source(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        REWARD = "reward", "Reward"
        STARTER = "starter", "Starter"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_skins",
    )
    skin = models.ForeignKey(
        Skin,
        on_delete=models.CASCADE,
        related_name="owners",
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(
        max_length=50,
        choices=Source.choices,
        default=Source.STARTER,
    )

    class Meta:
        db_table = "user_skins"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skin"],
                name="unique_skin_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user} owns {self.skin}"


# ==========================
# SUBSCRIPTIONS
# ==========================

class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELED = "canceled", "Canceled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan_name = models.CharField(max_length=50)  # e.g. "hvm_pro_monthly"
    status = models.CharField(max_length=20, choices=Status.choices)
    started_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    external_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Stripe or external subscription ID",
    )
    auto_renew = models.BooleanField(default=True)

    class Meta:
        db_table = "subscriptions"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.plan_name} ({self.status})"


# ==========================
# STATS
# ==========================

class Stats(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stats",
    )
    games_played = models.PositiveIntegerField(default=0)
    wins_engine = models.PositiveIntegerField(default=0)
    wins_gemini = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    best_streak = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stats"

    def __str__(self):
        return f"Stats for {self.user}"

# game/models.py

class PlayerProfile(models.Model):
    """Represents a player in HvM (human or AI agent)."""

    PLAYER_TYPE_HUMAN = "human"
    PLAYER_TYPE_AI = "ai"
    PLAYER_TYPE_CHOICES = [
        (PLAYER_TYPE_HUMAN, "Human"),
        (PLAYER_TYPE_AI, "AI"),
    ]

    SKILL_BEGINNER = "beginner"
    SKILL_INTERMEDIATE = "intermediate"
    SKILL_EXPERT = "expert"
    SKILL_CHOICES = [
        (SKILL_BEGINNER, "Beginner"),
        (SKILL_INTERMEDIATE, "Intermediate"),
        (SKILL_EXPERT, "Expert"),
    ]

    # null user = AI bot or guest
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="player_profile",
    )

    display_name = models.CharField(max_length=50, unique=True)
    player_type = models.CharField(
        max_length=10, choices=PLAYER_TYPE_CHOICES, default=PLAYER_TYPE_HUMAN
    )

    # "gradient_1" or full URL if you want
    avatar = models.CharField(max_length=100, blank=True)

    # Rating / tier
    rating = models.IntegerField(default=1200)  # ELO-like score
    skill_tier = models.CharField(
        max_length=20, choices=SKILL_CHOICES, default=SKILL_BEGINNER
    )

    # JSON list of badge IDs: ["fire_streak", "legend", ...]
    badges = models.JSONField(default=list, blank=True)
    current_streak = models.PositiveIntegerField(default=0)
    last_played = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-rating"]

    def __str__(self):
        return self.display_name


# game/models.py

# game/models.py (remplace uniquement Game + Move)




class Game(models.Model):
    # ✅ remets ces deux constantes de choix
    MODE_CHOICES = [
        ("engine", "Engine"),
        ("gemini", "Gemini"),
        ("openspiel", "OpenSpiel"),
    ]

    RESULT_CHOICES = [
        ("win", "Win"),
        ("loss", "Loss"),
        ("draw", "Draw"),
        ("ongoing", "Ongoing"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Game config
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    difficulty = models.CharField(max_length=20, default="standard")
    board_size = models.IntegerField(default=15)
    ranked = models.BooleanField(default=False)

    # Status / result
    status = models.CharField(max_length=20, default="active")  # active | finished
    result = models.CharField(
        max_length=20, choices=RESULT_CHOICES, default="ongoing"
    )  # ongoing | win | loss | draw

    created_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Game#{self.id} {self.mode}/{self.difficulty} {self.result}"
    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["result", "created_at"]),
            models.Index(fields=["mode", "created_at"]),
        ]

class Move(models.Model):
    PLAYER_CHOICES = [
        ("X", "Human"),
        ("O", "AI"),
    ]
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="moves")
    move_number = models.IntegerField()
    player = models.CharField(max_length=1)  # "X" or "O"
    row = models.IntegerField()
    col = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "game_move"
        # Protect ordering AND cell occupancy (you already had the SQLite constraint)
        unique_together = (
            ("game", "move_number"),
            ("game", "row", "col"),
        )
        ordering = ["move_number"]

    def __str__(self):
        return f"Move#{self.move_number} {self.player}@({self.row},{self.col})"
        indexes = [
            models.Index(fields=["game", "move_number"]),
            models.Index(fields=["game", "row", "col"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["game", "row", "col"], name="uniq_game_cell"),
        ]


class Feedback(models.Model):
    class FeedbackType(models.TextChoices):
        BUG = "bug", "Bug"
        IDEA = "idea", "Idea"
        RATING = "rating", "Rating"
        OTHER = "other", "Other"

    class FeedbackStatus(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"
        RESOLVED = "resolved", "Resolved"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
    )

    # optionnel: relier à une partie
    game = models.ForeignKey(
        "game.Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
    )

    type = models.CharField(max_length=16, choices=FeedbackType.choices, default=FeedbackType.OTHER)
    status = models.CharField(max_length=16, choices=FeedbackStatus.choices, default=FeedbackStatus.NEW)

    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1..5
    message = models.TextField()

    # contexte optionnel
    engine = models.CharField(max_length=16, null=True, blank=True)      # engine|gemini|openspiel
    page = models.CharField(max_length=64, null=True, blank=True)        # play-ai, dashboard...
    user_agent = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Feedback({self.id}) {self.type} {self.status}"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["type", "created_at"]),
        ]

# game/models.py


class PlayerRating(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rating")

    elo_ranked = models.IntegerField(default=1200)
    games_ranked = models.IntegerField(default=0)
    wins_ranked = models.IntegerField(default=0)
    losses_ranked = models.IntegerField(default=0)
    draws_ranked = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rating(user={self.user_id}, elo={self.elo_ranked})"


class MatchQueueEntry(models.Model):
    class Mode(models.TextChoices):
        CASUAL = "casual", "Casual"
        RANKED = "ranked", "Ranked"

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        MATCHED = "matched", "Matched"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="queue_entries")

    mode = models.CharField(max_length=16, choices=Mode.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)

    elo_snapshot = models.IntegerField(default=1200)
    preferences = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    matched_game = models.ForeignKey("game.PvPGame", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [
            models.Index(fields=["mode", "status", "created_at"]),
            models.Index(fields=["mode", "status", "elo_snapshot"]),
        ]

    def __str__(self):
        return f"QueueEntry(user={self.user_id}, mode={self.mode}, status={self.status})"


class PvPGame(models.Model):
    class Mode(models.TextChoices):
        CASUAL = "casual", "Casual"
        RANKED = "ranked", "Ranked"

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ACTIVE = "active", "Active"
        FINISHED = "finished", "Finished"

    class Result(models.TextChoices):
        ONGOING = "ongoing", "Ongoing"
        P1_WIN = "p1_win", "P1 win"
        P2_WIN = "p2_win", "P2 win"
        DRAW = "draw", "Draw"

    p1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pvp_games_as_p1",
        db_column="player_x_id",
    )
    p2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pvp_games_as_p2",
        null=True,
        blank=True,
        db_column="player_o_id",
    )

    mode = models.CharField(max_length=16, choices=Mode.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)
    result = models.CharField(max_length=16, choices=Result.choices, default=Result.ONGOING)
    winning_line = models.JSONField(null=True, blank=True)
    is_private = models.BooleanField(default=False)
    invite_code = models.CharField(max_length=16, unique=True, db_index=True, null=True, blank=True)
    invite_created_at = models.DateTimeField(null=True, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    invite_used_at = models.DateTimeField(null=True, blank=True)

    board_size = models.IntegerField(default=15)
    turn = models.CharField(max_length=1, default="X")  # "X" or "O"

    started_at = models.DateTimeField(auto_now_add=True)
    last_move_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    turn_timeout_sec = models.IntegerField(default=30)  # ranked/casual can override later
    time_control = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"PvPGame(id={self.id}, mode={self.mode}, status={self.status})"

    @classmethod
    def generate_unique_invite_code(cls, length: int = 10) -> str:
        if length < 8:
            length = 8
        if length > 12:
            length = 12
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(64):
            code = "".join(secrets.choice(alphabet) for _ in range(length))
            if not cls.objects.filter(invite_code=code).exists():
                return code
        raise RuntimeError("Unable to generate unique invite code.")


class PvPMove(models.Model):
    game = models.ForeignKey(PvPGame, on_delete=models.CASCADE, related_name="moves")

    move_number = models.IntegerField()
    player = models.CharField(max_length=1)  # "X" or "O"
    row = models.IntegerField()
    col = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["game", "row", "col"], name="uniq_pvp_game_cell"),
            models.UniqueConstraint(fields=["game", "move_number"], name="uniq_pvp_game_move_number"),
        ]
        indexes = [
            models.Index(fields=["game", "move_number"]),
            models.Index(fields=["game", "row", "col"]),
        ]

    def __str__(self):
        return f"PvPMove(game={self.game_id}, n={self.move_number}, p={self.player}, {self.row},{self.col})"


class RematchRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    game = models.ForeignKey(PvPGame, on_delete=models.CASCADE, related_name="rematch_requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rematch_requests_sent",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    new_game = models.ForeignKey(
        PvPGame,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rematch_origin_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game"],
                condition=models.Q(status="pending"),
                name="uniq_pending_rematch_per_game",
            ),
        ]
        indexes = [
            models.Index(fields=["game", "status", "created_at"]),
        ]

    def __str__(self):
        return f"RematchRequest(game={self.game_id}, requester={self.requester_id}, status={self.status})"
