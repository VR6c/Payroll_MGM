from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from django.http import HttpResponse

urlpatterns = [
    path('.well-known/appspecific/com.chrome.devtools.json', lambda r: HttpResponse(status=204)),
    path('', RedirectView.as_view(pattern_name='accounts:login', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('employees/', include('employees.urls')),
    path('attendance/', include('attendance.urls')),
    path('leave/', include('leave.urls')),
    path('payroll/', include('payroll.urls')),
    path('activities/', include('activities.urls')),
    path('reports/', include('reports.urls')),
    path('overtime/', include('overtime.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


