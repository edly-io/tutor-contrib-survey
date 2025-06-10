from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from .models import SurveyModel

class SurveyStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        survey, _ = SurveyModel.objects.get_or_create(user=request.user)
        return Response(
            {"status": survey.status, "count": survey.times_shown},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        survey, _ = SurveyModel.objects.get_or_create(user=request.user)
        if not survey.is_completed:
            survey.update_count()
        return Response(
            {"status": survey.status},
            status=status.HTTP_200_OK
        )


class SurveyCompletedView(APIView):
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_301_MOVED_PERMANENTLY
            )
        
        user = get_object_or_404(User, email=email)
        survey, _ = SurveyModel.objects.get_or_create(user=user)
        
        if not survey.is_completed:
            survey.is_completed = True
            survey.save()
        
        return Response(
            {"status": survey.status},
            status=status.HTTP_200_OK
        )