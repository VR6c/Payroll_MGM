# Payroll Management System

A Django-based HR & Payroll Management System covering employee records, attendance, leave, payroll processing, loans/advances, and management reporting, with role-based access for Super Admins, HR Admins, Managers, and Employees.

## Features
- **Employee & Company Management**
- **Attendance & Leave Tracking**
- **Loans & Salary Advances**
- **Automated Payroll Generation & Reports**
- **Role-Aware Dashboard with Analytics**
- **MySQL & SQLite Support**
- **Docker & Docker Compose Ready**
- **GitHub Actions CI/CD Pipeline**

---

## Quick Start with Docker Compose

1. **Clone the repository:**
   ```bash
   git clone https://github.com/loemratana/payroll-system.git
   cd payroll-system
   ```

2. **Start application containers:**
   ```bash
   docker compose up -d --build
   ```

3. Access the application in your browser at `http://localhost:8000`.

---

## Manual / Local Setup

1. **Create and activate virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run database migrations:**
   ```bash
   USE_MYSQL=false python manage.py migrate
   ```

4. **Run unit tests:**
   ```bash
   USE_MYSQL=false python manage.py test
   ```

5. **Start development server:**
   ```bash
   USE_MYSQL=false python manage.py runserver
   ```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 5.1 (Python) |
| Database | MySQL (via PyMySQL), with SQLite fallback for local dev (`USE_MYSQL=false`) |
| Frontend | Django Templates + Bootstrap 5, `django-crispy-forms` / `crispy-bootstrap5`, jQuery, Select2, Chart.js, Material Design Icons |
| Auth | Custom `User` model (`accounts.User`, extends `AbstractUser`) with a `role` field |
| Deployment | Docker + `docker-compose.yml`, GitHub Actions CI |
| Other | Pillow (image uploads), python-dateutil, factory-boy (test fixtures) |

## Architecture

- Django project root: `config/` (settings, root `urls.py`, business-rule loader).
- All apps live under `App/` (added to `sys.path` in settings so they import as top-level packages, e.g. `from employees.models import Employee`).
- Templates are centralized under `templates/<app>/*.html` (not per-app), sharing one `base.html` with a consistent design system (`hrms-*` CSS classes in `static/assets/css/app.css`).
- Static design system: CSS custom properties (`--app-primary`, `--app-border`, etc.) defined in `app.css`, layered on top of a Bootstrap-based admin template (`style.css`).

## Role Model

Defined in `accounts.User.Role`:
- **super_admin** — full access across all modules.
- **hr_admin** — full access to HR/payroll operations (mirrors super_admin in most permission checks).
- **manager** — read/limited-write access to team-facing views (employees, attendance, leave, schedules).
- **employee** — self-service only (own attendance, leave requests, payslips, loans).

Access control is enforced via `accounts.mixins.RoleRequiredMixin` (`required_roles = [...]` per view) and `LoginRequiredMixin` for self-service views.

---

## Module Breakdown

### 1. `accounts` — Authentication & Shared Infrastructure
- **Model**: `User(AbstractUser)` with `role` (choices above) and `phone`.
- **Purpose**: login/logout/password-change, and houses cross-cutting view mixins used by every other app:
  - `RoleRequiredMixin` — restricts a view to a list of roles, raises `PermissionDenied` otherwise.
  - `FieldPermissionMixin` — strips form fields a role isn't allowed to edit (e.g. a manager can't edit salary).
  - `ModalFormMixin` — for Create/Update/Delete views whose only UI is an inline modal on a list page (no dedicated full-page template); redirects bare GETs and invalid POSTs back to the list with an error message instead of crashing.
  - `csv_response(filename, header, rows)` — shared helper used by every module's CSV export views.
- Also defines `SecureSessionMiddleware` (session hardening).

### 2. `companies` — Organization Structure & Settings
- **Models**:
  - `Company` — name, logo, contact info, timezone.
  - `Department` — belongs to a Company.
  - `Position` — belongs to a Company and optionally a Department.
  - `BusinessRuleSettings` — a singleton row of configurable payroll/leave/attendance rules (tax rate, NSSF rate, overtime multiplier, currency symbol, leave carry-over cap, leave notice period, standard work hours, attendance grace period). Falls back to `config/rules.py` / `config/business_rules.json` defaults until a row exists (`get_solo()`).
- **Views**: `CompanySettingsView` — single settings page with two forms (company profile + business rules).
- **URL**: `/company/settings/`.

### 3. `employees` — Employee, Department & Position Management
- **Model**: `Employee` — linked 1:1 to a `User` (optional), belongs to a Company/Department/Position, has a self-referencing `manager` FK, tracks `basic_salary`, `join_date`, `status` (active/inactive/resigned/terminated). Supports soft-delete (`soft_delete()`) and GDPR-style `anonymize()`. Uses a custom manager (`ActiveEmployeeManager`) that hides soft-deleted/anonymized rows by default (`all_objects` for the unfiltered set).
- **Views**:
  - `EmployeeListView` — searchable/filterable directory (search, department, status, configurable page size).
  - `EmployeeCreateView` / `EmployeeUpdateView` (role-gated field permissions) / `EmployeeDetailView` (profile page with leave balances, recent attendance, salary structure, recent payrolls).
  - `PositionListView` / `DepartmentListView` and their Create/Update/Delete (modal-based).
  - CSV export views for the employee list, positions, and departments.
- **URLs**: `/employees/`, `/employees/positions/`, `/employees/departments/`, plus `/create/`, `/<pk>/`, `/<pk>/edit/`, and `.../export/` variants.

### 4. `attendance` — Daily Attendance & Work Schedules
- **Models**:
  - `Attendance` — one row per employee per day (check-in/out, computed `working_hours`, status: present/late/absent/early_leave/overtime).
  - `WorkSchedule` — named shift template (start/end/late-after/early-leave thresholds).
  - `EmployeeSchedule` — per-employee, per-day-of-week schedule (flexible or standard, supports split/half-day shifts); provides `get_weekly_matrices_for_employees()` to build the weekly grid used by the schedule UI.
- **Services**: `AttendanceService` (check-in/check-out logic), `ScheduleService` (save/read an employee's weekly schedule).
- **Views**:
  - `CheckInView` / `CheckOutView` — self-service, called from the dashboard.
  - `MyAttendanceView` — personal attendance history.
  - `AttendanceReportView` — company-wide attendance table with filters (status, type shortcut, date) and inline create/edit/delete modals.
  - `WorkScheduleListView` — weekly schedule grid with department/position/search filters and grouping; `SaveEmployeeScheduleView` / `GetEmployeeScheduleView` back the "Edit Work Schedule" modal via JSON endpoints.
  - CSV export views for my-attendance, the attendance report, and the schedule grid — all respecting the same filters as their on-screen counterparts.
- **URLs**: `/attendance/check-in/`, `/check-out/`, `/my/`, `/schedules/`, `/report/`, plus export/API endpoints.

### 5. `leave` — Leave Requests, Types & Balances
- **Models**:
  - `LeaveType` — per-company leave category (default annual days, paid/unpaid, active flag).
  - `LeaveRequest` — employee's request (leave type, reason, computed `total_days`, status: pending/approved/rejected/cancelled, approver).
  - `LeavePeriod` — one or more date ranges attached to a request (supports split leave).
  - `LeaveBalance` — per employee/leave-type/year allocation (allocated / used / remaining days).
- **Views**:
  - `LeaveRequestCreateView` — the "New Leave Request" form: leave type + reason, dynamic period rows (auto-computed day counts), with a sidebar showing the employee's current-year balances.
  - `MyLeaveListView` — personal leave history + balances.
  - `LeaveTypeListView` / `LeaveTypeGroupListView` (balance allocation table) and their modal-based Create/Update/Delete.
  - CSV export views for my-leaves, leave types, and leave balances.
- **URLs**: `/leave/`, `/leave/create/`, `/leave/types/`, `/leave/type-groups/`, plus export variants.
- **Note**: there is currently no admin-facing "all leave requests / approve-reject" view — `MyLeaveListView` is always scoped to `request.user`. Leave requests get a `status` field but no in-app approval workflow view yet (a gap worth closing in a future iteration).

### 6. `payroll` — Salary Structures, Payroll Runs & Payslips
- **Models**:
  - `SalaryStructure` — an employee's basic salary + allowances (transportation, housing, meal, other), with an effective date and active flag.
  - `Payroll` — one generated payroll record per employee per period (basic, overtime, allowance, bonus → gross; tax, NSSF, loan deduction, other deduction → total deduction; net salary; status: draft/processing/approved/paid/cancelled).
- **Services**: `PayrollCalculator` — computes a payroll run for an employee for a period (applies loan deductions via `loans.PayrollLoanDeduction`, prorates for mid-period joiners, recalculates totals when a bonus is added).
- **Views**:
  - `PayrollListView` — company-wide payroll runs, filterable by status/period.
  - `SalaryStructureView`/`SalarySetupView`, `AllowanceView`, `BonusIncentiveView` — management tables for salary components and bonuses (modal-based create/update/delete).
  - `NewPayrollView` — bulk-generates payroll for all active employees for a chosen period.
  - `PayslipDetailView` / `MyPayslipListView` — individual payslip view and self-service payslip history.
  - CSV export views for the payroll list, salary setup, bonuses, allowances, and my-payslips.
- **URLs**: `/payroll/`, `/payroll/salary-setup/`, `/payroll/bonuses/`, `/payroll/allowances/`, `/payroll/new-payroll/`, `/payroll/my/`, `/payroll/<pk>/payslip/`, plus export variants.

### 7. `loans` — Employee Loans & Salary Advances
- **Models**:
  - `Loan` — type (loan/advance), principal, monthly installment, remaining balance, start period, status (pending/approved/rejected/completed/cancelled), requested-by/approved-by.
  - `PayrollLoanDeduction` — per-payroll-run record of how much of a loan was deducted, so a regenerated draft payroll doesn't double-deduct.
- **Views**:
  - `LoanListView` — HR-facing list with status/type/search filters, approve/reject actions, and a "record loan" modal that auto-approves (HR-initiated loans).
  - `MyLoanListView` / `MyLoanCreateView` — employee self-service request flow (starts as pending, awaiting approval).
  - CSV export views for the loan list and my-loans.
- **URLs**: `/loans/`, `/loans/create/`, `/loans/<pk>/approve/`, `/reject/`, `/loans/my/`, plus export variants.

### 8. `reports` — Management Reporting
- **Views** (all `TemplateView`, read-only aggregation):
  - `DailyReportView` — today's attendance snapshot (present/late/absent counts + full list).
  - `SummaryReportView` — headcount, active count, total net payroll paid, pending leave count, last 20 payroll records.
  - `DetailReportView` — full employee ledger (code, name, department, position, basic salary, status).
- Each report has a CSV export endpoint alongside a browser "Print" button (for a PDF-style printout).
- **URLs**: `/reports/daily/`, `/reports/summary/`, `/reports/detail/`, plus export variants.

### 9. `dashboard` — Role-Aware Landing Page
- **View**: `DashboardView`, branches by role:
  - **Employee**: today's attendance status, leave balance summary, latest payslip, quick check-in/out actions, recent leave requests.
  - **Admin/HR/Manager**: headcount + today's attendance breakdown (present/late/early-leave/absent) and pending-leave count as stat tiles; a "Recent Employees" table; a system activity stream; and three Chart.js visualizations:
    - **Attendance Trend** — daily present/late/absent counts, last 14 days.
    - **Payroll Trend** — net salary paid per month, last 6 months.
    - **Leave Requests** — breakdown by status for the current year.
- All chart data is computed server-side (`App/dashboard/views.py`) and passed to the template via Django's `json_script` filter (no unsafe inline JSON).

### 10. `activities` — Audit / Activity Log
- **Model**: `Activity` — user, optionally linked employee, module, action, description, timestamp. Indexed for recent-first queries.
- **Purpose**: powers the "System Activity Stream" on the admin dashboard; a lightweight, append-only audit trail of notable actions across modules.

---

## Cross-Cutting Patterns Worth Knowing

- **CSV export convention**: every list/report view has a matching `*ExportView` that reuses the exact same filtering logic as the page (via a shared `filter_*()` function) and streams CSV via `accounts.mixins.csv_response`. Export buttons pass the current `request.GET` querystring through so the download always matches what's on screen.
- **Modal-only forms**: most "Add/Edit/Delete" actions across the app are inline Bootstrap modals on the list page rather than separate pages — the corresponding Create/Update/Delete views intentionally have no full-page template and use `ModalFormMixin` to redirect safely if hit directly (bare GET, or a failed POST validation) instead of crashing.
- **Design system**: shared `hrms-*` CSS classes (page headers, stat tiles, data tables, status pills, pagination) keep every module visually consistent; colors/spacing are driven by CSS custom properties in `app.css`.
