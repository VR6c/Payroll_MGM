from .models import Activity

def log_activity(user, employee=None, module='', action='', description=''):
    Activity.objects.create(user=user, employee=employee, module=module, action=action, description=description)
