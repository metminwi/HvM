from unittest.mock import patch

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from game.models import PvPGame


User = get_user_model()


class PvPPrivateInviteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(
            username="host_user",
            email="host@example.com",
            password="pass12345",
        )
        self.friend = User.objects.create_user(
            username="friend_user",
            email="friend@example.com",
            password="pass12345",
        )
        self.other = User.objects.create_user(
            username="other_user",
            email="other@example.com",
            password="pass12345",
        )

    def test_private_create_ok(self):
        self.client.force_authenticate(user=self.host)
        response = self.client.post(
            "/api/game/pvp/private/create/",
            {"mode": "casual"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("game_id", response.data)
        self.assertIn("invite_code", response.data)
        self.assertEqual(len(response.data["invite_code"]), 10)

        game = PvPGame.objects.get(id=response.data["game_id"])
        self.assertTrue(game.is_private)
        self.assertEqual(game.status, PvPGame.Status.WAITING)
        self.assertIsNone(game.p2_id)
        self.assertIsNotNone(game.invite_created_at)
        self.assertIsNotNone(game.invite_expires_at)
        self.assertGreater(game.invite_expires_at, game.invite_created_at)

    @patch("game.views_pvp_private.notify_game")
    @patch("game.views_pvp_private.notify_user")
    def test_private_join_ok(self, mock_notify_user, mock_notify_game):
        game = PvPGame.objects.create(
            p1=self.host,
            p2=None,
            mode=PvPGame.Mode.CASUAL,
            status=PvPGame.Status.WAITING,
            result=PvPGame.Result.ONGOING,
            is_private=True,
            invite_code="ABC12345",
        )

        self.client.force_authenticate(user=self.friend)
        response = self.client.post(
            "/api/game/pvp/private/join/",
            {"code": "abc12345"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"game_id": game.id})

        game.refresh_from_db()
        self.assertEqual(game.p2_id, self.friend.id)
        self.assertEqual(game.status, PvPGame.Status.ACTIVE)
        self.assertIsNotNone(game.invite_used_at)
        self.assertEqual(mock_notify_user.call_count, 2)
        mock_notify_game.assert_called_once_with(
            game.id,
            {"type": "player_joined", "game_id": game.id, "p2": self.friend.id},
        )

    def test_private_join_self_returns_game(self):
        game = PvPGame.objects.create(
            p1=self.host,
            p2=None,
            mode=PvPGame.Mode.CASUAL,
            status=PvPGame.Status.WAITING,
            result=PvPGame.Result.ONGOING,
            is_private=True,
            invite_code="SELF1234",
        )

        self.client.force_authenticate(user=self.host)
        response = self.client.post(
            "/api/game/pvp/private/join/",
            {"code": game.invite_code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"game_id": game.id})

    def test_private_join_already_filled_forbidden(self):
        game = PvPGame.objects.create(
            p1=self.host,
            p2=self.friend,
            mode=PvPGame.Mode.CASUAL,
            status=PvPGame.Status.ACTIVE,
            result=PvPGame.Result.ONGOING,
            is_private=True,
            invite_code="FULL1234",
        )

        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            "/api/game/pvp/private/join/",
            {"code": game.invite_code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_private_join_expired_invite_gone(self):
        game = PvPGame.objects.create(
            p1=self.host,
            p2=None,
            mode=PvPGame.Mode.CASUAL,
            status=PvPGame.Status.WAITING,
            result=PvPGame.Result.ONGOING,
            is_private=True,
            invite_code="EXPIRE01",
            invite_created_at=timezone.now() - timedelta(hours=2),
            invite_expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.client.force_authenticate(user=self.friend)
        response = self.client.post(
            "/api/game/pvp/private/join/",
            {"code": game.invite_code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
