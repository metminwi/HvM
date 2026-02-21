from __future__ import annotations
# game/services.py

from django.db.models import QuerySet
from .models import Game, Stats, User, PlayerProfile, Move
from django.db.models import Avg, Count, Q


from datetime import timedelta
from django.utils import timezone
from django.conf import settings

from typing import Dict, Any, List


def recompute_stats_for_user(user: User) -> Stats:
    """
    Recalcule les stats globales d’un joueur à partir de la table Game.
    On ignore les parties encore en cours.
    """
    qs: QuerySet[Game] = Game.objects.filter(player=user).exclude(result="ongoing")

    games_played = qs.count()

    wins_engine = qs.filter(mode="engine", result="win").count()
    wins_gemini = qs.filter(mode="gemini", result="win").count()
    losses = qs.filter(result="lose").count()
    draws = qs.filter(result="draw").count()

    # Streaks : on parcourt les games dans l'ordre chronologique
    ordered_results = qs.order_by("started_at").values_list("result", flat=True)

    best_streak = 0
    current_streak = 0
    for res in ordered_results:
        if res == "win":
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 0

    stats, _ = Stats.objects.get_or_create(user=user)
    stats.games_played = games_played
    stats.wins_engine = wins_engine
    stats.wins_gemini = wins_gemini
    stats.losses = losses
    stats.draws = draws
    stats.best_streak = best_streak
    stats.current_streak = current_streak
    stats.save()

    return stats


def get_dashboard_payload(user: User) -> dict:
    """
    Construit le payload prêt pour DashboardSerializer.
    """
    stats = recompute_stats_for_user(user)

    total_wins = stats.wins_engine + stats.wins_gemini
    if stats.games_played > 0:
        winrate = round((total_wins / stats.games_played) * 100, 1)
    else:
        winrate = 0.0

    payload = {
        "games_played": stats.games_played,
        "wins_engine": stats.wins_engine,
        "wins_gemini": stats.wins_gemini,
        "losses": stats.losses,
        "draws": stats.draws,
        "best_streak": stats.best_streak,
        "current_streak": stats.current_streak,
        "winrate": winrate,
    }
    return payload
def get_detailed_dashboard_payload(user: User) -> dict:
    """
    Version détaillée du dashboard :
    - summary : mêmes champs que /api/dashboard/
    - by_mode : stats séparées ENGINE / GEMINI
    - durations : durées moyennes, calculées à partir de started_at / ended_at
    - recent_games : 10 dernières parties
    """

    # Résumé global (ta fonction existante)
    summary = get_dashboard_payload(user)

    qs = Game.objects.filter(player=user).exclude(result="ongoing")

    # ---- Stats par mode ----
    def mode_block(mode: str) -> dict:
        qsm = qs.filter(mode=mode)
        games = qsm.count()
        wins = qsm.filter(result="win").count()
        losses = qsm.filter(result="lose").count()
        draws = qsm.filter(result="draw").count()
        winrate = round((wins / games) * 100, 1) if games > 0 else 0.0
        return {
            "games": games,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "winrate": winrate,
        }

    by_mode = {
        "engine": mode_block("engine"),
        "gemini": mode_block("gemini"),
    }

    # ---- Durées : on calcule en Python à partir de started_at / ended_at ----
    def avg_duration(qs_subset) -> int:
        durations = []
        for g in qs_subset:
            if g.started_at and g.ended_at:
                delta = g.ended_at - g.started_at
                durations.append(delta.total_seconds())
        if not durations:
            return 0
        return int(sum(durations) / len(durations))

    durations = {
        "average_duration_sec": avg_duration(qs),
        "average_win_duration_sec": avg_duration(qs.filter(result="win")),
        "average_loss_duration_sec": avg_duration(qs.filter(result="lose")),
    }

    # ---- 10 dernières parties ----
    recent_games_qs = qs.order_by("-started_at")[:10]
    recent_games = [
        {
            "id": g.id,
            "mode": g.mode,
            "result": g.result,
            "duration_sec": (
                (g.ended_at - g.started_at).total_seconds()
                if g.started_at and g.ended_at
                else None
            ),
            "started_at": g.started_at,
            "ended_at": g.ended_at,
        }
        for g in recent_games_qs
    ]

    return {
        "summary": summary,
        "by_mode": by_mode,
        "durations": durations,
        "recent_games": recent_games,
    }
# game/services.py

ENGINE_RATING = 1500
GEMINI_RATING = 1650


def _get_period_start(period: str):
    """
    Return a datetime start bound for the given period, or None for 'global'.
    """
    if period == "global":
        return None

    now = timezone.now()

    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        return now - timedelta(days=7)
    elif period == "month":
        return now - timedelta(days=30)

    return None


def _get_or_create_stats_and_profile(user: User) -> tuple[Stats, PlayerProfile]:
    stats, _ = Stats.objects.get_or_create(user=user)

    profile, created = PlayerProfile.objects.get_or_create(
        user=user,
        defaults={
            "display_name": user.username or user.email or f"user-{user.pk}",
            "player_type": PlayerProfile.PLAYER_TYPE_HUMAN,
            "rating": 1200,
        },
    )
    if not profile.display_name:
        profile.display_name = user.username or user.email or f"user-{user.pk}"
    return stats, profile


def _skill_from_rating(rating: int) -> str:
    if rating >= 2000:
        return PlayerProfile.SKILL_EXPERT
    if rating >= 1700:
        return PlayerProfile.SKILL_INTERMEDIATE
    return PlayerProfile.SKILL_BEGINNER


def _elo_update(current_rating: int, opponent_rating: int, score: float) -> int:
    if current_rating < 1800:
        k = 32
    elif current_rating < 2200:
        k = 24
    else:
        k = 16

    expected = 1.0 / (1.0 + 10 ** ((opponent_rating - current_rating) / 400))
    new_rating = current_rating + k * (score - expected)
    return max(800, int(round(new_rating)))


def update_stats_for_finished_game(game: Game) -> None:
    user = game.player
    if not user or game.result == "ongoing":
        return

    stats, profile = _get_or_create_stats_and_profile(user)

    # 1) Stats globales
    stats.games_played += 1

    if game.result == "win":
        if game.mode == "engine":
            stats.wins_engine += 1
        elif game.mode == "gemini":
            stats.wins_gemini += 1

        stats.current_streak += 1
        if stats.current_streak > stats.best_streak:
            stats.best_streak = stats.current_streak

    elif game.result == "lose":
        stats.losses += 1
        stats.current_streak = 0

    elif game.result == "draw":
        stats.draws += 1
        stats.current_streak = 0

    stats.updated_at = timezone.now()
    stats.save()

    # 2) Elo global
    if game.mode == "engine":
        opp_rating = ENGINE_RATING
    elif game.mode == "gemini":
        opp_rating = GEMINI_RATING
    else:
        opp_rating = 1500

    if game.result == "win":
        score = 1.0
    elif game.result == "draw":
        score = 0.5
    else:
        score = 0.0

    new_rating = _elo_update(profile.rating, opp_rating, score)
    profile.rating = new_rating
    profile.skill_tier = _skill_from_rating(new_rating)
    profile.current_streak = stats.current_streak
    profile.last_played = timezone.now()
    profile.save()
# game/services.py

# game/services.py


def _empty_detailed_dashboard_v2() -> Dict[str, Any]:
    """
    Payload vide / par défaut pour le dashboard v2.
    Tous les nombres sont 0 et pas de NaN -> React est content.
    """
    return {
        "games_played": 0,
        "wins_engine": 0,
        "wins_gemini": 0,
        "losses": 0,
        "draws": 0,
        "best_streak": 0,
        "current_streak": 0,
        "winrate": 0.0,
        "avg_duration_sec": None,
        "avg_eval_score": None,
        "avg_depth": None,
        "engine_winrate": 0.0,
        "gemini_winrate": 0.0,
        "recent_games": [],
    }


def _safe_winrate(wins: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * wins / total, 1)


def get_detailed_dashboard_v2(user: Optional[User]) -> Dict[str, Any]:
    """
    Version clean / robuste pour le nouveau dashboard graphique HvM.
    - Ne dépend que de Game + Stats.
    - Aucun calcul ne renvoie NaN.
    """
    if not user:
        return _empty_detailed_dashboard_v2()

    # Parties terminées & rankées
    games_qs = (
        Game.objects.filter(
            player=user,
            ranked=True,
            ended_at__isnull=False,
            result__in=["win", "lose", "draw"],
        )
        .order_by("-ended_at")
        .select_related("player")
    )

    games_played = games_qs.count()

    engine_games = games_qs.filter(mode="engine")
    gemini_games = games_qs.filter(mode="gemini")

    wins_engine = engine_games.filter(result="win").count()
    wins_gemini = gemini_games.filter(result="win").count()
    losses = games_qs.filter(result="lose").count()
    draws = games_qs.filter(result="draw").count()

    total_wins = wins_engine + wins_gemini

    # Streaks depuis Stats si dispo
    stats_obj = Stats.objects.filter(user=user).first()
    best_streak = stats_obj.best_streak if stats_obj else 0
    current_streak = stats_obj.current_streak if stats_obj else 0

    # Winrates
    winrate = _safe_winrate(total_wins, games_played)
    engine_winrate = _safe_winrate(wins_engine, engine_games.count())
    gemini_winrate = _safe_winrate(wins_gemini, gemini_games.count())

    # Durée moyenne (si le champ existe)
    avg_duration = None
    if hasattr(Game, "duration_sec"):
        avg_duration = games_qs.aggregate(
            avg_duration=Avg("duration_sec")
        )["avg_duration"]

    # Pour l'instant on ne remonte PAS les stats IA (eval_score / depth)
    avg_eval_score = None
    avg_depth = None

    # Parties récentes (on envoie tout ce qu’il faut pour le front)
    recent_qs = games_qs[:20]

    recent_games: List[Dict[str, Any]] = []
    for g in recent_qs:
        recent_games.append(
            {
                "id": g.id,
                "mode": g.mode,          # "engine" | "gemini"
                "result": g.result,      # "win" | "lose" | "draw"
                "duration_sec": getattr(g, "duration_sec", None),
                "avg_eval_score": None,  # à remplir plus tard quand on remettra Move
                "avg_depth": None,       # idem
                "started_at": (
                    g.started_at.isoformat()
                    if getattr(g, "started_at", None)
                    else None
                ),
            }
        )

    return {
        "games_played": games_played,
        "wins_engine": wins_engine,
        "wins_gemini": wins_gemini,
        "losses": losses,
        "draws": draws,
        "best_streak": best_streak,
        "current_streak": current_streak,
        "winrate": winrate,
        "avg_duration_sec": float(avg_duration) if avg_duration is not None else None,
        "avg_eval_score": avg_eval_score,
        "avg_depth": avg_depth,
        "engine_winrate": engine_winrate,
        "gemini_winrate": gemini_winrate,
        "recent_games": recent_games,
    }
