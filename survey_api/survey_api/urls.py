"""
URLs for survey_api.
"""
from django.urls import re_path  # pylint: disable=unused-import
from django.views.generic import TemplateView  # pylint: disable=unused-import

from .views import SurveyCompletedView, SurveyStatusView

urlpatterns = [
    # TODO: Fill in URL patterns and views here.
    # re_path(r'', TemplateView.as_view(template_name="survey_api/base.html")),
    re_path(r'^api/status/?$', SurveyStatusView.as_view(), name='survey-status'),

    # POST → marks the survey as completed and returns new status
    re_path(r'^api/completed/?$', SurveyCompletedView.as_view(), name='survey-completed'),
]
