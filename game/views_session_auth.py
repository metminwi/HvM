# game/views_session_auth.py

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.db.models import Q

from rest_framework import status, permissions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from .serializers import SignupSerializer, MeSerializer, ProfileUpdateSerializer

User = get_user_model()


class CSRFView(APIView):
    """
    GET /api/game/auth/csrf/
    -> force le cookie csrftoken
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)}, status=status.HTTP_200_OK)


class SignupSessionView(APIView):
    """
    POST /api/game/auth/signup/
    -> crée user + login automatique (session)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # auto-login (crée sessionid)
        login(request, user)

        return Response(
            {"message": "Signup OK", "user": MeSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginSessionView(APIView):
    """
    POST /api/game/auth/login/
    Body:
      - { email, password }
      - OU { username, password }

    -> crée session Django

    ✅ Fix important:
    - évite 500 si plusieurs users partagent le même email (MultipleObjectsReturned)
    - renvoie 409 (Conflict) si doublons email détectés
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data or {}

        password = (data.get("password") or "").strip()
        email = (data.get("email") or "").strip().lower()
        username = (data.get("username") or "").strip()

        if not password or (not email and not username):
            return Response(
                {"detail": "email or username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = None

        # 1) login via username direct
        if username:
            user = authenticate(request, username=username, password=password)

        # 2) login via email (mapping email -> username)
        if user is None and email:
            qs = User.objects.filter(email__iexact=email).order_by("-date_joined")

            # Si ton système a déjà créé des doublons email à cause d'appels signup,
            # on refuse proprement au lieu de crasher en 500.
            if qs.count() > 1:
                return Response(
                    {
                        "detail": (
                            "Multiple accounts found for this email. "
                            "Please cleanup duplicate accounts (dev) or contact support."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            u = qs.first()
            if u:
                user = authenticate(request, username=u.username, password=password)

        if not user:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)

        return Response(
            {"message": "Login OK", "user": MeSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class LogoutSessionView(APIView):
    """
    POST /api/game/auth/logout/
    -> supprime la session
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"message": "Logged out"}, status=status.HTTP_200_OK)


class MeSessionView(APIView):
    """
    GET /api/game/auth/me/
    -> utilisateur connecté via session
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    (Optionnel) Endpoint alternatif pour debug.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_staff": u.is_staff,
                "date_joined": u.date_joined,
            },
            status=status.HTTP_200_OK,
        )
class ProfileSessionView(APIView):
    """
    GET  /api/game/auth/profile/  -> infos profil
    PATCH /api/game/auth/profile/ -> update partiel
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        return Response(MeSerializer(user).data, status=status.HTTP_200_OK)


class ChangePasswordSessionView(APIView):
    """
    POST /api/game/auth/password/change/
    Body: { "old_password": "...", "new_password": "..." }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        old_password = (request.data.get("old_password") or "")
        new_password = (request.data.get("new_password") or "")

        errors = {}
        if not old_password:
            errors["old_password"] = ["This field is required."]
        if not new_password:
            errors["new_password"] = ["This field is required."]
        elif len(new_password) < 8:
            errors["new_password"] = ["Ensure this field has at least 8 characters."]

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.check_password(old_password):
            return Response(
                {"detail": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=request.user)
        except DjangoValidationError as exc:
            return Response(
                {"new_password": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)

        return Response({"message": "Password updated"}, status=status.HTTP_200_OK)
