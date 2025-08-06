from django.contrib import admin
from .models import SurveyModel, GoogleFormResponseModel, CourseFeedbackModel

admin.site.register(SurveyModel)
admin.site.register(GoogleFormResponseModel)
admin.site.register(CourseFeedbackModel)

