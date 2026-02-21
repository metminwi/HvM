# game/signals.py

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PlayerProfile

User = settings.AUTH_USER_MODEL

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_player_profile(sender, instance, created, **kwargs):
    """
    Automatically create a PlayerProfile whenever a new User is created.
    """
    if created:
        # Eviter doublons
        if not hasattr(instance, "player_profile"):
            PlayerProfile.objects.create(
                user=instance,
                display_name=instance.username or (instance.email or "Unknown"),
                player_type=PlayerProfile.PLAYER_TYPE_HUMAN,
            )
