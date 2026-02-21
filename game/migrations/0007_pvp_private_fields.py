from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0006_rematchrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="pvpgame",
            name="invite_code",
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="pvpgame",
            name="is_private",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="pvpgame",
            name="player_o",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="pvp_games_as_o", to="game.user"),
        ),
        migrations.AlterField(
            model_name="pvpgame",
            name="status",
            field=models.CharField(choices=[("waiting", "Waiting"), ("active", "Active"), ("finished", "Finished"), ("abandoned", "Abandoned")], default="active", max_length=16),
        ),
    ]
