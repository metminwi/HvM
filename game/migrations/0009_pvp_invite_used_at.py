from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0008_pvp_invite_timestamps"),
    ]

    operations = [
        migrations.AddField(
            model_name="pvpgame",
            name="invite_used_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
