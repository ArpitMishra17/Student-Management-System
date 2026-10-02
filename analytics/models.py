"""Models for the attendance analytics app.

These are deliberately decoupled from the legacy `myapp` models through string
references so that the analytics pipeline can be rolled out incrementally
without forcing a data migration on the core student database.
"""

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AcademicTerm(models.Model):
    """A single academic term (semester / trimester) that metrics roll up into."""

    TERM_TYPE_CHOICES = [
        ("SEM", "Semester"),
        ("TRIM", "Trimester"),
        ("YEAR", "Full Year"),
    ]

    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=120)
    term_type = models.CharField(max_length=8, choices=TERM_TYPE_CHOICES, default="SEM")
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_locked = models.BooleanField(
        default=False,
        help_text="Locked terms reject new attendance rows and cannot be re-scored.",
    )

    class Meta:
        ordering = ["-starts_on"]
        verbose_name_plural = "academic terms"

    def __str__(self):
        return f"{self.code} — {self.label}"

    def clean(self):
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            from django.core.exceptions import ValidationError

            raise ValidationError({"ends_on": "Term end date cannot precede its start date."})

    @property
    def total_days(self):
        if not self.starts_on or not self.ends_on:
            return 0
        return (self.ends_on - self.starts_on).days + 1

    def contains(self, day):
        return bool(day) and self.starts_on <= day <= self.ends_on


class AttendanceSession(models.Model):
    """One teacher-marked roll call for a class, section, period and subject."""

    class Status(models.TextChoices):
        PRESENT = "P", "Present"
        ABSENT = "A", "Absent"
        LATE = "L", "Late"
        EXCUSED = "E", "Excused"

    term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="sessions"
    )
    class_name = models.CharField(max_length=80)
    section = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=120)
    period = models.PositiveIntegerField(default=1)

    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_sessions_marked",
    )
    marked_at = models.DateTimeField(default=timezone.now)
    on_date = models.DateField(default=timezone.localdate)

    # Denormalised counters, refreshed by `recalculate_counters`.
    total_strength = models.PositiveIntegerField(default=0)
    present_count = models.PositiveIntegerField(default=0)
    absent_count = models.PositiveIntegerField(default=0)

    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-on_date", "class_name", "period"]
        constraints = [
            models.UniqueConstraint(
                fields=["term", "class_name", "section", "subject", "period", "on_date"],
                name="uniq_session_per_period_day",
            ),
            models.CheckConstraint(
                check=Q(total_strength__gte=0), name="attendance_strength_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["class_name", "on_date"]),
            models.Index(fields=["term", "subject"]),
        ]

    def __str__(self):
        return f"{self.class_name}/{self.section or '-'} {self.subject} P{self.period} @ {self.on_date}"

    @property
    def attendance_percentage(self):
        if not self.total_strength:
            return 0.0
        return round((self.present_count / self.total_strength) * 100, 2)

    def recalculate_counters(self, save=True):
        aggregate = self.entries.aggregate(
            total=models.Count("id"),
            present=models.Count("id", filter=models.Q(status="P")),
            absent=models.Count("id", filter=models.Q(status="A")),
        )
        self.total_strength = aggregate["total"] or 0
        self.present_count = aggregate["present"] or 0
        self.absent_count = aggregate["absent"] or 0
        if save:
            self.save(update_fields=["total_strength", "present_count", "absent_count"])
        return aggregate


class AttendanceEntry(models.Model):
    """Per-student status inside an `AttendanceSession`."""

    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="entries"
    )
    student = models.ForeignKey(
        "myapp.Student",
        on_delete=models.CASCADE,
        related_name="attendance_entries",
    )
    status = models.CharField(
        max_length=1, choices=AttendanceSession.Status.choices, default=AttendanceSession.Status.PRESENT
    )
    note = models.CharField(max_length=255, blank=True)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["session__on_date", "student__id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"], name="uniq_entry_per_student_per_session"
            )
        ]

    def __str__(self):
        return f"{self.student} -> {self.get_status_display()}"

    @property
    def counts_as_present(self):
        return self.status in {AttendanceSession.Status.PRESENT, AttendanceSession.Status.LATE}


class StudentAttendanceSummary(models.Model):
    """Pre-aggregated per-term standing for a student. Refreshed nightly."""

    student = models.ForeignKey(
        "myapp.Student", on_delete=models.CASCADE, related_name="attendance_summaries"
    )
    term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="student_summaries"
    )
    sessions_eligible = models.PositiveIntegerField(default=0)
    sessions_attended = models.PositiveIntegerField(default=0)
    sessions_absent = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    risk_band = models.CharField(max_length=16, default="unknown")
    computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-percentage"]
        constraints = [
            models.UniqueConstraint(fields=["student", "term"], name="uniq_summary_per_term")
        ]

    def __str__(self):
        return f"{self.student} @ {self.term.code}: {self.percentage}%"

    @property
    def is_at_risk(self):
        return self.risk_band in {"watch", "critical"}


class AttendanceAuditLog(models.Model):
    """Append-only trail of who changed which attendance row, and when."""

    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="audit_logs"
    )
    entry = models.ForeignKey(
        AttendanceEntry, on_delete=models.CASCADE, null=True, blank=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_audit_logs",
    )
    action = models.CharField(max_length=32)
    previous_status = models.CharField(max_length=1, blank=True)
    new_status = models.CharField(max_length=1, blank=True)
    request_id = models.UUIDField(default=uuid.uuid4, editable=False)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["session", "action"])]

    def __str__(self):
        return f"{self.action} on session {self.session_id} by {self.actor_id}"