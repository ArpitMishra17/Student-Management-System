"""Views for the analytics app.

The endpoints return JSON so the existing server-rendered templates in
`templates/` can consume them with a small amount of vanilla JS, matching how
the rest of the project talks to its AJAX endpoints.
"""

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import AcademicTerm, AttendanceEntry, AttendanceSession, StudentAttendanceSummary


def _parse_date(value):
    if not value:
        return timezone.localdate()
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise Http404("Expected a date formatted as YYYY-MM-DD.")


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@require_GET
@login_required
def term_list(request):
    """All academic terms, newest first."""
    terms = AcademicTerm.objects.all()
    payload = [
        {
            "id": t.pk,
            "code": t.code,
            "label": t.label,
            "term_type": t.get_term_type_display(),
            "starts_on": t.starts_on.isoformat(),
            "ends_on": t.ends_on.isoformat(),
            "total_days": t.total_days,
            "is_locked": t.is_locked,
        }
        for t in terms
    ]
    if _wants_json(request):
        return JsonResponse({"terms": payload})
    return JsonResponse({"terms": payload})


@require_GET
@login_required
def term_standings(request, term_code):
    """Per-student attendance standing for a term, optionally scoped to a class."""
    term = get_object_or_404(AcademicTerm, code=term_code)
    standings = services.build_standings(
        term,
        class_name=request.GET.get("class"),
        section=request.GET.get("section"),
    )
    return JsonResponse(
        {
            "term": term.code,
            "generated_at": timezone.now().isoformat(),
            "count": len(standings),
            "standings": [s.as_dict() for s in standings],
        }
    )


@require_GET
@login_required
def session_detail(request, session_id):
    term_session = get_object_or_404(
        AttendanceSession.objects.select_related("term", "marked_by"), pk=session_id
    )
    entries = term_session.entries.select_related("student").all()

    rows = [
        {
            "student_id": e.student_id,
            "student": str(e.student),
            "status": e.status,
            "status_display": e.get_status_display(),
            "counts_as_present": e.counts_as_present,
            "note": e.note,
        }
        for e in entries
    ]

    return JsonResponse(
        {
            "session": {
                "id": term_session.pk,
                "term": term_session.term.code,
                "class_name": term_session.class_name,
                "section": term_session.section,
                "subject": term_session.subject,
                "period": term_session.period,
                "on_date": term_session.on_date.isoformat(),
                "attendance_percentage": term_session.attendance_percentage,
                "counters": {
                    "total_strength": term_session.total_strength,
                    "present_count": term_session.present_count,
                    "absent_count": term_session.absent_count,
                },
            },
            "entries": rows,
        }
    )


@staff_member_required
@require_POST
def record_session(request):
    """Accept a JSON roll call payload and persist it."""
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body is not valid JSON."}, status=400)

    session_id = body.get("session_id")
    if not session_id:
        return JsonResponse({"error": "session_id is required."}, status=400)

    session = get_object_or_404(AttendanceSession, pk=session_id)
    raw_entries = body.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        return JsonResponse({"error": "entries must be a non-empty list."}, status=400)

    entries = []
    for item in raw_entries:
        student_id = item.get("student_id")
        status = item.get("status", "P")
        if student_id is None or status not in dict(AttendanceSession.Status.choices):
            return JsonResponse(
                {"error": f"Bad entry: student_id={student_id!r}, status={status!r}"},
                status=400,
            )
        entries.append((student_id, status, item.get("note", "")))

    try:
        services.record_session(
            session, entries, actor=request.user, request_id=request.headers.get("X-Request-ID")
        )
    except services.TermLockedError as exc:
        return JsonResponse({"error": str(exc)}, status=409)

    return JsonResponse(
        {
            "ok": True,
            "session_id": session.pk,
            "attendance_percentage": session.attendance_percentage,
        },
        status=201,
    )


@staff_member_required
@require_POST
def amend_entry(request, entry_id):
    """Change a single entry and leave an audit trail behind."""
    entry = get_object_or_404(AttendanceEntry.objects.select_related("session"), pk=entry_id)
    status = (request.POST.get("status") or "").strip().upper()

    if status not in dict(AttendanceSession.Status.choices):
        return JsonResponse({"error": f"Unknown status {status!r}."}, status=400)

    if entry.session.term.is_locked:
        return JsonResponse(
            {"error": f"Term {entry.session.term.code} is locked."}, status=409
        )

    previous = entry.status
    entry.status = status
    entry.note = request.POST.get("note", entry.note)
    entry.save(update_fields=["status", "note", "marked_at"])

    entry.session.recalculate_counters()

    from .models import AttendanceAuditLog

    AttendanceAuditLog.objects.create(
        session=entry.session,
        entry=entry,
        actor=request.user,
        action="amended",
        previous_status=previous,
        new_status=status,
        payload={"note": entry.note},
    )

    return JsonResponse({"ok": True, "entry_id": entry.pk, "status": entry.status})


@require_GET
@login_required
def dashboard(request):
    """Compact payload powering the analytics dashboard landing page."""
    term_code = request.GET.get("term")
    term = (
        get_object_or_404(AcademicTerm, code=term_code)
        if term_code
        else services.term_for_date(_parse_date(request.GET.get("date")))
    )

    if term is None:
        return JsonResponse(
            {"error": "No academic term is active for the requested date."}, status=404
        )

    risky = services.at_risk_students(term, limit=25)
    heatmap = services.subject_heatmap(term)

    return JsonResponse(
        {
            "term": term.code,
            "term_label": term.label,
            "is_locked": term.is_locked,
            "totals": {
                "students_tracked": StudentAttendanceSummary.objects.filter(term=term).count(),
                "at_risk": len(risky),
                "sessions": AttendanceSession.objects.filter(term=term).count(),
            },
            "heatmap": heatmap,
            "at_risk": [
                {
                    "student": str(r.student),
                    "percentage": float(r.percentage),
                    "risk_band": r.risk_band,
                }
                for r in risky
            ],
        }
    )


@require_GET
@login_required
def student_timeline(request, student_id):
    """Chronological attendance history for a single student."""
    entries = (
        AttendanceEntry.objects.filter(student_id=student_id)
        .select_related("session", "session__term")
        .order_by("-session__on_date")[:500]
    )

    timeline = [
        {
            "date": e.session.on_date.isoformat(),
            "term": e.session.term.code,
            "subject": e.session.subject,
            "class_name": e.session.class_name,
            "section": e.session.section,
            "status": e.status,
            "status_display": e.get_status_display(),
            "note": e.note,
        }
        for e in entries
    ]

    attended = sum(1 for e in entries if e.counts_as_present)
    total = len(entries)

    return JsonResponse(
        {
            "student_id": student_id,
            "sessions": total,
            "attended": attended,
            "percentage": round((attended / total) * 100, 2) if total else 0.0,
            "timeline": timeline,
        }
    )