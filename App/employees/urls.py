from django.urls import path
from .views import (
    EmployeeListView, EmployeeCreateView, EmployeeUpdateView, EmployeeDetailView,
    PositionListView, PositionCreateView, PositionUpdateView, PositionDeleteView,
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView, DepartmentDeleteView,
    BranchListView, BranchCreateView, BranchUpdateView, BranchDeleteView
)
app_name = 'employees'
urlpatterns = [
    path('', EmployeeListView.as_view(), name='list'),
    path('branches/', BranchListView.as_view(), name='branches'),
    path('branches/create/', BranchCreateView.as_view(), name='branch_create'),
    path('branches/<int:pk>/edit/', BranchUpdateView.as_view(), name='branch_update'),
    path('branches/<int:pk>/delete/', BranchDeleteView.as_view(), name='branch_delete'),
    path('positions/', PositionListView.as_view(), name='positions'),
    path('positions/create/', PositionCreateView.as_view(), name='position_create'),
    path('positions/<int:pk>/edit/', PositionUpdateView.as_view(), name='position_update'),
    path('positions/<int:pk>/delete/', PositionDeleteView.as_view(), name='position_delete'),
    path('departments/', DepartmentListView.as_view(), name='departments'),
    path('departments/create/', DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='department_delete'),
    path('create/', EmployeeCreateView.as_view(), name='create'),
    path('<int:pk>/', EmployeeDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', EmployeeUpdateView.as_view(), name='update'),
]


