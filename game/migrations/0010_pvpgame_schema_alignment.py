from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0009_pvp_invite_used_at"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="pvpgame",
                    old_name="player_x",
                    new_name="p1",
                ),
                migrations.RenameField(
                    model_name="pvpgame",
                    old_name="player_o",
                    new_name="p2",
                ),
                migrations.AlterField(
                    model_name="pvpgame",
                    name="p1",
                    field=models.ForeignKey(
                        db_column="player_x_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pvp_games_as_p1",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                migrations.AlterField(
                    model_name="pvpgame",
                    name="p2",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        db_column="player_o_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pvp_games_as_p2",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="pvpgame",
            name="invite_code",
            field=models.CharField(blank=True, db_index=True, max_length=16, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="pvpgame",
            name="status",
            field=models.CharField(
                choices=[("waiting", "Waiting"), ("active", "Active"), ("finished", "Finished")],
                default="waiting",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="pvpgame",
            name="result",
            field=models.CharField(
                choices=[("ongoing", "Ongoing"), ("p1_win", "P1 win"), ("p2_win", "P2 win"), ("draw", "Draw")],
                default="ongoing",
                max_length=16,
            ),
        ),
    ]
