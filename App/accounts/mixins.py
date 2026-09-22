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

        # 1. Granular permission check
        if self.required_permission:
            if hasattr(user, 'has_permission') and user.has_permission(self.required_permission):
                return True
            return False

        # 2. Module check
        if self.required_module:
            if hasattr(user, 'has_module_access') and user.has_module_access(self.required_module):
                return True
            return False

        # 3. Infer module from request resolver
        app_name = None
        if hasattr(self.request, 'resolver_match') and self.request.resolver_match:
            app_name = getattr(self.request.resolver_match, 'app_name', None)

        app_to_module = {
            'dashboard': 'dashboard',
            'attendance': 'attendance',
            'employees': 'employees',
            'leave': 'leave',
            'overtime': 'overtime',
            'payroll': 'payroll',
            'reports': 'reports',
            'activities': 'activities',
            'accounts': 'users',
        }
        module_key = app_to_module.get(app_name)

        # For custom roles: verify module access
        if hasattr(user, 'role_obj') and user.role_obj and not user.role_obj.is_system:
            if module_key and hasattr(user, 'has_module_access'):
                return user.has_module_access(module_key)
            return False

        # 4. System roles fallback (hr_admin, manager, employee)
        if self.required_roles:
            user_role = getattr(user, 'role', None)
            if user_role in self.required_roles:
                if module_key and hasattr(user, 'has_module_access') and getattr(user, 'role_obj', None):
                    return user.has_module_access(module_key)
                return True
            return False

        return True

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
