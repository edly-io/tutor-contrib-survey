import requests
from requests.exceptions import RequestException

from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from acl_extra_reg_fields.models import ExtraInfo

from .models import SurveyModel, GoogleFormResponseModel, CourseFeedbackModel

def get_access_token():
    SCOPES = [
        "https://www.googleapis.com/auth/forms.responses.readonly",
        "https://www.googleapis.com/auth/forms.body.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
        "openid",
        "profile",
        "email",
    ]

    credentials = service_account.Credentials.from_service_account_info(
        settings.SERVICE_ACCOUNT_INFO, scopes=SCOPES
    )

    credentials.refresh(Request())
    return credentials.token

class PermissionsAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"is_allowed": bool(request.user.is_superuser)})


class DashboardInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = list(User.objects.values('id', 'username', 'email'))
        feedback_forms = [
            {
                'id': feedback.id,
                'form_id': feedback.form_id,
                'course': feedback.course.display_name,
            }
            for feedback in CourseFeedbackModel.objects.select_related('course').all()
        ]

        return JsonResponse({ "users": users, "feedback_forms": feedback_forms })

class SurveyStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        survey, _ = SurveyModel.objects.get_or_create(user=request.user)
        return Response(
            {"status": survey.status, "count": survey.times_shown, "email": request.user.email},
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

    def get(self, request):
        try:
            token = get_access_token()
        except Exception as e:
            return JsonResponse({"error": f"Token error: {str(e)}"}, status=500)

        headers = {"Authorization": f"Bearer {token}"}

        ID_ENGLISH_FORM = "1MXaneZl67ofajuD9CuEhABtW-xzuWOw-uYfxGLyZ3dA"
        ID_FRENCH_FORM = "1xjY3XCawFdY5L_NcU4L7HCuDtwaizGg3fIbF8fVlThQ"

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


class GoogleFormResponseView(APIView):
    permission_classes = [AllowAny]  

    def post(self, request):
        email       = request.data.get('email')
        form_id     = request.data.get('form_id')
        response_id = request.data.get('response_id')

        if not all([email, form_id, response_id]):
            return Response(
                {"detail": "Missing one of: email, form_id, response_id."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": f"No user found with email '{email}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            resp = GoogleFormResponseModel.objects.create(
                user=user,
                form_id=form_id,
                response_id=response_id,
                submitted_at=timezone.now()
            )
        except:
            return Response(
                {"detail": "That form_id/response_id pair already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "id":           resp.pk,
                "user_email":   user.email,
                "form_id":      resp.form_id,
                "response_id":  resp.response_id,
                "submitted_at": resp.submitted_at,
            },
            status=status.HTTP_201_CREATED
        )


class RegistrationResponsesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_items(self):
        lang_options = [
            {"value": label, "label": label}
            for _, label in ExtraInfo.LANGUAGES
        ]
        ref_options = [
            {"value": label, "label": label}
            for _, label in ExtraInfo.SOCIAL_NETWORKS
        ]

        return [
            {
                "itemId": "username",
                "title": "Username",
                "questionItem": {
                    "question": {
                        "questionId": "username",
                        "textQuestion": {}
                    }
                }
            },
            {
                "itemId": "email",
                "title": "Email",
                "questionItem": {
                    "question": {
                        "questionId": "email",
                        "textQuestion": {}
                    }
                }
            },
            {
                "itemId": "date_joined",
                "title": "Date Joined",
                "questionItem": {
                    "question": {
                        "questionId": "lastSubmittedTime",
                        "textQuestion": {}
                    }
                }
            },
            {
                "itemId": "preferred_language",
                "title": "Preferred Language",
                "questionItem": {
                    "question": {
                        "questionId": "preferred_language",
                        "choiceQuestion": {
                            "type": "RADIO",
                            "options": lang_options
                        }
                    }
                }
            },
            {
                "itemId": "referrer",
                "title": "How did you hear about the platform?",
                "questionItem": {
                    "question": {
                        "questionId": "referrer",
                        "choiceQuestion": {
                            "type": "RADIO",
                            "options": ref_options
                        }
                    }
                }
            },
        ]

    def get_responses(self):
        qs = ExtraInfo.objects.all()
        out = []
        for info in qs:
            out.append({
                "responseId": str(info.pk),
                "answers": {
                    "username": {
                        "questionId": "username",
                        "textAnswers": {"answers": [{"value": info.user.username}]}
                    },
                    "email": {
                        "questionId": "email",
                        "textAnswers": {"answers": [{"value": info.user.email}]}
                    },
                    "lastSubmittedTime": {
                        "questionId": "lastSubmittedTime",
                        "textAnswers": {"answers": [{"value": info.user.date_joined}]}
                    },
                    "preferred_language": {
                        "questionId": "preferred_language",
                        "textAnswers": {
                            "answers": [{"value": info.get_preferred_language_display()}]
                        }
                    },
                    "referrer": {
                        "questionId": "referrer",
                        "textAnswers": {
                            "answers": [{"value": info.get_referrer_display()}]
                        }
                    }
                }
            })
        return out

    def get(self, request):
        return Response({
            "meta": {"items": self.get_items()},
            "responses": self.get_responses(),
        })
    

class CourseResponseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        form_id = request.query_params.get('form_id')
        
        try:
            token = get_access_token()
        except Exception as e:
            return JsonResponse({"error": f"Token error: {str(e)}"}, status=500)

        url_base = f"https://forms.googleapis.com/v1/forms/{form_id}"
        url_responses = f"https://forms.googleapis.com/v1/forms/{form_id}/responses"

        headers = {"Authorization": f"Bearer {token}"}

        try: 
            meta = requests.get(url_base, headers=headers)
            meta.raise_for_status()
            meta = meta.json()

            responses = requests.get(url_responses, headers=headers)
            responses.raise_for_status()
            responses = responses.json()

        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"API error: {str(e)}"}, status=500)
        return JsonResponse({
            "meta": meta,
            "responses": responses['responses']
        })
    


class UserRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    def get_items(self):
        return RegistrationResponsesView().get_items()

    def get_responses(self, username):
        try:
            user = get_object_or_404(User, username=username)
            info = ExtraInfo.objects.select_related('user').get(user=user)
        except ExtraInfo.DoesNotExist:
            return []

        return [{
            "responseId": str(info.pk),
            "answers": {
                "username": {
                    "questionId": "username",
                    "textAnswers": {"answers": [{"value": info.user.username}]}
                },
                "email": {
                    "questionId": "email",
                    "textAnswers": {"answers": [{"value": info.user.email}]}
                },
                "lastSubmittedTime": {
                    "questionId": "lastSubmittedTime",
                    "textAnswers": {"answers": [{"value": info.user.date_joined}]}
                },
                "preferred_language": {
                    "questionId": "preferred_language",
                    "textAnswers": {
                        "answers": [{"value": info.get_preferred_language_display()}]
                    }
                },
                "referrer": {
                    "questionId": "referrer",
                    "textAnswers": {
                        "answers": [{"value": info.get_referrer_display()}]
                    }
                }
            }
        }]

    def get(self, request):

        username = request.query_params.get('username')

        responses = self.get_responses(username)
        if not responses:
            return Response({
                "meta": {"items": []},
                "responses": []
            })

        return Response({
            "meta": {"items": self.get_items()},
            "responses": responses
        })


class UserCourseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        form_id = request.query_params.get('form_id')
        username = request.query_params.get('username')

        user = get_object_or_404(User, username=username)

        try:
            submission = GoogleFormResponseModel.objects.get(form_id=form_id, user=user)
        except ObjectDoesNotExist:
            submission = None

        if not submission: 
            return JsonResponse({
                "meta": {"items": []},
                "responses": []
            })

        try:
            token = get_access_token()
        except Exception as e:
            return JsonResponse({"error": f"Token error: {str(e)}"}, status=500)

        url_base = f"https://forms.googleapis.com/v1/forms/{form_id}"
        url_responses = f"https://forms.googleapis.com/v1/forms/{form_id}/responses/{submission.response_id}"

        headers = {"Authorization": f"Bearer {token}"}        

        try: 
            meta = requests.get(url_base, headers=headers)
            meta.raise_for_status()
            meta = meta.json()

            responses = requests.get(url_responses, headers=headers)
            responses.raise_for_status()
            responses = responses.json()

        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"API error: {str(e)}"}, status=500)
        
        return JsonResponse({
            "meta": meta,
            "responses": [responses]
        })
    

class UserOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    ID_ENGLISH_FORM = "1MXaneZl67ofajuD9CuEhABtW-xzuWOw-uYfxGLyZ3dA"
    ID_FRENCH_FORM = "1xjY3XCawFdY5L_NcU4L7HCuDtwaizGg3fIbF8fVlThQ"

    def get(self, request):
        email = request.query_params.get('email')

        try:
            token = get_access_token()
        except Exception as e:
            return JsonResponse({"error": f"Token error: {str(e)}"}, status=500)
        
        headers = {"Authorization": f"Bearer {token}"}        

        def get_form_responses(form_id, headers):
            """
            Fetch form metadata and all responses from Google Forms API.
            Raises RuntimeError on any network/HTTP failure.
            """
            base_url = f"https://forms.googleapis.com/v1/forms/{form_id}"
            try:
                # Metadata (to find question IDs)
                resp_meta = requests.get(base_url, headers=headers)
                resp_meta.raise_for_status()
                meta = resp_meta.json()

                # All responses
                resp_data = requests.get(f"{base_url}/responses", headers=headers)
                resp_data.raise_for_status()
                responses = resp_data.json().get("responses", [])

                return meta, responses

            except RequestException as e:
                raise RuntimeError(f"Google Forms API request failed for form {form_id}: {e}")
            
        def find_email_question_id(form_meta, email_field_titles):
            """
            Scan form metadata for any item whose title matches one of
            email_field_titles, and return its questionId.
            """
            for item in form_meta.get("items", []):
                title = item.get("title", "").strip()
                q = item.get("questionItem", {}).get("question", {})
                qid = q.get("questionId")
                if title in email_field_titles and qid:
                    return qid
            return None
        
        def find_response_by_email(responses, email_qid, email_to_find):
            """
            Look through each response's answers[email_qid] for a match
            against email_to_find. Supports both textAnswers and emailAnswer.
            Returns the first matching response dict, or None.
            """
            for resp in responses:
                ans = resp.get("answers", {}).get(email_qid)
                if not ans:
                    continue

                # Try textAnswers → list of {"value": "..."}
                if "textAnswers" in ans:
                    for a in ans["textAnswers"].get("answers", []):
                        if a.get("value", "").strip().lower() == email_to_find.lower():
                            return resp

                # Fallback to emailAnswer → {"email": "..."}
                if "emailAnswer" in ans:
                    if ans["emailAnswer"].get("email", "").strip().lower() == email_to_find.lower():
                        return resp

            return None

        try:
            meta_en, responses_en = get_form_responses(self.ID_ENGLISH_FORM, headers)
            meta_fr, responses_fr = get_form_responses(self.ID_FRENCH_FORM, headers)
        except RuntimeError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY
            )
        
        qid_en = find_email_question_id(meta_en, {"Email address"})
        qid_fr = find_email_question_id(meta_fr, {"Adresse e-mail"})

        if not qid_en and not qid_fr:
            return Response(
                {"error": "Could not locate an email question in either form."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


        try:
            match = None
            match_meta = None
            if qid_en:
                match = find_response_by_email(responses_en, qid_en, email)
                if match:
                    match_meta = meta_en
            if qid_fr and match is None:
                match = find_response_by_email(responses_fr, qid_fr, email)
                if match:
                    match_meta = meta_fr

        except Exception as e:
            return Response(
                {"error": f"Error scanning form responses: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

        if match:
            return JsonResponse({
                "meta": match_meta,
                "responses": [match]
            })
        else:
            return JsonResponse({
                "meta": {"items": []},
                "responses": []
            })