"""URL configuration for the analytics app."""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("analytics/", views.dashboard, name="dashboard"),
    path("analytics/terms/", views.term_list, name="term-list"),
    path("analytics/terms/<slug:term_code>/standings/", views.term_standings, name="term-standings"),
    path("analytics/sessions/<int:session_id>/", views.session_detail, name="session-detail"),
    path("analytics/sessions/record/", views.record_session, name="record-session"),
    path(
        "analytics/entries/<int:entry_id>/amend/",
        views.amend_entry,
        name="amend-entry",
    ),
    path(
        "analytics/students/<int:student_id>/timeline/",
        views.student_timeline,
        name="student-timeline",
    ),
]