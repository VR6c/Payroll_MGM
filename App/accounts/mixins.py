from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    required_roles = []

    def test_func(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if not self.required_roles:
            return True
        return getattr(user, 'role', None) in self.required_roles

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
