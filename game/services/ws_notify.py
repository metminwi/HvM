from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def notify_user(user_id: int, payload: dict):
    """
    Push event to a specific user group user_<id>
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {"type": "queue_event", "payload": payload},
    )


def notify_game(game_id: int, payload: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"pvp_game_{game_id}",
        {"type": "game_event", "payload": payload},
    )


def notify_lobby(payload: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "pvp_lobby",
        {"type": "queue_event", "payload": payload},
    )
