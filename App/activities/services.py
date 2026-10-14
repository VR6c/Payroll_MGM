from .models import Activity

def log_activity(user, employee=None, module='', action='', description=''):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        return Activity.objects.create(
            user=user,
            employee=employee,
            module=module,
            action=action,
            description=description
        )
    except Exception:
        return None
