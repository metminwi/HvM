# game/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class GameConsumer(AsyncWebsocketConsumer):
    """
    Room temps réel : ws://<host>/ws/game/<room_name>/
    Messages attendus (JSON):
      { "type": "move", "row": 7, "col": 7, "player": "X" }
      { "type": "reset" }
      { "type": "chat", "text": "hello" }
    """
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.group_name = f"gomoku_{self.room_name}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.channel_layer.group_send(self.group_name, {
            "type": "broadcast",
            "payload": {"system": f"joined:{self.channel_name}"}
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        # Re-broadcast à toute la room
        await self.channel_layer.group_send(self.group_name, {
            "type": "broadcast",
            "payload": data
        })

    async def broadcast(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
