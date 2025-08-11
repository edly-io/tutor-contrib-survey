"""
URLs for survey_api.
"""
from django.urls import re_path  # pylint: disable=unused-import
from django.views.generic import TemplateView  # pylint: disable=unused-import

from .views import PermissionsAccessView, DashboardInfoView, SurveyCompletedView, SurveyStatusView, FormResponses, RegistrationResponsesView, GoogleFormResponseView, CourseResponseView, UserRegistrationView, UserCourseView, UserOnboardingView

urlpatterns = [
    # TODO: Fill in URL patterns and views here.
    # re_path(r'', TemplateView.as_view(template_name="survey_api/base.html")),
    re_path(r'^api/status/?$', SurveyStatusView.as_view(), name='survey-status'),
    re_path(r'^api/allowed/?$', PermissionsAccessView.as_view(), name='allowed'),

    re_path(r'^api/dashboard/?$', DashboardInfoView.as_view(), name='dashboard'),

    # POST → marks the survey as completed and returns new status
    re_path(r'^api/completed/?$', SurveyCompletedView.as_view(), name='survey-completed'),

    re_path(r'^api/responses/q', FormResponses.as_view(), name='form-responses'),
    re_path(r'^api/responses/registration/?$', RegistrationResponsesView.as_view(), name='registration-responses'),
    re_path(r'^api/responses/course/q', CourseResponseView.as_view(), name='course-responses'),

    re_path(r'^api/user/course/q', UserCourseView.as_view(), name='user-course'),
    re_path(r'^api/user/onboarding/q', UserOnboardingView.as_view(), name='user-onboarding'),
    re_path(r'^api/user/registration/q', UserRegistrationView.as_view(), name='user-registration'),

    re_path(r'^api/course-forms/?$', GoogleFormResponseView.as_view(), name='course-form'),
]
