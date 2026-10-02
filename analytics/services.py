"""Business logic for the analytics app.

Nothing in here touches the HTTP layer; views call into these services so the
same calculations can be reused by management commands and Celery tasks.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    AcademicTerm,
    AttendanceAuditLog,
    AttendanceEntry,
    AttendanceSession,
    StudentAttendanceSummary,
)

logger = logging.getLogger(__name__)

# Percentages at or below these thresholds drop a student into a risk band.
RISK_THRESHOLDS = (
    (75.0, "critical"),
    (85.0, "high"),
    (92.0, "watch"),
)
BELOW_THRESHOLD_BAND = "ok"


class TermLockedError(RuntimeError):
    """Raised when a write is attempted against a locked academic term."""


@dataclass
class StudentStanding:
    """Flat view of one student's attendance standing for a term."""

    student_id: int
    display_name: str
    eligible: int = 0
    attended: int = 0
    absent: int = 0
    late: int = 0
    subjects: dict = field(default_factory=dict)

    @property
    def percentage(self):
        if not self.eligible:
            return 0.0
        return round((self.attended / self.eligible) * 100, 2)

    @property
    def risk_band(self):
        return classify_risk(self.percentage)

    def as_dict(self):
        return {
            "student_id": self.student_id,
            "display_name": self.display_name,
            "eligible": self.eligible,
            "attended": self.attended,
            "absent": self.absent,
            "late": self.late,
            "percentage": self.percentage,
            "risk_band": self.risk_band,
            "subjects": self.subjects,
        }


def classify_risk(percentage):
    """Map an attendance percentage onto a risk band label."""
    for ceiling, band in RISK_THRESHOLDS:
        if percentage <= ceiling:
            return band
    return BELOW_THRESHOLD_BAND


@transaction.atomic
def record_session(session, entries, actor=None, request_id=None):
    """Persist a batch of attendance entries for a session and refresh counters.

    `entries` is an iterable of ``(student, status, note)`` tuples.
    """
    if session.term.is_locked:
        raise TermLockedError(f"Term {session.term.code} is locked; attendance is read-only.")

    created = 0
    for student, status, note in entries:
        entry, was_created = AttendanceEntry.objects.update_or_create(
            session=session,
            student=student,
            defaults={"status": status, "note": note or ""},
        )
        created += int(was_created)
        AttendanceAuditLog.objects.create(
            session=session,
            entry=entry,
            actor=actor,
            action="created" if was_created else "amended",
            new_status=status,
            payload={"request_id": str(request_id) if request_id else "", "note": note or ""},
        )

    session.recalculate_counters()
    logger.info(
        "Recorded %s entries (%s new) for session %s by %s",
        len(list(entries)) if isinstance(entries, list) else "batched",
        created,
        session.pk,
        getattr(actor, "pk", None),
    )
    return session


def build_standings(term, class_name=None, section=None):
    """Compute per-student standing for every session in a term."""
    qs = AttendanceSession.objects.filter(term=term)
    if class_name:
        qs = qs.filter(class_name=class_name)
    if section:
        qs = qs.filter(section=section)

    buckets = defaultdict(
        lambda: StudentStanding(student_id=0, display_name="", subjects=defaultdict(int))
    )

    rows = (
        AttendanceEntry.objects.filter(session__in=qs)
        .values(
            "student_id",
            "student__user__name",
            "student__user__email",
            "status",
            "session__subject",
        )
        .annotate(n=Count("id"))
    )

    for row in rows:
        bucket = buckets[row["student_id"]]
        bucket.student_id = row["student_id"]
        bucket.display_name = (
            row.get("student__user__name")
            or row.get("student__user__email")
            or str(row["student_id"])
        )
        count = row["n"]

        status = row["status"]
        subject = row["session__subject"]

        bucket.subjects[subject] += count
        if status in (AttendanceSession.Status.PRESENT, AttendanceSession.Status.LATE):
            bucket.attended += count
            if status == AttendanceSession.Status.LATE:
                bucket.late += count
        elif status == AttendanceSession.Status.ABSENT:
            bucket.absent += count
        # Excused entries deliberately do not add to eligible sessions.

        bucket.eligible += count

    return sorted(buckets.values(), key=lambda s: (s.percentage, s.display_name))


@transaction.atomic
def refresh_summaries(term):
    """Rebuild `StudentAttendanceSummary` rows for the whole term."""
    standings = build_standings(term)
    now = timezone.now()

    summary_rows = []
    for standing in standings:
        summary_rows.append(
            StudentAttendanceSummary(
                student_id=standing.student_id,
                term=term,
                sessions_eligible=standing.eligible,
                sessions_attended=standing.attended,
                sessions_absent=standing.absent,
                percentage=standing.percentage,
                risk_band=standing.risk_band,
                computed_at=now,
            )
        )

    StudentAttendanceSummary.objects.filter(term=term).delete()
    StudentAttendanceSummary.objects.bulk_create(summary_rows, batch_size=500)
    logger.info("Rebuilt %s summary rows for term %s", len(summary_rows), term.code)
    return len(summary_rows)


def subject_heatmap(term):
    """Percentage per (class, subject) pair, useful for spotting chronic classes."""
    rows = (
        AttendanceSession.objects.filter(term=term)
        .values("class_name", "subject")
        .annotate(
            strength=Count("id"),
            total_present=Count("id", filter=Q(present_count__gt=0)),
            present_sum=Count("present_count"),
            strength_sum=Count("total_strength"),
        )
    )

    heatmap = {}
    for row in rows:
        strength_sum = row["strength_sum"] or 0
        present_sum = row["present_sum"] or 0
        pct = round((present_sum / strength_sum) * 100, 2) if strength_sum else 0.0
        heatmap.setdefault(row["class_name"], {})[row["subject"]] = {
            "sessions": row["strength"],
            "percentage": pct,
        }
    return heatmap


def at_risk_students(term, limit=None):
    qs = (
        StudentAttendanceSummary.objects.filter(term=term, risk_band__in=["watch", "high", "critical"])
        .select_related("student")
        .order_by("percentage")
    )
    if limit:
        qs = qs[:limit]
    return list(qs)


def term_for_date(day=None):
    """Look up the term covering a date, if one exists."""
    day = day or timezone.localdate()
    term = AcademicTerm.objects.filter(starts_on__lte=day, ends_on__gte=day).first()
    if term is None:
        logger.warning("No academic term covers %s", day)
    return term