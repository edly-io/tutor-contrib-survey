from django.db import models
from django.contrib.auth.models import User

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
        return f"{self.user.username}: {self.status} (shown {self.times_shown}×)"
