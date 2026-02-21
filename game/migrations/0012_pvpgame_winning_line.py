from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0011_merge_20260221_0552"),
    ]

    operations = [
        migrations.AddField(
            model_name="pvpgame",
            name="winning_line",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
