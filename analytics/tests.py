"""Tests for the analytics app.

The legacy `myapp` tests exercise view rendering; these focus on the service
layer and the JSON endpoints, since that is where the maths lives.
"""

import json
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from analytics.models import (
    AcademicTerm,
    AttendanceAuditLog,
    AttendanceEntry,
    AttendanceSession,
    StudentAttendanceSummary,
)
from analytics.services import (
    TermLockedError,
    build_standings,
    classify_risk,
    record_session,
    refresh_summaries,
    subject_heatmap,
    term_for_date,
)


class AnalyticsTestData(TestCase):
    """Shared fixtures: one term, two students, three sessions."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        from myapp.models import Student

        User = get_user_model()

        alice_user = User.objects.create_user(
            email="alice@example.com", password="hunter2hunter2", name="Alice"
        )
        bob_user = User.objects.create_user(
            email="bob@example.com", password="hunter2hunter2", name="Bob"
        )

        today = timezone.localdate()
        cls.term = AcademicTerm.objects.create(
            code="SEM-TEST-01",
            label="Test Semester 1",
            term_type="SEM",
            starts_on=today - timedelta(days=30),
            ends_on=today + timedelta(days=30),
        )
        cls.alice = Student.objects.create(user=alice_user, aadhar="A0000000001")
        cls.bob = Student.objects.create(user=bob_user, aadhar="B0000000002")

        # Session 1: both present.
        s1 = AttendanceSession.objects.create(
            term=cls.term, class_name="10A", section="A", subject="Maths", period=1,
            on_date=today - timedelta(days=3), total_strength=2, present_count=2,
        )
        # Session 2: Alice present, Bob absent.
        s2 = AttendanceSession.objects.create(
            term=cls.term, class_name="10A", section="A", subject="Maths", period=1,
            on_date=today - timedelta(days=2), total_strength=2, present_count=1,
        )
        # Session 3 (different subject): both present.
        s3 = AttendanceSession.objects.create(
            term=cls.term, class_name="10A", section="A", subject="Physics", period=2,
            on_date=today - timedelta(days=1), total_strength=2, present_count=2,
        )

        AttendanceEntry.objects.bulk_create(
            [
                AttendanceEntry(session=s1, student=cls.alice, status="P"),
                AttendanceEntry(session=s1, student=cls.bob, status="P"),
                AttendanceEntry(session=s2, student=cls.alice, status="P"),
                AttendanceEntry(session=s2, student=cls.bob, status="A"),
                AttendanceEntry(session=s3, student=cls.alice, status="L"),
                AttendanceEntry(session=s3, student=cls.bob, status="P"),
            ]
        )
        cls.sessions = [s1, s2, s3]

        # bulk_create skips post_save signals, so seed the denormalised counters
        # by hand to mirror what the signal handler does in normal operation.
        for session in cls.sessions:
            session.recalculate_counters()


class RiskBandTests(TestCase):
    def test_classify_risk_boundaries(self):
        self.assertEqual(classify_risk(100.0), "ok")
        self.assertEqual(classify_risk(95.0), "ok")
        self.assertEqual(classify_risk(92.0), "watch")
        self.assertEqual(classify_risk(85.0), "high")
        self.assertEqual(classify_risk(75.0), "critical")
        self.assertEqual(classify_risk(10.0), "critical")


class TermModelTests(TestCase):
    def test_total_days_is_inclusive(self):
        term = AcademicTerm.objects.create(
            code="SEM-X", label="X", starts_on=date(2024, 1, 1), ends_on=date(2024, 1, 31)
        )
        self.assertEqual(term.total_days, 31)
        self.assertTrue(term.contains(date(2024, 1, 15)))
        self.assertFalse(term.contains(date(2024, 2, 1)))

    def test_term_for_date_returns_matching_term(self):
        term = AcademicTerm.objects.create(
            code="SEM-Y", label="Y", starts_on=date(2024, 5, 1), ends_on=date(2024, 6, 30)
        )
        self.assertEqual(term_for_date(date(2024, 5, 20)), term)
        self.assertIsNone(term_for_date(date(2024, 7, 1)))


class ServiceTests(AnalyticsTestData):
    def test_session_counters_recalculate_from_entries(self):
        session = self.sessions[1]
        session.recalculate_counters()
        session.refresh_from_db()
        self.assertEqual(session.total_strength, 2)
        self.assertEqual(session.present_count, 1)
        self.assertEqual(session.absent_count, 1)
        self.assertEqual(session.attendance_percentage, 50.0)

    def test_late_entries_count_as_present(self):
        self.assertTrue(self.sessions[2].entries.get(student=self.bob).counts_as_present)
        self.assertTrue(self.sessions[2].entries.get(student=self.alice).counts_as_present)
        self.assertFalse(self.sessions[1].entries.get(student=self.bob).counts_as_present)

    def test_build_standings_computes_percentages(self):
        standings = {s.student_id: s for s in build_standings(self.term)}
        alice = standings[self.alice.id]
        bob = standings[self.bob.id]

        self.assertEqual(alice.eligible, 3)
        self.assertEqual(alice.attended, 3)  # P, P, L
        self.assertEqual(alice.percentage, 100.0)
        self.assertEqual(alice.risk_band, "ok")

        self.assertEqual(bob.eligible, 3)
        self.assertEqual(bob.attended, 2)  # P, A, P
        self.assertEqual(bob.percentage, 66.67)
        self.assertEqual(bob.risk_band, "critical")

    def test_standings_respect_class_filter(self):
        self.assertEqual(len(build_standings(self.term, class_name="10A")), 2)
        self.assertEqual(len(build_standings(self.term, class_name="11B")), 0)

    def test_refresh_summaries_is_idempotent(self):
        first = refresh_summaries(self.term)
        second = refresh_summaries(self.term)
        self.assertEqual(first, 2)
        self.assertEqual(second, 2)
        self.assertEqual(StudentAttendanceSummary.objects.filter(term=self.term).count(), 2)

    def test_summary_rows_carry_risk_bands(self):
        refresh_summaries(self.term)
        bob_summary = StudentAttendanceSummary.objects.get(term=self.term, student=self.bob)
        self.assertEqual(bob_summary.risk_band, "critical")
        self.assertTrue(bob_summary.is_at_risk)
        self.assertFalse(float(bob_summary.percentage) > 100)

    def test_subject_heatmap_groups_by_class_and_subject(self):
        heatmap = subject_heatmap(self.term)
        self.assertIn("10A", heatmap)
        self.assertIn("Maths", heatmap["10A"])
        self.assertEqual(heatmap["10A"]["Maths"]["sessions"], 2)
        self.assertEqual(heatmap["10A"]["Physics"]["percentage"], 100.0)

    def test_record_session_rejects_locked_terms(self):
        self.term.is_locked = True
        self.term.save(update_fields=["is_locked"])
        with self.assertRaises(TermLockedError):
            record_session(self.sessions[0], [(self.alice, "A", "")], actor=None)

    def test_record_session_upserts_and_logs(self):
        session = self.sessions[0]
        record_session(session, [(self.alice, "A", "late arrival"), (self.bob, "P", "")], actor=None)
        session.refresh_from_db()

        self.assertEqual(session.present_count, 1)
        self.assertEqual(session.absent_count, 1)
        self.assertEqual(AttendanceAuditLog.objects.filter(session=session).count(), 2)
        self.assertEqual(session.entries.get(student=self.alice).note, "late arrival")


class ApiTests(AnalyticsTestData):
    def setUp(self):
        self.client.force_login(self.alice_user())

    def alice_user(self):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            email="staff@example.com", password="hunter2hunter2", name="Staff", is_staff=True
        )

    def test_term_list_endpoint(self):
        response = self.client.get(reverse("analytics:term-list"))
        self.assertEqual(response.status_code, 200)
        codes = [t["code"] for t in response.json()["terms"]]
        self.assertIn("SEM-TEST-01", codes)

    def test_term_standings_endpoint(self):
        response = self.client.get(
            reverse("analytics:term-standings", args=["SEM-TEST-01"]),
            {"class": "10A"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["term"], "SEM-TEST-01")

    def test_session_detail_endpoint(self):
        response = self.client.get(
            reverse("analytics:session-detail", args=[self.sessions[1].pk])
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["entries"]), 2)
        self.assertEqual(body["session"]["counters"]["absent_count"], 1)

    def test_student_timeline_endpoint(self):
        response = self.client.get(
            reverse("analytics:student-timeline", args=[self.bob.id])
        )
        body = response.json()
        self.assertEqual(body["sessions"], 3)
        self.assertEqual(body["attended"], 2)
        self.assertAlmostEqual(body["percentage"], 66.67, places=2)

    def test_dashboard_endpoint(self):
        refresh_summaries(self.term)
        response = self.client.get(reverse("analytics:dashboard"), {"term": "SEM-TEST-01"})
        body = response.json()
        self.assertEqual(body["term"], "SEM-TEST-01")
        self.assertEqual(body["totals"]["sessions"], 3)
        self.assertEqual(body["totals"]["at_risk"], 1)

    def test_record_session_rejects_malformed_json(self):
        response = self.client.post(
            reverse("analytics:record-session"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_record_session_rejects_unknown_status(self):
        response = self.client.post(
            reverse("analytics:record-session"),
            data=json.dumps(
                {"session_id": self.sessions[0].pk, "entries": [{"student_id": self.alice.id, "status": "Z"}]}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Bad entry", response.json()["error"])

    def test_record_session_succeeds(self):
        response = self.client.post(
            reverse("analytics:record-session"),
            data=json.dumps(
                {
                    "session_id": self.sessions[0].pk,
                    "entries": [
                        {"student_id": self.alice.id, "status": "A"},
                        {"student_id": self.bob.id, "status": "P"},
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["ok"])

    def test_record_session_returns_409_for_locked_term(self):
        self.term.is_locked = True
        self.term.save(update_fields=["is_locked"])
        response = self.client.post(
            reverse("analytics:record-session"),
            data=json.dumps(
                {"session_id": self.sessions[0].pk, "entries": [{"student_id": self.alice.id, "status": "P"}]}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        response = self.client.get(reverse("analytics:dashboard"))
        self.assertEqual(response.status_code, 302)


class CommandTests(AnalyticsTestData):
    def test_rebuild_summaries_dry_run(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("rebuild_summaries", "--term", "SEM-TEST-01", "--dry-run", stdout=out)
        self.assertIn("dry-run", out.getvalue())
        self.assertEqual(StudentAttendanceSummary.objects.filter(term=self.term).count(), 0)

    def test_rebuild_summaries_writes_rows(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("rebuild_summaries", "--term", "SEM-TEST-01", stdout=out)
        self.assertEqual(StudentAttendanceSummary.objects.filter(term=self.term).count(), 2)

    def test_lock_term_marks_term_locked(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("lock_term", "SEM-TEST-01", stdout=out)
        self.term.refresh_from_db()
        self.assertTrue(self.term.is_locked)
        self.assertEqual(StudentAttendanceSummary.objects.filter(term=self.term).count(), 2)