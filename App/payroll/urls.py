from django.urls import path
from .views import (
    MyPayslipListView, PayslipDetailView, PayslipPdfExportView,
    PayrollListView, PayrollListExcelExportView, PayrollListPdfExportView,
    PayrollDeleteView,
    SalarySetupView, SalaryStructureCreateView, SalaryStructureUpdateView, SalaryStructureDeleteView,
    BonusIncentiveView, BonusAddView, AllowanceView, NewPayrollView, FormulaGuideView
)

app_name = 'payroll'

urlpatterns = [
    path('', PayrollListView.as_view(), name='list'),
    path('export/excel/', PayrollListExcelExportView.as_view(), name='export_excel'),
    path('export/pdf/', PayrollListPdfExportView.as_view(), name='export_pdf'),
    path('salary-setup/', SalarySetupView.as_view(), name='salary_setup'),
    path('salary-setup/create/', SalaryStructureCreateView.as_view(), name='salary_setup_create'),
    path('salary-setup/<int:pk>/edit/', SalaryStructureUpdateView.as_view(), name='salary_setup_update'),
    path('salary-setup/<int:pk>/delete/', SalaryStructureDeleteView.as_view(), name='salary_setup_delete'),
    path('bonuses/', BonusIncentiveView.as_view(), name='bonuses'),
    path('bonuses/<int:pk>/add/', BonusAddView.as_view(), name='bonus_add'),
    path('allowances/', AllowanceView.as_view(), name='allowances'),
    path('new-payroll/', NewPayrollView.as_view(), name='new_payroll'),
    path('formula-guide/', FormulaGuideView.as_view(), name='formula_guide'),
    path('my/', MyPayslipListView.as_view(), name='my_payslips'),
    path('<int:pk>/payslip/', PayslipDetailView.as_view(), name='payslip'),
    path('<int:pk>/payslip/pdf/', PayslipPdfExportView.as_view(), name='payslip_pdf'),
    path('<int:pk>/delete/', PayrollDeleteView.as_view(), name='delete'),
]
