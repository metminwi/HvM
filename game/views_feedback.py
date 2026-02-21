from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.renderers import JSONRenderer

from .serializers import FeedbackCreateSerializer

class FeedbackCreateView(APIView):
    # tu peux mettre AllowAny si tu veux accepter feedback anonyme
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = FeedbackCreateSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        fb = ser.save()
        return Response(
            {"id": fb.id, "detail": "Feedback received"},
            status=status.HTTP_201_CREATED,
        )
