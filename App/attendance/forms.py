import datetime
from django import forms
from django.utils import timezone
from .models import Attendance, LunchBreak
from employees.models import Employee

class LunchBreakForm(forms.ModelForm):
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        initial='12:00'
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        initial='13:00'
    )

    class Meta:
        model = LunchBreak
        fields = [
            'name', 'break_type', 'company', 'start_time', 'end_time',
            'duration_minutes', 'auto_deduct', 'min_work_hours', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Standard Lunch Break'}),
            'break_type': forms.Select(attrs={'class': 'form-select'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': '60'}),
            'min_work_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'placeholder': '4.00'}),
            'auto_deduct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.start_time:
                self.initial['start_time'] = self.instance.start_time.strftime('%H:%M')
            if self.instance.end_time:
                self.initial['end_time'] = self.instance.end_time.strftime('%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        st = cleaned_data.get('start_time')
        et = cleaned_data.get('end_time')
        duration = cleaned_data.get('duration_minutes')

        if st and et:
            st_dt = datetime.datetime.combine(datetime.date(2000, 1, 1), st)
            et_dt = datetime.datetime.combine(datetime.date(2000, 1, 1), et)
            if et < st:
                et_dt += datetime.timedelta(days=1)
            diff_mins = int((et_dt - st_dt).total_seconds() // 60)
            if not duration:
                cleaned_data['duration_minutes'] = diff_mins
        return cleaned_data


class AttendanceForm(forms.ModelForm):
    check_in = forms.CharField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )
    check_out = forms.CharField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )

    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'check_in', 'check_out', 'status']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.check_in:
                # Format to HH:MM for HTML5 time input
                self.initial['check_in'] = self.instance.check_in.strftime('%H:%M')
            if self.instance.check_out:
                self.initial['check_out'] = self.instance.check_out.strftime('%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        date_val = cleaned_data.get('date')
        status = cleaned_data.get('status')
        check_in_raw = cleaned_data.get('check_in')
        check_out_raw = cleaned_data.get('check_out')

        if status == 'absent':
            cleaned_data['check_in'] = None
            cleaned_data['check_out'] = None
            return cleaned_data

        current_tz = timezone.get_current_timezone()

        def parse_time_str(val):
            if not val:
                return None
            val_str = str(val).strip()
            if 'T' in val_str:
                val_str = val_str.split('T')[-1]
            elif ' ' in val_str:
                val_str = val_str.split(' ')[-1]
            for fmt in ('%H:%M:%S', '%H:%M'):
                try:
                    return datetime.datetime.strptime(val_str, fmt).time()
                except ValueError:
                    pass
            return None

        ci_time = parse_time_str(check_in_raw)
        co_time = parse_time_str(check_out_raw)

        ci_dt = None
        co_dt = None

        if date_val and ci_time:
            naive_ci = datetime.datetime.combine(date_val, ci_time)
            ci_dt = timezone.make_aware(naive_ci, current_tz) if timezone.is_aware(timezone.now()) else naive_ci

        if date_val and co_time:
            end_d = date_val + datetime.timedelta(days=1) if (ci_time and co_time < ci_time) else date_val
            naive_co = datetime.datetime.combine(end_d, co_time)
            co_dt = timezone.make_aware(naive_co, current_tz) if timezone.is_aware(timezone.now()) else naive_co

        cleaned_data['check_in'] = ci_dt
        cleaned_data['check_out'] = co_dt

        employee = cleaned_data.get('employee')
        if status == 'early_leave':
            cleaned_data['status'] = 'checkout_early'
        elif status in ('present', '', None) and employee and date_val and (ci_dt or co_dt):
            from .services import AttendanceService
            cleaned_data['status'] = AttendanceService.determine_status(
                employee, date_val, ci_dt, co_dt, user_status=status
            )

        return cleaned_data
