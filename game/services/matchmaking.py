from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from game.models import MatchQueueEntry, PvPGame, PlayerRating
from game.services.ws_notify import notify_user


@dataclass
class MatchResult:
    matched: bool
    game_id: int | None = None
    role: str | None = None  # "X" or "O"
    opponent_user_id: int | None = None


def _elo_window(waited_sec: int) -> int:
    """
    Progressive ELO window:
    50 -> 100 -> 200 -> 400 (cap)
    """
    base = 50
    growth = 10 * max(0, waited_sec)  # +10 ELO/sec (aggressive < 30s)
    return min(400, base + growth)


def _waited_seconds(entry: MatchQueueEntry) -> int:
    return int((timezone.now() - entry.created_at).total_seconds())


def _ensure_rating(user, mode: str) -> int:
    """
    Ensure a PlayerRating exists.
    Ranked needs rating; casual may ignore it.
    """
    rating, _ = PlayerRating.objects.get_or_create(user=user)
    return rating.elo_ranked


def try_match(entry_id: int) -> MatchResult:
    """
    Attempt to match the given waiting entry.
    Must be concurrency-safe (atomic + re-check status).
    """
    with transaction.atomic():
        entry = (
            MatchQueueEntry.objects
            .select_for_update()
            .filter(id=entry_id)
            .first()
        )

        if not entry:
            return MatchResult(matched=False)

        if entry.status != MatchQueueEntry.Status.WAITING:
            return MatchResult(matched=False)

        waited_a = _waited_seconds(entry)
        window = _elo_window(waited_a)

        candidates = (
            MatchQueueEntry.objects
            .select_for_update()
            .filter(
                mode=entry.mode,
                status=MatchQueueEntry.Status.WAITING,
            )
            .exclude(user_id=entry.user_id)
            .order_by("created_at")
        )

        best = None
        best_score = None

        for candidate in candidates:
            waited_b = _waited_seconds(candidate)
            window_b = _elo_window(min(waited_a, waited_b))
            allowed = max(window, window_b)

            diff = abs(
                (entry.elo_snapshot or 1200)
                - (candidate.elo_snapshot or 1200)
            )

            if diff > allowed:
                continue

            # Lower score is better:
            # prioritize closest ELO, then older waiting
            score = diff * 1000 - waited_b

            if best is None or score < best_score:
                best = candidate
                best_score = score

        if best is None:
            return MatchResult(matched=False)

        best = (
            MatchQueueEntry.objects
            .select_for_update()
            .filter(id=best.id)
            .first()
        )

        if not best or best.status != MatchQueueEntry.Status.WAITING:
            return MatchResult(matched=False)

        # Older entry gets X (FIFO fairness)
        a_is_x = entry.created_at <= best.created_at
        p1 = entry.user if a_is_x else best.user
        p2 = best.user if a_is_x else entry.user

        game = PvPGame.objects.create(
            p1=p1,
            p2=p2,
            mode=entry.mode,
            status=PvPGame.Status.ACTIVE,
            result=PvPGame.Result.ONGOING,
            turn="X",
            last_move_at=timezone.now(),
        )

        now = timezone.now()

        entry.status = MatchQueueEntry.Status.MATCHED
        entry.matched_at = now
        entry.matched_game = game
        entry.save(update_fields=["status", "matched_at", "matched_game"])

        best.status = MatchQueueEntry.Status.MATCHED
        best.matched_at = now
        best.matched_game = game
        best.save(update_fields=["status", "matched_at", "matched_game"])

        role = "X" if p1.id == entry.user_id else "O"
        opponent_id = p2.id if role == "X" else p1.id

        # WebSocket notifications
        notify_user(
            p1.id,
            {
                "type": "queue.matched",
                "game_id": game.id,
                "role": "X",
                "opponent_user_id": p2.id,
            },
        )

        notify_user(
            p2.id,
            {
                "type": "queue.matched",
                "game_id": game.id,
                "role": "O",
                "opponent_user_id": p1.id,
            },
        )

        return MatchResult(
            matched=True,
            game_id=game.id,
            role=role,
            opponent_user_id=opponent_id,
        )
