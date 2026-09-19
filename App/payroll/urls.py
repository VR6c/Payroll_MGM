from django.urls import path
from .views import (
    MyPayslipListView, PayslipDetailView, PayrollListView, PayrollDeleteView,
    SalarySetupView, SalaryStructureCreateView, SalaryStructureUpdateView, SalaryStructureDeleteView,
    BonusIncentiveView, BonusAddView, AllowanceView, NewPayrollView
)
app_name = 'payroll'
urlpatterns = [
    path('', PayrollListView.as_view(), name='list'),
    path('salary-setup/', SalarySetupView.as_view(), name='salary_setup'),
    path('salary-setup/create/', SalaryStructureCreateView.as_view(), name='salary_setup_create'),
    path('salary-setup/<int:pk>/edit/', SalaryStructureUpdateView.as_view(), name='salary_setup_update'),
    path('salary-setup/<int:pk>/delete/', SalaryStructureDeleteView.as_view(), name='salary_setup_delete'),
    path('bonuses/', BonusIncentiveView.as_view(), name='bonuses'),
    path('bonuses/<int:pk>/add/', BonusAddView.as_view(), name='bonus_add'),
    path('allowances/', AllowanceView.as_view(), name='allowances'),
    path('new-payroll/', NewPayrollView.as_view(), name='new_payroll'),
    path('my/', MyPayslipListView.as_view(), name='my_payslips'),
    path('<int:pk>/payslip/', PayslipDetailView.as_view(), name='payslip'),
    path('<int:pk>/delete/', PayrollDeleteView.as_view(), name='delete'),
]


