from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0007_pvp_private_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pvpgame",
            name="invite_code",
            field=models.CharField(blank=True, db_index=True, max_length=32, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="pvpgame",
            name="invite_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pvpgame",
            name="invite_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
