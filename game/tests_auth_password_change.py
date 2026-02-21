from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


User = get_user_model()


class ChangePasswordSessionViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/game/auth/password/change/"
        self.password = "OldPassword123!"
        self.user = User.objects.create_user(
            username="password_user",
            email="password_user@example.com",
            password=self.password,
        )

    def test_change_password_success(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        response = self.client.post(
            self.url,
            {"old_password": self.password, "new_password": "NewPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": "Password updated"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword123!"))
        me_response = self.client.get("/api/game/auth/me/", format="json")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old_password(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        response = self.client.post(
            self.url,
            {"old_password": "WrongPassword!", "new_password": "NewPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"detail": "Old password is incorrect."})

    def test_change_password_weak_password(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        response = self.client.post(
            self.url,
            {"old_password": self.password, "new_password": "short"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_change_password_requires_authentication(self):
        response = self.client.post(
            self.url,
            {"old_password": self.password, "new_password": "NewPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data,
            {"detail": "Authentication credentials were not provided."},
        )
