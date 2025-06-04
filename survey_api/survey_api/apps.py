"""
survey_api Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins.constants import (
    PluginURLs
)
from openedx.core.djangoapps.plugins.constants import ProjectType


class SurveyApiConfig(AppConfig):
    """
    Configuration for the survey_api Django application.
    """

    name = 'survey_api'

    plugin_app = {
    # Configuration setting for Plugin URLs for this app.
    PluginURLs.CONFIG: {
        ProjectType.LMS: {
            # The namespace to provide to django's urls.include.
            PluginURLs.NAMESPACE: 'survey_api',

            # The application namespace to provide to django's urls.include.
            # Optional; Defaults to None.
            PluginURLs.APP_NAME: 'survey_api',

            # The regex to provide to django's urls.url.
            # Optional; Defaults to r''.
            PluginURLs.REGEX: r'',

            # The python path (relative to this app) to the URLs module to be plugged into the project.
            # Optional; Defaults to 'urls'.
            PluginURLs.RELATIVE_PATH: 'urls',
        },
        ProjectType.CMS: {
            # The namespace to provide to django's urls.include.
            PluginURLs.NAMESPACE: 'survey_api',

            # The application namespace to provide to django's urls.include.
            # Optional; Defaults to None.
            PluginURLs.APP_NAME: 'survey_api',

            # The regex to provide to django's urls.url.
            # Optional; Defaults to r''.
            PluginURLs.REGEX: r'',

            # The python path (relative to this app) to the URLs module to be plugged into the project.
            # Optional; Defaults to 'urls'.
            PluginURLs.RELATIVE_PATH: 'urls',
        },
    },
}