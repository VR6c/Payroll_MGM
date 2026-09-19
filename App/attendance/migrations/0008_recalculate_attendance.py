import datetime
from django.db import migrations
from django.utils import timezone

def recalculate_attendance_working_hours(apps, schema_editor):
    Attendance = apps.get_model('attendance', 'Attendance')
    LunchBreak = apps.get_model('attendance', 'LunchBreak')
    
    breaks = list(LunchBreak.objects.filter(status=True, auto_deduct=True))
    if not breaks:
        b = LunchBreak.objects.create(
            name='Standard Lunch Break',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(13, 0),
            duration_minutes=60,
            auto_deduct=True,
            status=True
        )
        breaks = [b]
    
    for att in Attendance.objects.filter(check_in__isnull=False, check_out__isnull=False):
        raw = att.check_out - att.check_in
        if raw.total_seconds() > 0:
            target_date = att.date or att.check_in.date()
            total_deduct = datetime.timedelta(0)
            for b in breaks:
                if b.start_time and b.end_time:
                    tz = att.check_in.tzinfo
                    naive_start = datetime.datetime.combine(target_date, b.start_time)
                    naive_end = datetime.datetime.combine(target_date, b.end_time)
                    if b.end_time < b.start_time:
                        naive_end += datetime.timedelta(days=1)

                    if tz:
                        b_start = timezone.make_aware(naive_start, tz) if timezone.is_naive(naive_start) else naive_start
                        b_end = timezone.make_aware(naive_end, tz) if timezone.is_naive(naive_end) else naive_end
                    else:
                        b_start = naive_start
                        b_end = naive_end
                    
                    ov_start = max(att.check_in, b_start)
                    ov_end = min(att.check_out, b_end)
                    if ov_end > ov_start:
                        total_deduct += (ov_end - ov_start)
            
            att.working_hours = max(datetime.timedelta(0), raw - total_deduct)
            att.save(update_fields=['working_hours'])

class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0007_lunchbreak'),
    ]

    operations = [
        migrations.RunPython(recalculate_attendance_working_hours, migrations.RunPython.noop),
    ]
