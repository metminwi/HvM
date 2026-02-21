# game/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class GameConsumer(AsyncWebsocketConsumer):
    """
    Legacy room realtime: ws://<host>/ws/game/<room_name>/
    """
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.group_name = f"gomoku_{self.room_name}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        await self.channel_layer.group_send(self.group_name, {
            "type": "broadcast",
            "payload": data
        })

    async def broadcast(self, event):
        await self.send(text_data=json.dumps(event["payload"]))




class LobbyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user = user
        self.group_name = "pvp_lobby"
        self.user_group = f"user_{user.id}"  # ✅ important

        # Lobby group (optional, for queue-wide broadcast)
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Per-user group (for direct notifications: queue.matched)
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        await self.accept()

        await self.send_json({
            "type": "lobby.connected",
            "user": user.username,
            "user_id": user.id,
        })

    async def disconnect(self, close_code):
        # safe discard
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """
        Receive messages from client.
        Supports:
        - ping
        - game.join (subscribe to pvp_game_<id>)
        - game.leave
        """
        msg_type = content.get("type")

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

        if msg_type == "game.join":
            game_id = content.get("game_id")
            if not game_id:
                await self.send_json({"type": "error", "detail": "Missing game_id"})
                return

            group = f"pvp_game_{int(game_id)}"
            await self.channel_layer.group_add(group, self.channel_name)

            await self.send_json({"type": "game.joined", "game_id": int(game_id)})
            return

        if msg_type == "game.leave":
            game_id = content.get("game_id")
            if not game_id:
                return

            group = f"pvp_game_{int(game_id)}"
            await self.channel_layer.group_discard(group, self.channel_name)
            return

    # -------- events from server (group_send) --------

    async def queue_event(self, event):
        """
        Server -> user_<id> group notifications (match found, queue updates).
        event = {"type":"queue_event","payload": {...}}
        """
        payload = event.get("payload") or {}
        await self.send_json(payload)

    async def game_event(self, event):
        """
        Server -> pvp_game_<id> group notifications (moves, turns, ended).
        event = {"type":"game_event","payload": {...}}
        """
        payload = event.get("payload") or {}
        await self.send_json(payload)
