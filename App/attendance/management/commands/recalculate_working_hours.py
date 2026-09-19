from django.core.management.base import BaseCommand
from attendance.models import Attendance

class Command(BaseCommand):
    help = 'Recalculate working hours for existing attendance records applying active lunch break deductions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recalculate all records even if working_hours is already set.',
        )

    def handle(self, *args, **options):
        qs = Attendance.objects.filter(check_in__isnull=False, check_out__isnull=False)
        total = qs.count()
        self.stdout.write(f"Found {total} attendance records with check-in and check-out.")

        updated = 0
        for att in qs.select_related('employee'):
            old_wh = att.working_hours
            att.calculate_working_hours()
            if old_wh != att.working_hours:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully recalculated working hours! Total examined: {total}, Updated: {updated} records."
        ))
