from django.views.generic import ListView
from accounts.mixins import RoleRequiredMixin
from .models import Activity

class ActivityListView(RoleRequiredMixin, ListView):
    model = Activity
    template_name = 'activities/list.html'
    context_object_name = 'activities'
    paginate_by = 50
    required_roles = ['super_admin', 'hr_admin']

    def get_queryset(self):
        return Activity.objects.select_related('user', 'employee').all().order_by('-created_at')
