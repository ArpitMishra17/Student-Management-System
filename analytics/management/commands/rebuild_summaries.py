"""`manage.py rebuild_summaries --term <CODE>`"""

from django.core.management.base import BaseCommand, CommandError

from analytics.models import AcademicTerm
from analytics.services import refresh_summaries


class Command(BaseCommand):
    help = "Recompute StudentAttendanceSummary rows for one academic term."

    def add_arguments(self, parser):
        parser.add_argument("--term", required=True, help="Academic term code, e.g. SEM-2024-01.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute the standings and report them without writing to the database.",
        )

    def handle(self, *args, **options):
        code = options["term"]
        try:
            term = AcademicTerm.objects.get(code=code)
        except AcademicTerm.DoesNotExist:
            raise CommandError(f"No academic term with code {code!r}.")

        if options["dry_run"]:
            from analytics.services import build_standings

            standings = build_standings(term)
            self.stdout.write(f"[dry-run] would write {len(standings)} summary rows.")
            for standing in standings[:10]:
                self.stdout.write(
                    f"  {standing.display_name:<30} {standing.percentage:>6}%  {standing.risk_band}"
                )
            return

        count = refresh_summaries(term)
        self.stdout.write(self.style.SUCCESS(f"Wrote {count} summary rows for {term.code}."))