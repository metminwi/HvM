import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from game.models import PvPGame
from game.services.ws_notify import notify_game

class Command(BaseCommand):
    help = "PvP timeout worker (dev). Checks active games and ends on timeout."

    def handle(self, *args, **options):
        self.stdout.write("PvP timeout worker started…")
        while True:
            now = timezone.now()
            active = PvPGame.objects.filter(status=PvPGame.Status.ACTIVE)

            for g in active:
                last = g.last_move_at or g.started_at
                if (now - last).total_seconds() > g.turn_timeout_sec:
                    # current turn player times out -> other wins
                    g.status = PvPGame.Status.FINISHED
                    g.ended_at = now
                    if g.turn == "X":
                        g.result = PvPGame.Result.P2_WIN
                    else:
                        g.result = PvPGame.Result.P1_WIN
                    g.save()

                    notify_game(g.id, {
                        "type": "game.ended",
                        "game_id": g.id,
                        "result": g.result,
                        "reason": "timeout",
                        "turn": g.turn,
                    })

            time.sleep(2)
