from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from payroll.models import Payroll
from .models import Activity
import json

@receiver(pre_save, sender=Payroll)
def track_payroll_changes(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Payroll.objects.get(pk=instance.pk)
            changes = {}
            for field in ['basic_salary', 'overtime', 'bonus', 'tax', 'net_salary', 'status']:
                old_val = getattr(old, field)
                new_val = getattr(instance, field)
                if str(old_val) != str(new_val):
                    changes[field] = {'old': str(old_val), 'new': str(new_val)}
            if changes:
                instance._audit_changes = changes
        except Payroll.DoesNotExist:
            pass

@receiver(post_save, sender=Payroll)
def log_payroll_audit(sender, instance, created, **kwargs):
    if not created and hasattr(instance, '_audit_changes'):
        user = getattr(instance, '_updated_by_user', None) or instance.employee.user
        if not user and instance.employee.manager:
            user = instance.employee.manager.user
        if not user:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
        if user:
            Activity.objects.create(
                user=user,
                employee=instance.employee,
                module='PAYROLL',
                action='UPDATE',
                description=json.dumps(instance._audit_changes)
            )
