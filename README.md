# Payroll Management System (Payroll MGM)

[![Django CI/CD Pipeline](https://github.com/VR6c/Payroll_MGM/actions/workflows/ci.yml/badge.svg)](https://github.com/VR6c/Payroll_MGM/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![Django Version](https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white)
![Database](https://img.shields.io/badge/Database-MySQL%20%7C%20SQLite-4479A1?logo=mysql&logoColor=white)
![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-TVR-green)

A production-ready, enterprise-grade **Human Resource & Payroll Management System (HRMS)** powered by Django 5.1 and modern web technologies. Designed to streamline employee lifecycle management, branch networks, attendance tracking with automated lunch break deductions, overtime approvals, leave allocations, dynamic rule-based payroll processing, multi-format reporting (Excel & PDF), and executive analytics backed by robust Role-Based Access Control (RBAC).

---

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Module Breakdown](#module-breakdown)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Quick Start with Docker Compose](#quick-start-with-docker-compose)
  - [Manual / Local Development Setup](#manual--local-development-setup)
- [Database Seeding & Management Commands](#database-seeding--management-commands)
- [Environment Configuration](#environment-configuration)
- [Business Rules & Deduction Engine](#business-rules--deduction-engine)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Project Directory Structure](#project-directory-structure)
- [Contributing & License](#contributing--license)

---

## Key Features

- **Organization & Multi-Branch Hierarchy**:
  - Manage companies, departments, job positions, and multiple operating **branches** (branch codes, physical addresses, and contact info).
  - Assign employees across branches and filter operational reports by branch and department.

- **Employee Lifecycle & Privacy Management**:
  - Full employee records (personal data, emergency contacts, hire dates, basic compensation, branch, and line manager hierarchy).
  - Lifecycle state management (`Active`, `Inactive`, `Resigned`, `Terminated`).
  - Non-destructive soft delete (`soft_delete()`) and GDPR-compliant record anonymization (`anonymize()` -> `[REDACTED]`).

- **Attendance & Lunch Break Tracking**:
  - Self-service clock-in and clock-out with automated duration calculation, late check-in, and early leave detection.
  - **Automated Lunch Break Deductions** (`LunchBreak`): Configurable break windows (Lunch, Tea, Custom) with automated duration deduction from total worked hours when qualifying shift thresholds are met.
  - Interactive weekly schedule grid supporting split shifts, half-day rules, and schedule export.
  - One-click management command to recalculate historical working hours against active break policies.

- **Overtime Management & Request Workflow**:
  - Configurable overtime rate categories (Normal Day 1.5x, Weekend 2.0x, Public Holiday 3.0x).
  - Self-service overtime submission for employees with real-time wage and payout estimations.
  - Administrative approval/rejection workflows with reason tracking and audit timestamps.
  - Dynamic hourly rate computation derived from employee salary structures and monthly standard working hours.
  - Dedicated overtime reporting with Excel (`.xlsx`) and PDF export capabilities.

- **Leave Management & Accruals**:
  - Configurable leave types (paid, unpaid, annual allowances, maternity, sick leave).
  - Split-period leave requests (`LeavePeriod`) and automatic balance validation upon approval.
  - Automated leave balance accrual command.

- **Dynamic Payroll & Deduction Engine**:
  - **Multi-Component Salary Structures**: Base pay, housing, transportation, meal, and custom allowances.
  - **Daily Salary Formula Engine**: Transparent daily rate calculations supporting multiple standard industry formulas (e.g., `(Monthly × 12) / (52 × 5.5)`, `Monthly / 26`, `Monthly / 24`) with an interactive Formula Guide.
  - **Configurable Deduction Rules** (`DeductionRule`): Create granular, condition-based deduction policies for absences, unpaid leave, late arrivals, and early departures using percentage-of-salary or fixed dollar amounts.
  - **Automated Overtime Integration**: Seamlessly pulls approved overtime earnings directly into gross payroll computations.
  - **Statutory Deductions & Taxes**: Built-in tax and social security (NSSF) calculations with configurable thresholds.
  - **Bonus & Incentive Management**: Award performance incentives with instant recalculation of net totals.
  - **High-Fidelity Payslips**: Interactive payslip breakdown and downloadable, print-ready PDF payslips.

- **Multi-Format Reporting & Executive Analytics**:
  - **Daily Report**: Real-time daily attendance snapshot with present, late, absent, and break metrics.
  - **Summary Report**: Executive dashboard tracking active headcount, department distributions, and total payroll disbursements.
  - **Detail Report**: Comprehensive multi-column employee compensation and attendance ledger.
  - **High-Fidelity Exports**: Full support for styled **Excel (.xlsx)** spreadsheets (via `openpyxl`) and formatted **PDF reports** (via `ReportLab`).

- **Enterprise Security & Auditing**:
  - Multi-tiered RBAC (`super_admin`, `hr_admin`, `manager`, `employee`).
  - View-level (`RoleRequiredMixin`) and form field-level (`FieldPermissionMixin`) access guards.
  - Session protection middleware (`SecureSessionMiddleware`) guarding against session hijacking.
  - Append-only activity log (`Activity`) tracking user and administrative operations.

---

## Tech Stack

| Layer | Technology / Package | Description |
|---|---|---|
| **Backend Framework** | [Django 5.1](https://www.djangoproject.com/) | Robust, high-level Python web framework |
| **Language** | Python 3.11+ | Modern Python runtime |
| **Database** | [MySQL 8.0](https://www.mysql.com/) / [SQLite 3](https://sqlite.org/) | Production MySQL via PyMySQL; SQLite fallback for local development |
| **Frontend UI** | Django Templates, Bootstrap 5 | Modern responsive interface with custom `hrms-*` design tokens |
| **UI Components** | Select2, Crispy Forms (`crispy-bootstrap5`), Material Design Icons | Enhanced search dropdowns, responsive modals, and clean typography |
| **Excel Export** | [openpyxl](https://openpyxl.readthedocs.io/) (>=3.1.5) | Generates styled multi-column Excel workbooks for payroll and reports |
| **PDF Generation** | [ReportLab](https://www.reportlab.com/) (>=4.0.0) | High-fidelity vector PDF generation for official payslips and reports |
| **Containerization** | Docker & Docker Compose | Multi-service orchestration for web and database services |
| **Testing & CI** | Factory Boy, Django Test Runner, GitHub Actions | Automated integration testing and CI pipeline |
| **Utilities** | Pillow (10.4.0), python-dateutil | Photo processing, calendar math, and schedule interval computation |

---

## System Architecture

```
                                  +-----------------------+
                                  |     Browser Client    |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  |  Django App Layer     |
                                  | (accounts, employees, |
                                  |  attendance, overtime,|
                                  |  leave, companies,    |
                                  |  payroll, reports)    |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
                     v                                                 v
        +-------------------------+                       +-------------------------+
        |  MySQL 8.0 (Production) |                       | SQLite (Dev Fallback)   |
        |  USE_MYSQL=true         |                       | USE_MYSQL=false         |
        +-------------------------+                       +-------------------------+
```

- **Domain-Driven Architecture**: Business logic is decoupled into standalone Django apps under `App/`:
  - `accounts`, `activities`, `attendance`, `companies`, `dashboard`, `employees`, `leave`, `overtime`, `payroll`, `reports`.
- **Modular Exporters**: Dedicated export engines in `App/reports/exporters.py` and `App/overtime/exporters.py` streamline CSV, Excel (`openpyxl`), and PDF (`ReportLab`) generation across all modules.
- **Unified Templates**: Organized under `templates/<app>/*.html` using a cohesive base theme (`templates/base.html`).
- **Centralized Rules**: Business logic parameters (tax rates, NSSF rates, standard hours, overtime multipliers) reside in `config/business_rules.json` and are accessed via `config/rules.py`.

---

## Role-Based Access Control (RBAC)

User roles are governed by `accounts.User.Role`:

| Role | Scope & Permissions |
|---|---|
| **Super Admin** (`super_admin`) | Unrestricted access to all modules, administrative settings, payroll generation, employee master records, company branches, and activity audit trails. |
| **HR Admin** (`hr_admin`) | Full operational management: employee records, branches, work schedules, lunch break policies, overtime approvals, leave allocations, bulk payroll generation, and executive reports. |
| **Manager** (`manager`) | Management of assigned department/branch teams: view employee directory, team schedules, attendance reports, review overtime requests, and view summary metrics. Restricted from altering sensitive salary structures. |
| **Employee** (`employee`) | Self-service portal: dashboard attendance clock-in/out, personal attendance log, overtime request submission/cancellation, leave request submission, and payslip history. |

Access enforcement is provided by:
- `accounts.mixins.RoleRequiredMixin`: Enforces `required_roles = [...]` on class-based views, raising `PermissionDenied` on violation.
- `accounts.mixins.FieldPermissionMixin`: Strips unauthorized fields from submitted forms based on role privileges (e.g. preventing non-admins from editing compensation).

---

## Module Breakdown

### 1. `accounts` — Identity & Security
- Custom `User` model inheriting from `AbstractUser` with assigned `role` and `phone`.
- Reusable access control mixins: `RoleRequiredMixin` and `FieldPermissionMixin`.
- `SecureSessionMiddleware` to detect suspicious IP or User-Agent deviations and mitigate session hijacking.

### 2. `companies` — Organizational Hierarchy
- Models: `Company`, `Department`, `Position`, and `Branch`.
- Multi-branch support: create and configure physical branch locations (`code`, `address`, `phone`) linked to parent companies.
- Shared `get_default_company()` utility ensuring consistent company associations.

### 3. `employees` — Employee Lifecycle Management
- `Employee` model featuring personal details, job metadata, branch assignment, salary baseline, and manager hierarchy.
- Custom `ActiveEmployeeManager` automatically filtering out deleted or anonymized records.
- Soft-delete (`soft_delete()`) and GDPR anonymization (`anonymize()`) methods.
- Views for employee directory search/filtering, profiles, and inline position/department/branch management.

### 4. `attendance` — Clocking, Lunch Breaks & Schedules
- `Attendance` model calculating elapsed net `working_hours` and evaluating statuses (`present`, `late`, `absent`, `checkout_early`, `overtime`).
- `LunchBreak` model: Define configurable break windows (Lunch, Tea, Custom) with `auto_deduct` rules and minimum work hour thresholds.
- Net working hour calculation (`calculate_net_working_hours`) automatically discounts active break intervals.
- Self-service `CheckInView` and `CheckOutView`.
- Dynamic weekly work schedule matrix (`EmployeeSchedule`, `WorkSchedule`) supporting split shifts and half-days.
- Export endpoints for schedules, attendance registers (Excel, PDF, CSV), and the `recalculate_working_hours` command.

### 5. `overtime` — Overtime Management & Approvals
- `OvertimeType` model: Configurable rate multipliers (e.g., 1.5x Normal, 2.0x Weekend, 3.0x Holiday).
- `OvertimeRequest` model: Tracks requested overtime hours, start/end times, auto-computed hourly wage rates, and total compensation amounts.
- Complete approval lifecycle (`pending`, `approved`, `rejected`, `cancelled`) with manager/HR review notes.
- Self-service portal (`/overtime/my/`) for employees to submit and cancel requests.
- Administrative dashboard (`/overtime/`) to review, filter, and approve records.
- Dedicated overtime report views with Excel and PDF export capabilities.

### 6. `leave` — Time-Off Requests & Allowances
- Configurable `LeaveType` definitions and per-employee `LeaveBalance` tracking per calendar year.
- `LeaveRequest` supporting multiple split date periods (`LeavePeriod`).
- Balance validation and automatic quota deduction upon request approval.

### 7. `payroll` — Compensation & Payslip Engine
- `SalaryStructure` managing basic salary and itemized allowances (transportation, housing, meal, other).
- `Payroll` model capturing attendance metrics (`attendance_days`, `absent_days`, `late_hours`, `overtime_hours`, `unpaid_leave_days`, `holiday_days`).
- **Daily Salary Formula Engine**: Transparent formulas for daily rate determination accessible via `/payroll/formula-guide/`.
- **Dynamic Deduction Rules Engine** (`DeductionRule`, `PayrollDeductionItem`): Create flexible rules based on attendance categories (absent, late, unpaid leave, early leave) with conditions and custom calculation types.
- Automatic aggregation of approved overtime compensation into gross earnings.
- `NewPayrollView` generating bulk payroll batches for all active employees for any target period.
- `BonusIncentiveView` allowing HR to award performance bonuses and immediately recalculate net totals.
- Self-service and administrative payslip views (`PayslipDetailView`, `MyPayslipListView`) with PDF export (`PayslipPdfExportView`).

### 8. `reports` — Executive Reporting & Analytics
- `DailyReportView`: Real-time attendance breakdown with branch and department filters.
- `SummaryReportView`: High-level summary of headcount, payroll disbursements, and leave counts.
- `DetailReportView`: Detailed employee register cross-referencing salaries, recent attendances, and payroll periods.
- High-fidelity **Excel (.xlsx)** and **PDF** export options across all report categories powered by `App/reports/exporters.py`.

### 9. `dashboard` — Role-Aware Landing Experience
- **Employee View**: Today's clock-in status, remaining leave balance, latest net salary card, overtime summary, and recent requests.
- **Admin/Manager View**: Total active employees, attendance counts (present/late), pending overtime and leave requests, recent hires, and system activity logs.

### 10. `activities` — System Audit Logging
- `Activity` model recording actor, targeted employee, module, action, and timestamp.
- Indexed by date and module for fast audit stream queries.

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Git**
- *(Optional)* **Docker & Docker Compose**
- *(Optional)* **MySQL 8.0** (if running with MySQL instead of SQLite)

---

### Quick Start with Docker Compose

The simplest way to spin up the complete stack (Django Web App + MySQL 8.0) is using Docker Compose:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/VR6c/Payroll_MGM.git
   cd Payroll_MGM
   ```

2. **Prepare the environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Build and launch containers:**
   ```bash
   docker compose up -d --build
   ```

4. **Verify container health:**
   ```bash
   docker compose ps
   ```

5. Access the application in your browser at:
   ```
   http://localhost:8000
   ```

To view logs or stop the containers:
```bash
docker compose logs -f web
docker compose down
```

---

### Manual / Local Development Setup

For local development with SQLite (no external MySQL server required):

1. **Clone the repository:**
   ```bash
   git clone https://github.com/VR6c/Payroll_MGM.git
   cd Payroll_MGM
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate    # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Initialize database schema:**
   ```bash
   USE_MYSQL=false python manage.py migrate
   ```

5. **Seed initial data & create a superuser:**
   ```bash
   # Create administrative user
   USE_MYSQL=false python manage.py createsuperuser

   # Seed default overtime categories and sample records
   USE_MYSQL=false python manage.py seed_overtime

   # Seed work schedules
   USE_MYSQL=false python manage.py seed_schedules
   ```

6. **Run the local development server:**
   ```bash
   USE_MYSQL=false python manage.py runserver
   ```

7. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser and log in.

---

## Database Seeding & Management Commands

The system includes built-in Django management commands to seed initial configurations and perform maintenance:

| Command | App | Purpose |
|---|---|---|
| `python manage.py seed_overtime` | `overtime` | Seeds standard overtime types (Normal 1.5x, Weekend 2.0x, Holiday 3.0x) and sample overtime records. |
| `python manage.py seed_schedules` | `attendance` | Seeds default company work shifts and weekly schedules. |
| `python manage.py recalculate_working_hours` | `attendance` | Recalculates working hours for existing attendance logs applying active lunch break deduction rules. |
| `python manage.py accrue_leave` | `leave` | Accrues monthly leave allocations for active personnel. |
| `python manage.py seed_user` | `accounts` | Populates initial administrative and test user accounts. |

---

## Environment Configuration

Configure application behavior via environment variables or by editing `.env`:

| Variable | Default Value | Description |
|---|---|---|
| `USE_MYSQL` | `true` | Set to `false` to use SQLite fallback |
| `DB_NAME` | `payroll_mgm_db` | MySQL database name |
| `DB_USER` | `payroll_user` | MySQL database user |
| `DB_PASSWORD` | `payroll_pass` | MySQL user password |
| `DB_ROOT_PASSWORD` | `rootpassword` | MySQL root administrative password |
| `DB_HOST` | `db` *(Docker)* / `localhost` | Host address of MySQL server |
| `DB_PORT` | `3306` | MySQL port |
| `SECRET_KEY` | `django-insecure-...` | Django cryptographic signing secret |
| `DEBUG` | `True` | Debug mode toggle (`True` for dev, `False` for prod) |

---

## Business Rules & Deduction Engine

Operational constants and formulas are centrally configured in [`config/business_rules.json`](file:///config/business_rules.json):

```json
{
  "payroll": {
    "tax_rate": "0.10",
    "nssf_rate": "0.05",
    "overtime_multiplier": "1.5",
    "currency_symbol": "$",
    "decimal_places": 2
  },
  "leave": {
    "accrual_method": "monthly",
    "carry_over_max_days": 5,
    "min_notice_days": 3
  },
  "attendance": {
    "standard_work_hours_per_day": "8.0",
    "grace_period_minutes": 5
  }
}
```

These parameters are cached and accessed centrally via `config.rules.get_rule(section, key, default)`. In addition, dynamic deduction rules configured through the UI (`/payroll/deductions/`) allow fine-grained customization of:
- **Deduction Categories**: Absent, Unpaid Leave, Late, Early Leave, Custom.
- **Conditions**: Days, hours, or occurrence counts with comparison operators (`always`, `<=`, `<`, `>=`, `>`, `between`, `=`).
- **Calculation Modes**: Percentage of daily/hourly/monthly salary or fixed dollar amounts per unit / flat fee.

---

## Testing & Quality Assurance

The test suite validates integration workflows across views, model constraints, lunch break deductions, overtime processing, prorated payroll calculations, and multi-format exports using `factory-boy` model factories:

```bash
# Run all tests with SQLite fallback
USE_MYSQL=false python manage.py test

# Run tests with verbose output
USE_MYSQL=false python manage.py test -v 2

# Run specific test suites
USE_MYSQL=false python manage.py test tests.test_payroll
USE_MYSQL=false python manage.py test tests.test_overtime
USE_MYSQL=false python manage.py test tests.test_lunch_break
USE_MYSQL=false python manage.py test tests.test_deductions
USE_MYSQL=false python manage.py test tests.test_reports
USE_MYSQL=false python manage.py test tests.test_attendance_bulk
```

### Test Suite Overview

- [`tests/test_payroll.py`](file:///tests/test_payroll.py): Validates daily salary formulas, mid-period hire prorations, tax/NSSF calculations, and bulk payroll batch generation.
- [`tests/test_overtime.py`](file:///tests/test_overtime.py): Tests overtime request submission, hourly wage calculation, approval workflows, and status constraints.
- [`tests/test_lunch_break.py`](file:///tests/test_lunch_break.py): Verifies lunch break overlap detection and net working hour deductions.
- [`tests/test_deductions.py`](file:///tests/test_deductions.py): Validates dynamic deduction rules matching conditions and itemized deductions on payroll.
- [`tests/test_reports.py`](file:///tests/test_reports.py): Tests aggregation queries and Excel/PDF export view responses.
- [`tests/test_attendance_bulk.py`](file:///tests/test_attendance_bulk.py): Verifies high-volume attendance processing and recalculations.
- [`tests/test_views.py`](file:///tests/test_views.py): Enforces RBAC permissions and HTTP endpoint security.

Automated test execution is enforced on every commit and pull request via the [GitHub Actions CI Pipeline](.github/workflows/ci.yml).

---

## Project Directory Structure

```
Payroll_MGM/
├── App/                            # Core Django applications
│   ├── accounts/                   # Authentication, User model, RBAC mixins, middleware
│   ├── activities/                 # System audit log & activity streams
│   ├── attendance/                 # Time tracking, lunch break deductions, schedule matrix
│   │   └── management/commands/    # recalculate_working_hours, seed_schedules
│   ├── companies/                  # Company, Department, Position, and Branch definitions
│   ├── dashboard/                  # Role-aware dashboard views
│   ├── employees/                  # Employee profiles, directory, position/dept/branch views
│   ├── leave/                      # Leave categories, request workflows, annual balances
│   │   └── management/commands/    # accrue_leave
│   ├── overtime/                   # Overtime types, request approval lifecycle, exports
│   │   ├── exporters.py            # Excel, PDF, and CSV exporters for overtime
│   │   └── management/commands/    # seed_overtime
│   ├── payroll/                    # Salary structures, dynamic deduction rules, payslips
│   └── reports/                    # Daily, summary, and detail reporting views
│       └── exporters.py            # High-fidelity Excel and PDF report generator engine
├── config/                         # Django project settings & configuration
│   ├── business_rules.json         # Configurable payroll, tax, leave & attendance rules
│   ├── rules.py                    # Business rule loader utility
│   ├── settings.py                 # Core Django settings
│   ├── urls.py                     # Root URL routing
│   └── wsgi.py                     # WSGI gateway entry
├── static/                         # Static assets (CSS, JS, vendor libraries, icons)
│   ├── assets/css/app.css          # Custom HRMS design system & variables
│   └── assets/vendors/             # Bootstrap, FontAwesome, MDI, Select2
├── templates/                      # Centralized HTML templates by app
│   ├── accounts/
│   ├── attendance/                 # my_attendance, report, schedules, lunch_breaks
│   ├── dashboard/                  # home
│   ├── employees/                  # list, detail, form, branches, departments, positions
│   ├── leave/                      # create, my_leaves, types, type_groups
│   ├── overtime/                   # list, my_overtime, report, types
│   ├── partials/                   # Shared navbars, sidebars, alerts, pagination
│   ├── payroll/                    # list, new_payroll, payslip, deduction_rules, formula_guide
│   └── reports/                    # daily, summary, detail
├── tests/                          # Test suite & factories
│   ├── factories.py                # Factory Boy model factories
│   ├── test_attendance_bulk.py     # Bulk attendance & duration tests
│   ├── test_deductions.py          # Deduction rules engine unit tests
│   ├── test_lunch_break.py         # Lunch break calculation tests
│   ├── test_overtime.py            # Overtime workflow & calculation tests
│   ├── test_payroll.py             # Payroll calculator & generator tests
│   ├── test_reports.py             # Report generation & export tests
│   └── test_views.py               # View & RBAC integration tests
├── .github/workflows/ci.yml        # GitHub Actions continuous integration workflow
├── docker-compose.yml              # Multi-container orchestration (Web + MySQL)
├── Dockerfile                      # Application container build definition
├── entrypoint.sh                   # Docker entrypoint script
├── requirements.txt                # Python package dependencies
├── .env.example                    # Sample environment variables
└── README.md                       # Project documentation
```

---

## Contributing & License

1. Fork the repository: [https://github.com/VR6c/Payroll_MGM](https://github.com/VR6c/Payroll_MGM)
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

This project is licensed under the **TVR License**.
