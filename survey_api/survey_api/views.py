import requests
from django.conf import settings
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

        credentials = service_account.Credentials.from_service_account_info(
            settings.SERVICE_ACCOUNT_INFO, scopes=SCOPES
        )

        credentials.refresh(Request())
        return credentials.token

    def get(self, request):
        try:
            token = self.get_access_token()
        except Exception as e:
            return JsonResponse({"error": f"Token error: {str(e)}"}, status=500)

        headers = {"Authorization": f"Bearer {token}"}

        ID_ENGLISH_FORM = "14MuRMvwkwu2g3tFH3KGcAa9fR_3rCf3RfDRKTZ9MyiA"
        ID_FRENCH_FORM = "17Mpxpp44GW4VPEXK0qLZcVLYc5Ikm_vNuipTMPngHxc"

        url_en_base = f"https://forms.googleapis.com/v1/forms/{ID_ENGLISH_FORM}"
        url_fr_base = f"https://forms.googleapis.com/v1/forms/{ID_FRENCH_FORM}"
        url_en = f"https://forms.googleapis.com/v1/forms/{ID_ENGLISH_FORM}/responses"
        url_fr = f"https://forms.googleapis.com/v1/forms/{ID_FRENCH_FORM}/responses"

        try:
            resp_en_base = requests.get(url_en_base, headers=headers)
            resp_en_base.raise_for_status()
            metaEn = resp_en_base.json()

            resp_fr_base = requests.get(url_fr_base, headers=headers)
            resp_fr_base.raise_for_status()
            metaFr = resp_fr_base.json()

            resp_en = requests.get(url_en, headers=headers)
            resp_en.raise_for_status()
            responsesEn = resp_en.json().get("responses", [])

            resp_fr = requests.get(url_fr, headers=headers)
            resp_fr.raise_for_status()
            responsesFr = resp_fr.json().get("responses", [])

            lang = request.query_params.get('language')


            qmap = {}
            for meta, code in ((metaEn, "en"), (metaFr, "fr-ca")):
                form_id = meta.get("formId")
                for item in meta.get("items", []):
                    q = item.get("questionItem", {}).get("question", {})
                    qid = q.get("questionId")
                    if not qid:
                        continue
                    qmap.setdefault(qid, {"title": {}, "options": {}})
                    # store title
                    qmap[qid]["title"][code] = item.get("title", "")
                    # extract choice/checkbox options
                    opts = []
                    if "choiceQuestion" in q:
                        opts = [o["value"] for o in q["choiceQuestion"]["options"]]
                    elif "checkboxQuestion" in q:
                        opts = [o["value"] for o in q["checkboxQuestion"]["options"]]
                    qmap[qid]["options"][code] = opts

            def translate(qid, raw_value):
                opts_en = qmap.get(qid, {}).get("options", {}).get("en", [])
                opts_fr = qmap.get(qid, {}).get("options", {}).get("fr-ca", [])
                # find index
                if raw_value in opts_en:
                    idx = opts_en.index(raw_value)
                elif raw_value in opts_fr:
                    idx = opts_fr.index(raw_value)
                else:
                    # free-text or unknown -> passthrough
                    return raw_value
                # pick target list (fallback to en)
                tgt_opts = qmap[qid]["options"].get(lang, opts_en)
                return tgt_opts[idx] if idx < len(tgt_opts) else raw_value

            merged = []
            for src in (responsesEn, responsesFr):
                blocks = src.get("responses") if isinstance(src, dict) else src
                for resp in blocks:
                    new_ans = {}
                    for qid, ans_block in resp.get("answers", {}).items():
                        # extract raw values
                        raws = []
                        if "value" in ans_block:
                            raws = [ans_block["value"]]
                        elif "textAnswers" in ans_block:
                            raws = [a["value"] for a in ans_block["textAnswers"]["answers"]]

                        translated = [translate(qid, v) for v in raws]

                        # rebuild the Answer object exactly as Google returns it
                        new_ans[qid] = {
                            "questionId": qid,
                            "textAnswers": {
                                "answers": [{"value": v} for v in translated]
                            }
                        }

                    merged.append({
                        "formId":           resp.get("formId", metaEn.get("formId")),
                        "responseId":       resp.get("responseId"),
                        "createTime":       resp.get("createTime"),
                        "lastSubmittedTime": resp.get("lastSubmittedTime", resp.get("createTime")),
                        "respondentEmail":  resp.get("respondentEmail"),
                        "answers":          new_ans
                    })

            return Response({"responses": merged, "meta": metaEn if lang == "en" else metaFr })


        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"API error: {str(e)}"}, status=500)
