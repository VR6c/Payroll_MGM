from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    required_roles = []
    required_module = None
    required_permission = None

    def test_func(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, 'role', None) == 'super_admin':
            return True
        if not self.required_roles and not self.required_module and not self.required_permission:
            return True
        if self.required_roles and getattr(user, 'role', None) in self.required_roles:
            return True
        if self.required_permission and hasattr(user, 'has_permission'):
            if user.has_permission(self.required_permission):
                return True
        if self.required_module and hasattr(user, 'has_module_access'):
            if user.has_module_access(self.required_module):
                return True
        return False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You do not have permission to access this page.")
        return super().handle_no_permission()

class FieldPermissionMixin:
    FIELD_PERMISSIONS = {
        'super_admin': '__all__',
        'hr_admin': '__all__',
        'manager': ['first_name', 'last_name', 'department', 'position', 'status', 'join_date'],
        'employee': ['first_name', 'last_name', 'phone', 'address', 'photo'],
    }

    def get_allowed_fields(self):
        role = getattr(self.request.user, 'role', None)
        allowed = self.FIELD_PERMISSIONS.get(role, [])
        return None if allowed == '__all__' else allowed

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        allowed = self.get_allowed_fields()
        if allowed is not None:
            for field_name in list(form.fields.keys()):
                if field_name not in allowed:
                    del form.fields[field_name]
        return form
