from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from accounts.mixins import RoleRequiredMixin, FieldPermissionMixin
from companies.models import Company, Department, Position, Branch
from companies.services import get_default_company
from .models import Employee
from .forms import EmployeeForm, EmployeeFilterForm, PositionForm, DepartmentForm, BranchForm


class EmployeeListView(RoleRequiredMixin, ListView):
    model = Employee
    template_name = 'employees/list.html'
    context_object_name = 'employees'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        qs = Employee.objects.select_related('company', 'branch', 'department', 'position', 'manager', 'user').all()
        form = EmployeeFilterForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('search'):
                s = form.cleaned_data['search']
                qs = qs.filter(Q(first_name__icontains=s) | Q(last_name__icontains=s) | Q(employee_code__icontains=s))
            if form.cleaned_data.get('branch'):
                qs = qs.filter(branch=form.cleaned_data['branch'])
            if form.cleaned_data.get('department'):
                qs = qs.filter(department=form.cleaned_data['department'])
            if form.cleaned_data.get('status'):
                qs = qs.filter(status=form.cleaned_data['status'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = EmployeeFilterForm(self.request.GET)
        return ctx


def assign_company_to_employee(form, user):
    if not hasattr(form.instance, 'company') or not form.instance.company_id:
        dept = form.cleaned_data.get('department')
        pos = form.cleaned_data.get('position')
        if dept and getattr(dept, 'company_id', None):
            form.instance.company = dept.company
        elif pos and getattr(pos, 'company_id', None):
            form.instance.company = pos.company
        elif hasattr(user, 'employee_profile') and user.employee_profile and getattr(user.employee_profile, 'company_id', None):
            form.instance.company = user.employee_profile.company
        else:
            form.instance.company = get_default_company()


class EmployeeCreateView(RoleRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/form.html'
    success_url = reverse_lazy('employees:list')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        assign_company_to_employee(form, self.request.user)
        messages.success(self.request, "Employee created successfully!")
        return super().form_valid(form)


class EmployeeUpdateView(FieldPermissionMixin, RoleRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/form.html'
    success_url = reverse_lazy('employees:list')
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def form_valid(self, form):
        assign_company_to_employee(form, self.request.user)
        messages.success(self.request, "Employee updated successfully!")
        return super().form_valid(form)


class EmployeeDetailView(RoleRequiredMixin, DetailView):
    model = Employee
    template_name = 'employees/detail.html'
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return Employee.objects.select_related('company', 'department', 'position', 'manager', 'user')


class PositionListView(RoleRequiredMixin, ListView):
    model = Position
    template_name = 'employees/positions.html'
    context_object_name = 'positions'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return Position.objects.select_related('company', 'department').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = PositionForm()
        ctx['companies'] = Company.objects.all()
        ctx['departments'] = Department.objects.filter(status=True)
        return ctx


class DefaultCompanyFormMixin:
    """Mixin to automatically assign default company if not explicitly specified in form."""
    def form_valid(self, form):
        if not form.cleaned_data.get('company'):
            form.instance.company = get_default_company()
        return super().form_valid(form)


class PositionCreateView(DefaultCompanyFormMixin, RoleRequiredMixin, CreateView):
    model = Position
    form_class = PositionForm
    success_url = reverse_lazy('employees:positions')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Position created successfully!")
        return super().form_valid(form)


class PositionUpdateView(DefaultCompanyFormMixin, RoleRequiredMixin, UpdateView):
    model = Position
    form_class = PositionForm
    success_url = reverse_lazy('employees:positions')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Position updated successfully!")
        return super().form_valid(form)


class PositionDeleteView(RoleRequiredMixin, DeleteView):
    model = Position
    success_url = reverse_lazy('employees:positions')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Position deleted successfully!")
        return super().post(request, *args, **kwargs)


class DepartmentListView(RoleRequiredMixin, ListView):
    model = Department
    template_name = 'employees/departments.html'
    context_object_name = 'departments'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return Department.objects.select_related('company').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = DepartmentForm()
        ctx['companies'] = Company.objects.all()
        return ctx


class DepartmentCreateView(DefaultCompanyFormMixin, RoleRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    success_url = reverse_lazy('employees:departments')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Department created successfully!")
        return super().form_valid(form)


class DepartmentUpdateView(DefaultCompanyFormMixin, RoleRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    success_url = reverse_lazy('employees:departments')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Department updated successfully!")
        return super().form_valid(form)


class DepartmentDeleteView(RoleRequiredMixin, DeleteView):
    model = Department
    success_url = reverse_lazy('employees:departments')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Department deleted successfully!")
        return super().post(request, *args, **kwargs)


class BranchListView(RoleRequiredMixin, ListView):
    model = Branch
    template_name = 'employees/branches.html'
    context_object_name = 'branches'
    paginate_by = 20
    required_roles = ['super_admin', 'hr_admin', 'manager']

    def get_queryset(self):
        return Branch.objects.select_related('company').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = BranchForm()
        ctx['companies'] = Company.objects.all()
        return ctx


class BranchCreateView(DefaultCompanyFormMixin, RoleRequiredMixin, CreateView):
    model = Branch
    form_class = BranchForm
    success_url = reverse_lazy('employees:branches')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Branch created successfully!")
        return super().form_valid(form)


class BranchUpdateView(DefaultCompanyFormMixin, RoleRequiredMixin, UpdateView):
    model = Branch
    form_class = BranchForm
    success_url = reverse_lazy('employees:branches')
    required_roles = ['super_admin', 'hr_admin']

    def form_valid(self, form):
        messages.success(self.request, "Branch updated successfully!")
        return super().form_valid(form)


class BranchDeleteView(RoleRequiredMixin, DeleteView):
    model = Branch
    success_url = reverse_lazy('employees:branches')
    required_roles = ['super_admin', 'hr_admin']

    def post(self, request, *args, **kwargs):
        messages.success(self.request, "Branch deleted successfully!")
        return super().post(request, *args, **kwargs)






