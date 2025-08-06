from django.db import models
from django.contrib.auth.models import User

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

class SurveyModel(models.Model):
    STATUS_SHOW      = "show"
    STATUS_MUST_SHOW = "must_show"
    STATUS_DONT_SHOW = "dont_show"

    user         = models.OneToOneField(User, on_delete=models.CASCADE)
    times_shown  = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)

    def update_count(self):
        """Call this whenever the survey is shown."""
        self.times_shown += 1
        self.save()

    @property
    def status(self) -> str:
        """
        Returns exactly one of: 'show', 'must_show', or 'dont_show'.
        """
        if self.is_completed:
            return self.STATUS_DONT_SHOW

        # third (and any subsequent) view is non‑skippable
        if self.times_shown >= 3:
            return self.STATUS_MUST_SHOW

        # first and second views are skippable
        return self.STATUS_SHOW

    def __str__(self):
        return f"{self.user.username}: {self.status} (shown {self.times_shown})"


class CourseFeedbackModel(models.Model):
    course = models.OneToOneField(
        CourseOverview, 
        on_delete=models.CASCADE, 
        related_name='course_feedback_form', 
        help_text='Course Feedback Form'
    )

    form_id = models.CharField(
        max_length=128,
        help_text="The {formId} you need when calling GET /forms/{formId}/responses."
    )


class GoogleFormResponseModel(models.Model):
    """
    Minimal metadata to track every time a user submits any Google Form.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='form_responses',
        help_text="Who submitted this response."
    )
    form_id = models.CharField(
        max_length=128,
        help_text="The {formId} you need when calling GET /forms/{formId}/responses."
    )
    response_id = models.CharField(
        max_length=128,
        help_text="The {responseId} you need when calling GET /forms/{formId}/responses/{responseId}."
    )
    submitted_at = models.DateTimeField(
        help_text="Timestamp when the user hit submit in Google Forms."
    )
    
    class Meta:
        unique_together = (
            ('form_id', 'response_id'),
        )
        indexes = [
            models.Index(fields=['user', 'form_id']),     
            models.Index(fields=['form_id', 'submitted_at']), 
        ]

    def __str__(self):
        return f"{self.user} - {self.form_id}/{self.response_id}"
