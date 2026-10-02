"""App config for the analytics app."""

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics"
    verbose_name = "Attendance Analytics"

    def ready(self):
        # Importing here keeps model registration side effects out of startup.
        from . import signals  # noqa: F401