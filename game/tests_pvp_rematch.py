from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from game.models import PvPGame, RematchRequest


User = get_user_model()


class PvPRematchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player_x = User.objects.create_user(
            username="pvp_x",
            email="pvp_x@example.com",
            password="pass12345",
        )
        self.player_o = User.objects.create_user(
            username="pvp_o",
            email="pvp_o@example.com",
            password="pass12345",
        )
        self.other_user = User.objects.create_user(
            username="pvp_other",
            email="pvp_other@example.com",
            password="pass12345",
        )
        self.finished_game = PvPGame.objects.create(
            p1=self.player_x,
            p2=self.player_o,
            mode=PvPGame.Mode.CASUAL,
            status=PvPGame.Status.FINISHED,
            result=PvPGame.Result.P1_WIN,
            board_size=15,
            turn="X",
        )

    def test_rematch_request_non_participant_forbidden(self):
        self.client.force_authenticate(user=self.other_user)
        url = f"/api/game/pvp/games/{self.finished_game.id}/rematch/request/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("game.views_pvp_game.notify_user")
    def test_rematch_request_ok_sends_ws(self, mock_notify_user):
        self.client.force_authenticate(user=self.player_x)
        url = f"/api/game/pvp/games/{self.finished_game.id}/rematch/request/"
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ok"], True)
        rematch = RematchRequest.objects.get(game=self.finished_game, status=RematchRequest.Status.PENDING)
        self.assertEqual(rematch.requester_id, self.player_x.id)
        mock_notify_user.assert_called_once_with(
            self.player_o.id,
            {
                "type": "game.rematch.requested",
                "game_id": self.finished_game.id,
                "requester_id": self.player_x.id,
            },
        )

    @patch("game.views_pvp_game.notify_user")
    def test_rematch_accept_creates_new_game_and_returns_id(self, mock_notify_user):
        RematchRequest.objects.create(
            game=self.finished_game,
            requester=self.player_x,
            status=RematchRequest.Status.PENDING,
        )
        self.client.force_authenticate(user=self.player_o)
        url = f"/api/game/pvp/games/{self.finished_game.id}/rematch/accept/"
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ok"], True)
        self.assertIn("new_game_id", response.data)

        new_game = PvPGame.objects.get(id=response.data["new_game_id"])
        self.assertEqual(new_game.mode, self.finished_game.mode)
        self.assertEqual(new_game.status, PvPGame.Status.ACTIVE)
        self.assertEqual(new_game.p1_id, self.finished_game.p2_id)
        self.assertEqual(new_game.p2_id, self.finished_game.p1_id)

        rematch = RematchRequest.objects.get(game=self.finished_game)
        self.assertEqual(rematch.status, RematchRequest.Status.ACCEPTED)
        self.assertEqual(rematch.new_game_id, new_game.id)
        self.assertEqual(mock_notify_user.call_count, 2)
