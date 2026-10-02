from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AcademicTerm,
    AttendanceAuditLog,
    AttendanceEntry,
    AttendanceSession,
    StudentAttendanceSummary,
)


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "term_type", "starts_on", "ends_on", "is_locked")
    list_filter = ("term_type", "is_locked")
    search_fields = ("code", "label")


class AttendanceEntryInline(admin.TabularInline):
    model = AttendanceEntry
    extra = 0
    fields = ("student", "status", "note")
    raw_id_fields = ("student",)


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "class_name",
        "section",
        "subject",
        "period",
        "on_date",
        "attendance_bar",
        "term",
    )
    list_filter = ("term", "class_name", "subject", "on_date")
    search_fields = ("class_name", "section", "subject")
    date_hierarchy = "on_date"
    inlines = [AttendanceEntryInline]
    raw_id_fields = ("marked_by",)

    @admin.display(description="Attendance")
    def attendance_bar(self, obj):
        pct = obj.attendance_percentage
        colour = "green" if pct >= 90 else "orange" if pct >= 75 else "red"
        return format_html(
            '<span style="color:{};font-weight:600">{:.1f}%</span>', colour, pct
        )


@admin.register(AttendanceEntry)
class AttendanceEntryAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "status", "note", "marked_at")
    list_filter = ("status",)
    raw_id_fields = ("session", "student")


@admin.register(StudentAttendanceSummary)
class StudentAttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ("student", "term", "percentage", "risk_band", "computed_at")
    list_filter = ("risk_band", "term")
    readonly_fields = ("computed_at",)
    ordering = ("percentage",)

    @admin.display(description="Standing")
    def standing(self, obj):
        return f"{obj.percentage}% ({obj.risk_band})"


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "session", "actor", "previous_status", "new_status")
    list_filter = ("action",)
    readonly_fields = [f.name for f in AttendanceAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False