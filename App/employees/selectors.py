from django.db.models import Q, Prefetch
from .models import Employee
from attendance.models import Attendance
from datetime import timedelta

class EmployeeSelector:
    @staticmethod
    def get_list(company_id, filters=None):
        qs = Employee.objects.filter(company_id=company_id).select_related('department', 'position', 'manager')
        if filters:
            if filters.get('search'):
                s = filters['search']
                qs = qs.filter(Q(first_name__icontains=s) | Q(last_name__icontains=s) | Q(employee_code__icontains=s))
            if filters.get('department_id'):
                qs = qs.filter(department_id=filters['department_id'])
            if filters.get('status'):
                qs = qs.filter(status=filters['status'])
        return qs.order_by('first_name', 'last_name')
