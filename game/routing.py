from django.urls import re_path
from .consumers import LobbyConsumer, GameConsumer

websocket_urlpatterns = [
    re_path(r"ws/lobby/$", LobbyConsumer.as_asgi()),
    
]
