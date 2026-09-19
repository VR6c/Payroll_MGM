from django.urls import path
from .views import (
    LeaveRequestCreateView, MyLeaveListView,
    LeaveTypeListView, LeaveTypeCreateView, LeaveTypeUpdateView, LeaveTypeDeleteView,
    LeaveTypeGroupListView, LeaveBalanceCreateView, LeaveBalanceUpdateView, LeaveBalanceDeleteView
)
app_name = 'leave'
urlpatterns = [
    path('', MyLeaveListView.as_view(), name='my_leaves'),
    path('create/', LeaveRequestCreateView.as_view(), name='create'),
    path('types/', LeaveTypeListView.as_view(), name='types'),
    path('types/create/', LeaveTypeCreateView.as_view(), name='type_create'),
    path('types/<int:pk>/edit/', LeaveTypeUpdateView.as_view(), name='type_update'),
    path('types/<int:pk>/delete/', LeaveTypeDeleteView.as_view(), name='type_delete'),
    path('type-groups/', LeaveTypeGroupListView.as_view(), name='type_groups'),
    path('type-groups/create/', LeaveBalanceCreateView.as_view(), name='type_group_create'),
    path('type-groups/<int:pk>/edit/', LeaveBalanceUpdateView.as_view(), name='type_group_update'),
    path('type-groups/<int:pk>/delete/', LeaveBalanceDeleteView.as_view(), name='type_group_delete'),
]


