import os

import requests
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SurveyModel


class SurveyStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        survey, _ = SurveyModel.objects.get_or_create(user=request.user)
        return Response(
            {"status": survey.status, "count": survey.times_shown},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        survey, _ = SurveyModel.objects.get_or_create(user=request.user)
        if not survey.is_completed:
            survey.update_count()
        return Response({"status": survey.status}, status=status.HTTP_200_OK)


class SurveyCompletedView(APIView):
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_301_MOVED_PERMANENTLY,
            )

        user = get_object_or_404(User, email=email)
        survey, _ = SurveyModel.objects.get_or_create(user=user)

        if not survey.is_completed:
            survey.is_completed = True
            survey.save()

        return Response({"status": survey.status}, status=status.HTTP_200_OK)


class FormResponses(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_access_token(self):
        SCOPES = [
            "https://www.googleapis.com/auth/forms.responses.readonly",
            "https://www.googleapis.com/auth/forms.body.readonly",
            "openid",
            "profile",
            "email",
        ]
        SERVICE_ACCOUNT_FILE = os.path.join(
            os.path.dirname(__file__), "epfl-survey-0a4f10725356.json"
        )

        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )

        credentials.refresh(Request())
        return credentials.token

    def get(self, request):
        try:
            token = self.get_access_token()
        except Exception as e:
            return JsonResponse({"error": f"Token error: {str(e)}"}, status=500)

        headers = {"Authorization": f"Bearer {token}"}

        url_en_base = "https://forms.googleapis.com/v1/forms/14MuRMvwkwu2g3tFH3KGcAa9fR_3rCf3RfDRKTZ9MyiA"
        url_en = "https://forms.googleapis.com/v1/forms/14MuRMvwkwu2g3tFH3KGcAa9fR_3rCf3RfDRKTZ9MyiA/responses"
        url_fr = "https://forms.googleapis.com/v1/forms/17Mpxpp44GW4VPEXK0qLZcVLYc5Ikm_vNuipTMPngHxc/responses"

        try:
            resp_en_base = requests.get(url_en_base, headers=headers)
            resp_en_base.raise_for_status()
            data_en_base = resp_en_base.json()

            resp_en = requests.get(url_en, headers=headers)
            resp_en.raise_for_status()
            data_en = resp_en.json().get("responses", [])

            resp_fr = requests.get(url_fr, headers=headers)
            resp_fr.raise_for_status()
            data_fr = resp_fr.json().get("responses", [])

            combined = data_en + data_fr

            return JsonResponse(
                {"responses": combined, "meta": data_en_base}, status=200
            )

        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"API error: {str(e)}"}, status=500)
