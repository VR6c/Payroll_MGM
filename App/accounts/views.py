from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
from accounts.mixins import RoleRequiredMixin
from employees.models import Employee
from .models import Role, PERMISSION_CATALOG
from .forms import (
    UserCreateForm, UserUpdateForm, UserAdminPasswordResetForm, RoleForm
)

User = get_user_model()


class UserManagementListView(RoleRequiredMixin, ListView):
    model = User
    template_name = 'accounts/users.html'
    context_object_name = 'users'
    paginate_by = 15
    required_roles = ['super_admin']

    def get_queryset(self):
        qs = User.objects.select_related('employee_profile').order_by('-date_joined')

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            qs = qs.filter(
                Q(username__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query)
            )

        role_filter = self.request.GET.get('role', '').strip()
        if role_filter:
            qs = qs.filter(role=role_filter)

        status_filter = self.request.GET.get('status', '').strip()
        if status_filter == 'active':
            qs = qs.filter(is_active=True)
        elif status_filter == 'inactive':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_users = User.objects.all()

        ctx['total_users'] = all_users.count()
        ctx['super_admin_count'] = all_users.filter(role='super_admin').count()
        ctx['hr_admin_count'] = all_users.filter(role='hr_admin').count()
        ctx['manager_count'] = all_users.filter(role='manager').count()
        ctx['employee_count'] = all_users.filter(role='employee').count()
        ctx['active_users_count'] = all_users.filter(is_active=True).count()
        ctx['inactive_users_count'] = all_users.filter(is_active=False).count()

        ctx['create_form'] = UserCreateForm()
        ctx['password_reset_form'] = UserAdminPasswordResetForm()
        ctx['roles_list'] = Role.objects.all().order_by('-is_system', 'name')
        ctx['role_choices'] = [(r.code, r.name) for r in ctx['roles_list']]
        ctx['unlinked_employees'] = Employee.objects.filter(user__isnull=True).order_by('first_name', 'last_name')
        ctx['all_employees'] = Employee.objects.all().order_by('first_name', 'last_name')

        ctx['active_search'] = self.request.GET.get('search', '').strip()
        ctx['active_role'] = self.request.GET.get('role', '').strip()
        ctx['active_status'] = self.request.GET.get('status', '').strip()

        return ctx


class UserCreateView(RoleRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    success_url = reverse_lazy('accounts:user_list')
    required_roles = ['super_admin']

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"User '{user.username}' ({user.get_role_display()}) was created successfully!"
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                field_label = field.replace('_', ' ').title() if field != '__all__' else 'Error'
                messages.error(self.request, f"{field_label}: {error}")
        return redirect('accounts:user_list')


class UserUpdateView(RoleRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    success_url = reverse_lazy('accounts:user_list')
    required_roles = ['super_admin']

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"User '{user.username}' details and role were updated successfully!"
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                field_label = field.replace('_', ' ').title() if field != '__all__' else 'Error'
                messages.error(self.request, f"{field_label}: {error}")
        return redirect('accounts:user_list')


class UserPasswordResetView(RoleRequiredMixin, View):
    required_roles = ['super_admin']

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        form = UserAdminPasswordResetForm(request.POST)
        if form.is_valid():
            form.save(user)
            messages.success(request, f"Password for user '{user.username}' was reset successfully!")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Password Reset Error: {error}")
        return redirect('accounts:user_list')


class UserStatusToggleView(RoleRequiredMixin, View):
    required_roles = ['super_admin']

    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)

        if target == request.user:
            messages.error(request, "Security alert: You cannot deactivate your own account.")
            return redirect('accounts:user_list')

        if target.is_active and (target.role == 'super_admin' or target.is_superuser):
            other_active = User.objects.filter(
                Q(role='super_admin') | Q(is_superuser=True),
                is_active=True
            ).exclude(pk=target.pk).count()
            if other_active == 0:
                messages.error(request, "Action blocked: Cannot deactivate the only active Super Admin.")
                return redirect('accounts:user_list')

        target.is_active = not target.is_active
        target.save()
        status_label = "activated" if target.is_active else "deactivated"
        messages.success(request, f"User '{target.username}' was successfully {status_label}.")
        return redirect('accounts:user_list')


class UserDeleteView(RoleRequiredMixin, View):
    required_roles = ['super_admin']

    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)

        if target == request.user:
            messages.error(request, "Security alert: You cannot delete your own account.")
            return redirect('accounts:user_list')

        if target.role == 'super_admin' or target.is_superuser:
            other_admins = User.objects.filter(
                Q(role='super_admin') | Q(is_superuser=True)
            ).exclude(pk=target.pk).count()
            if other_admins == 0:
                messages.error(request, "Action blocked: Cannot delete the only Super Admin in the system.")
                return redirect('accounts:user_list')

        username = target.username
        target.delete()
        messages.success(request, f"User '{username}' was permanently deleted.")
        return redirect('accounts:user_list')


# ==============================================================================
# Access Role (RBAC) CRUD Views
# ==============================================================================

class RoleListView(RoleRequiredMixin, ListView):
    model = Role
    template_name = 'accounts/roles.html'
    context_object_name = 'roles'
    paginate_by = 20
    required_roles = ['super_admin']

    def get_queryset(self):
        qs = Role.objects.all().order_by('-is_system', 'name')
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(code__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_roles = Role.objects.all()

        ctx['total_roles'] = all_roles.count()
        ctx['system_roles_count'] = all_roles.filter(is_system=True).count()
        ctx['custom_roles_count'] = all_roles.filter(is_system=False).count()
        ctx['total_assigned_users'] = User.objects.count()

        ctx['create_role_form'] = RoleForm()
        ctx['module_choices'] = Role.MODULE_CHOICES
        ctx['permission_catalog'] = PERMISSION_CATALOG
        ctx['active_search'] = self.request.GET.get('search', '').strip()

        return ctx


class RoleCreateView(RoleRequiredMixin, CreateView):
    model = Role
    form_class = RoleForm
    success_url = reverse_lazy('accounts:role_list')
    required_roles = ['super_admin']

    def form_valid(self, form):
        role = form.save()
        messages.success(self.request, f"Access Role '{role.name}' ({role.code}) was created successfully!")
        return redirect(self.success_url)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                field_label = field.replace('_', ' ').title() if field != '__all__' else 'Error'
                messages.error(self.request, f"{field_label}: {error}")
        return redirect('accounts:role_list')


class RoleUpdateView(RoleRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    success_url = reverse_lazy('accounts:role_list')
    required_roles = ['super_admin']

    def form_valid(self, form):
        role = form.save()
        messages.success(self.request, f"Access Role '{role.name}' updated successfully!")
        return redirect(self.success_url)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                field_label = field.replace('_', ' ').title() if field != '__all__' else 'Error'
                messages.error(self.request, f"{field_label}: {error}")
        return redirect('accounts:role_list')


class RoleDeleteView(RoleRequiredMixin, View):
    required_roles = ['super_admin']

    def post(self, request, pk):
        role = get_object_or_404(Role, pk=pk)

        if role.is_system:
            messages.error(request, f"Security alert: Core system role '{role.name}' cannot be deleted.")
            return redirect('accounts:role_list')

        assigned_users_count = User.objects.filter(role=role.code).count()
        if assigned_users_count > 0:
            messages.error(
                request,
                f"Action blocked: Role '{role.name}' is currently assigned to {assigned_users_count} user(s). "
                f"Please reassign those users to another role before deleting."
            )
            return redirect('accounts:role_list')

        role_name = role.name
        role.delete()
        messages.success(request, f"Access Role '{role_name}' was permanently deleted.")
        return redirect('accounts:role_list')
