"""`manage.py lock_term <CODE>` — close a term to further attendance writes."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import AcademicTerm
from analytics.services import refresh_summaries


class Command(BaseCommand):
    help = "Lock an academic term, refreshing its summaries as part of the same transaction."

    def add_arguments(self, parser):
        parser.add_argument("code", help="Academic term code.")
        parser.add_argument(
            "--unlock", action="store_true", help="Unlock the term instead of locking it."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            term = AcademicTerm.objects.select_for_update().get(code=options["code"])
        except AcademicTerm.DoesNotExist:
            raise CommandError(f"No academic term with code {options['code']!r}.")

        if options["unlock"]:
            term.is_locked = False
            term.save(update_fields=["is_locked"])
            self.stdout.write(self.style.WARNING(f"{term.code} is now unlocked."))
            return

        if term.is_locked:
            self.stdout.write(f"{term.code} was already locked.")
            return

        count = refresh_summaries(term)
        term.is_locked = True
        term.save(update_fields=["is_locked"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Locked {term.code} after refreshing {count} summary rows. "
                "Attendance writes will now return HTTP 409."
            )
        )