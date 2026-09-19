# Payroll Management System (Payroll MGM)

[![Django CI/CD Pipeline](https://github.com/VR6c/Payroll_MGM/actions/workflows/ci.yml/badge.svg)](https://github.com/VR6c/Payroll_MGM/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![Django Version](https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white)
![Database](https://img.shields.io/badge/Database-MySQL%20%7C%20SQLite-4479A1?logo=mysql&logoColor=white)
![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

A production-ready, Django-powered **Human Resource & Payroll Management System (HRMS)** designed to streamline employee recordkeeping, attendance and schedule tracking, leave allocations, automated bulk payroll processing, payslip delivery, and executive reporting with robust role-based access control (RBAC).

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
- [Environment Configuration](#environment-configuration)
- [Business Rules & Settings](#business-rules--settings)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Project Directory Structure](#project-directory-structure)
- [Contributing & License](#contributing--license)

---

## Key Features

- **🏢 Organization & Structure**: Hierarchical structure managing companies, departments, and position definitions.
- **👥 Employee Directory & Lifecycle**: Complete profiles (contact info, emergency data, join dates, basic salary), status workflows (Active, Inactive, Resigned, Terminated), soft-delete mechanism, and GDPR-compliant record anonymization (`[REDACTED]`).
- **⏱️ Attendance Tracking**: Self-service check-in/out with automated daily duration calculation, late/early leave detection, overtime capture, and company-wide attendance monitoring.
- **📅 Flexible Work Schedules**: Interactive weekly shift assignment grid with support for standard/flexible shifts, split hours, half-day rules, and schedule CSV export.
- **🌴 Leave Management**: Configurable leave types (paid/unpaid, annual allowance), annual quota balance tracking, and multi-period leave request processing.
- **💰 Payroll & Compensation**:
  - Multi-component salary structures (Basic + Housing, Transportation, Meal, and Other Allowances).
  - Prorated salary calculation for mid-period hires.
  - One-click bulk payroll generation across active personnel.
  - Tax and social security (NSSF) deductions with configurable rates.
  - One-off bonus and incentive additions with dynamic totals recalculation.
  - Printable employee payslips and self-service payslip archives.
- **📊 Management Reporting**:
  - **Daily Report**: Today's attendance snapshot with present/late/absent tallies.
  - **Summary Report**: Executive metrics including total headcount, active employees, net payroll expenditure, and recent payroll runs.
  - **Detail Report**: Comprehensive ledger covering employee codes, departments, positions, salaries, and recent logs.
- **🛡️ Enterprise Security**:
  - Multi-tier role permissions (`super_admin`, `hr_admin`, `manager`, `employee`).
  - Form-level and field-level permissions (e.g., preventing managers from altering compensation data).
  - Session hardening middleware (`SecureSessionMiddleware`) checking client signatures against session hijacking.
- **📈 Audit Trail & Activity Feed**: Append-only activity logging for auditing key operations across modules.

---

## Tech Stack

| Layer | Technology / Package | Description |
|---|---|---|
| **Backend Framework** | [Django 5.1](https://www.djangoproject.com/) | High-level Python web framework |
| **Language** | Python 3.11+ | Modern Python runtime |
| **Database** | [MySQL 8.0](https://www.mysql.com/) / [SQLite 3](https://sqlite.org/) | MySQL for production/containers via PyMySQL; SQLite fallback for local development |
| **Frontend UI** | Django Templates, Bootstrap 5 | Responsive interface with custom `hrms-*` design tokens (`static/assets/css/app.css`) |
| **UI Components** | Select2, Crispy Forms (`crispy-bootstrap5`), Material Design Icons | Enhanced dropdowns, modal-based forms, and clean typography |
| **Containerization** | Docker & Docker Compose | Multi-container setup orchestrating Web & MySQL services |
| **Testing & CI** | Factory Boy, Django Test Runner, GitHub Actions | Automated continuous integration test suite |
| **Utilities** | Pillow (image processing), python-dateutil | Photo uploads, date math & scheduling calculations |

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
                                  |  attendance, leave,   |
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

- **Modular Design**: Domain logic is separated into standalone Django apps inside `App/` (`accounts`, `activities`, `attendance`, `companies`, `dashboard`, `employees`, `leave`, `payroll`, `reports`).
- **Centralized Templates**: Centralized under `templates/<app>/*.html` using a unified base layout (`templates/base.html`).
- **Configurable Rules**: Business logic defaults (tax rate, NSSF rate, standard hours, overtime multiplier) reside in `config/business_rules.json` and are accessed via `config/rules.py`.

---

## Role-Based Access Control (RBAC)

User roles are governed by `accounts.User.Role`:

| Role | Scope & Permissions |
|---|---|
| **Super Admin** (`super_admin`) | Unrestricted access to all modules, administrative settings, payroll generation, employee master records, and activity logs. |
| **HR Admin** (`hr_admin`) | Full operational access to employee records, work schedules, leave configuration, payroll generation, bonuses, and reports. |
| **Manager** (`manager`) | Access to employee directory, team schedules, attendance reports, and summary metrics. Restricted from altering sensitive salary structures. |
| **Employee** (`employee`) | Self-service portal: dashboard attendance clock-in/out, personal attendance log, leave request submission, and payslip history. |

Access enforcement is provided by:
- `accounts.mixins.RoleRequiredMixin`: Enforces `required_roles = [...]` on class-based views, raising `PermissionDenied` on violation.
- `accounts.mixins.FieldPermissionMixin`: Strips unauthorized fields from submitted forms based on role privileges.

---

## Module Breakdown

### 1. `accounts` — Identity & Security
- Custom `User` model inheriting from `AbstractUser` with assigned `role` and `phone`.
- Reusable access control mixins: `RoleRequiredMixin` and `FieldPermissionMixin`.
- `SecureSessionMiddleware` to detect suspicious IP/User-Agent deviations.

### 2. `companies` — Organizational Hierarchy
- Models: `Company`, `Department`, `Position`.
- Shared `get_default_company()` utility ensuring company association across models.

### 3. `employees` — Employee Lifecycle Management
- `Employee` model featuring personal details, job metadata, salary baseline, and manager hierarchy.
- Custom `ActiveEmployeeManager` automatically filtering out deleted or anonymized records.
- Soft-delete (`soft_delete()`) and GDPR anonymization (`anonymize()`) methods.
- Views for employee directory search/filtering, profiles, and inline position/department management.

### 4. `attendance` — Clocking & Shift Schedules
- `Attendance` model calculating elapsed `working_hours` and evaluating statuses (`present`, `late`, `absent`, `early_leave`, `overtime`).
- Self-service `CheckInView` and `CheckOutView`.
- Dynamic weekly work schedule matrix (`EmployeeSchedule`, `WorkSchedule`) supporting split shifts and half-days.
- Schedule data export endpoint (`ExportScheduleView`).

### 5. `leave` — Time-Off Requests & Allowances
- Configurable `LeaveType` definitions and per-employee `LeaveBalance` tracking per calendar year.
- `LeaveRequest` supporting multiple split date periods (`LeavePeriod`).
- Balance validation and deduction on request approval.

### 6. `payroll` — Compensation & Payslip Engine
- `SalaryStructure` managing basic salary and itemized allowances (transportation, housing, meal, other).
- `PayrollCalculator` service handling mid-month hire prorations, tax (default 10%), and social security (NSSF default 5%).
- `NewPayrollView` generating bulk payroll batches for all active employees for any target period.
- `BonusIncentiveView` allowing HR to award performance bonuses and immediately recalculate net totals.
- Self-service and administrative payslip views (`PayslipDetailView`, `MyPayslipListView`).

### 7. `reports` — Executive Reporting
- `DailyReportView`: Real-time daily attendance breakdown.
- `SummaryReportView`: High-level summary of headcount, payroll disbursements, and leave counts.
- `DetailReportView`: Detailed employee register cross-referencing salaries, recent attendances, and payroll periods.

### 8. `dashboard` — Role-Aware Landing Experience
- **Employee View**: Today's clock-in status, remaining leave balance, latest net salary card, and recent leave requests.
- **Admin/Manager View**: Total active employees, attendance counts (present/late), pending leave requests, recent hires, and system activity logs.

### 9. `activities` — System Audit Logging
- `Activity` model recording actor, targeted employee, module, action, and timestamp.
- Indexed by date and module for fast audit stream queries.

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Git**
- *(Optional)* **Docker & Docker Compose**
- *(Optional)* **MySQL 8.0** (if running without SQLite)

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

For local development with SQLite (no MySQL service required):

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

5. **Create a superuser account:**
   ```bash
   USE_MYSQL=false python manage.py createsuperuser
   ```

6. **Run the local development server:**
   ```bash
   USE_MYSQL=false python manage.py runserver
   ```

7. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser and log in.

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

## Business Rules & Settings

Operational constants and formulas are managed in [`config/business_rules.json`](file:///config/business_rules.json):

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

These parameters are cached and accessed centrally via `config.rules.get_rule(section, key, default)`.

---

## Testing & Quality Assurance

The test suite validates integration workflows across views, model constraints, prorated payroll calculations, and bulk generation routines using `factory-boy` test factories:

```bash
# Run tests with SQLite fallback
USE_MYSQL=false python manage.py test

# Run tests with verbose output
USE_MYSQL=false python manage.py test -v 2
```

Automated test execution is enforced on every commit and pull request via the [GitHub Actions CI Pipeline](.github/workflows/ci.yml).

---

## Project Directory Structure

```
Payroll_MGM/
├── App/                            # Core Django applications
│   ├── accounts/                   # Authentication, User model, RBAC mixins, middleware
│   ├── activities/                 # System audit log & activity streams
│   ├── attendance/                 # Time tracking, shift definitions, schedule matrix
│   ├── companies/                  # Company, Department, and Position definitions
│   ├── dashboard/                  # Role-aware dashboard views
│   ├── employees/                  # Employee profiles, directory, position/dept views
│   ├── leave/                      # Leave categories, request workflows, annual balances
│   ├── payroll/                    # Salary structures, allowances, payroll engine, payslips
│   └── reports/                    # Daily, summary, and detail reporting views
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
│   ├── attendance/
│   ├── dashboard/
│   ├── employees/
│   ├── leave/
│   ├── partials/                   # Shared navbars, sidebars, alerts, pagination
│   ├── payroll/
│   └── reports/
├── tests/                          # Test suite & factories
│   ├── factories.py                # Factory Boy model factories
│   ├── test_payroll.py             # Payroll calculator & generator unit tests
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

This project is licensed under the **MIT License**.
