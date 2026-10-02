"""Signal handlers for the analytics app."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AttendanceEntry, AttendanceSession

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AttendanceEntry)
def refresh_session_counters(sender, instance, created, **kwargs):
    """Keep the denormalised session counters honest after each write."""
    try:
        instance.session.recalculate_counters()
    except AttendanceSession.DoesNotExist:
        logger.warning(
            "AttendanceEntry %s saved with a missing session; counters not refreshed.",
            instance.pk,
        )


@receiver(post_save, sender=AttendanceSession)
def log_locked_term_edits(sender, instance, created, **kwargs):
    if not created and instance.term_id and instance.term.is_locked:
        logger.warning(
            "Session %s was edited despite term %s being locked.",
            instance.pk,
            instance.term.code,
        )