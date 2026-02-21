from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


User = get_user_model()


class AdminOverviewAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/game/admin/stats/overview/"
        self.user = User.objects.create_user(
            username="regular_user",
            email="regular@example.com",
            password="pass12345",
            is_staff=False,
            is_superuser=False,
        )
        self.admin = User.objects.create_user(
            username="staff_user",
            email="staff@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )

    def test_overview_anonymous_is_unauthorized_or_forbidden(self):
        response = self.client.get(self.url, format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_overview_non_staff_is_forbidden(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_overview_staff_is_ok(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
