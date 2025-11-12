"""
ASGI config for HvM project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

# HvM/asgi.py (remplace "HvM" si ton dossier projet porte un autre nom)
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from game.consumers import GameConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HvM.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path("ws/game/<str:room_name>/", GameConsumer.as_asgi()),
    ]),
})

