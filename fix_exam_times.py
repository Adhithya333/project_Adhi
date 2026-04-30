"""
Fix exam start_time and end_time that were stored as UTC when they should be EXAM_TIMEZONE (IST).
When staff in India entered 9:16 PM local, it was stored as 9:16 PM UTC (wrong).
This command re-interprets the stored date+time as EXAM_TIMEZONE local and saves the correct UTC.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import datetime

from exams.models import Exam


class Command(BaseCommand):
    help = 'Fix exam start_time/end_time that were stored as local time wrongly interpreted as UTC'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without saving')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        tz_name = getattr(settings, 'EXAM_TIMEZONE', 'Asia/Kolkata')
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
        except ImportError:
            import pytz
            tz = pytz.timezone(tz_name)
        fixed = 0
        for exam in Exam.objects.exclude(start_time__isnull=True):
            old_start = exam.start_time
            dt_local = datetime(
                old_start.year, old_start.month, old_start.day,
                old_start.hour, old_start.minute, old_start.second,
                tzinfo=tz
            )
            new_start = dt_local.astimezone(timezone.utc)
            if old_start != new_start:
                self.stdout.write(f'  {exam.title}: start {old_start} -> {new_start} (as {tz_name})')
                if not dry_run:
                    exam.start_time = new_start
                    exam.save(update_fields=['start_time'])
                fixed += 1
        for exam in Exam.objects.exclude(end_time__isnull=True):
            old_end = exam.end_time
            dt_local = datetime(
                old_end.year, old_end.month, old_end.day,
                old_end.hour, old_end.minute, old_end.second,
                tzinfo=tz
            )
            new_end = dt_local.astimezone(timezone.utc)
            if old_end != new_end:
                self.stdout.write(f'  {exam.title}: end {old_end} -> {new_end} (as {tz_name})')
                if not dry_run:
                    exam.end_time = new_end
                    exam.save(update_fields=['end_time'])
                fixed += 1
        if dry_run and fixed:
            self.stdout.write(self.style.WARNING(f'Dry run: would fix {fixed} exam time(s). Run without --dry-run to apply.'))
        elif fixed:
            self.stdout.write(self.style.SUCCESS(f'Fixed {fixed} exam time(s).'))
        else:
            self.stdout.write('No exam times needed fixing.')
