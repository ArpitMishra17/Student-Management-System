"""Small form helpers for accepting attendance payloads over HTTP."""

from django import forms

from .models import AcademicTerm, AttendanceSession


class AcademicTermForm(forms.ModelForm):
    class Meta:
        model = AcademicTerm
        fields = ["code", "label", "term_type", "starts_on", "ends_on", "is_locked"]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        starts, ends = cleaned.get("starts_on"), cleaned.get("ends_on")
        if starts and ends and ends < starts:
            raise forms.ValidationError("The term cannot end before it starts.")
        return cleaned


class AttendanceSessionForm(forms.ModelForm):
    class Meta:
        model = AttendanceSession
        fields = [
            "term",
            "class_name",
            "section",
            "subject",
            "period",
            "on_date",
            "remarks",
        ]
        widgets = {"on_date": forms.DateInput(attrs={"type": "date"})}

    def clean_period(self):
        period = self.cleaned_data["period"]
        if not 1 <= period <= 12:
            raise forms.ValidationError("Period must be between 1 and 12.")
        return period

    def clean(self):
        cleaned = super().clean()
        term = cleaned.get("term")
        on_date = cleaned.get("on_date")
        if term and on_date and not term.contains(on_date):
            raise forms.ValidationError(
                f"{on_date} falls outside {term.code} ({term.starts_on} to {term.ends_on})."
            )
        return cleaned