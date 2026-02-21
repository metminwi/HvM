from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0005_matchqueueentry_matched_game"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RematchRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("game", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rematch_requests", to="game.pvpgame")),
                ("new_game", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rematch_origin_requests", to="game.pvpgame")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rematch_requests_sent", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["game", "status", "created_at"], name="game_rematch_game_id_3e15cd_idx")],
                "constraints": [models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("game",), name="uniq_pending_rematch_per_game")],
            },
        ),
    ]
