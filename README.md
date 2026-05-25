GESM LEAVE MANAGEMENT SYSTEM
=============================
Django 5.2 - Python 3.10 - Bootstrap 5
Developed during internship at GESM, Philippines - 2026


TABLE OF CONTENTS
1. Project Overview
2. Tech Stack
3. Installation (Local)
4. Configuration (.env)
5. First Launch
6. User Roles
7. Features by Role
8. Leave Balance Logic
9. Deployment (Production)
10. Running Tests
11. Known Issues


1. PROJECT OVERVIEW


GESM Leave Management is a web application built for a school
to manage staff leave requests. It replaces a manual paper-based
system with a full digital workflow including:

- Leave submission and multi-step approval chain
- Automatic paid/unpaid leave calculation
- Calendar view of all absences
- Email notifications at each step
- Excel export for HR and accounting
- Annual reset with carry-over logic


2. TECH STACK


Backend     : Django 5.2, Python 3.10
Database    : SQLite (dev) -> PostgreSQL (production : need to be done after first pull)
Frontend    : Bootstrap 5, Font Awesome 6
Email       : Django email backend (SMTP in production)
Excel       : openpyxl
PDF         : reportlab (for leave certificates)
Auth        : Django built-in + custom User model


3. INSTALLATION (LOCAL)


Prerequisites: Python 3.10+, pip, git

-- Clone the repo
git clone https://github.com/your-repo/gesm-leave.git
cd gesm-leave

-- Create virtual environment
python -m venv env

-- Activate (Windows)
env\Scripts\activate

-- Activate (Mac/Linux)
source env/bin/activate

-- Install dependencies
pip install -r requirements.txt

-- Apply migrations
python manage.py makemigrations
python manage.py migrate

-- Create first HR account (see Section 5)
python manage.py shell

-- Run development server
python manage.py runserver


4. CONFIGURATION (.env) : to fill up after pull on git


Create a .env file at the root of the project (same level as manage.py).
NEVER commit this file to git. (already in .gitignore)

--- LOCAL DEVELOPMENT (SQLite) ---

SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

Leave empty for SQLite (default) :
DB_ENGINE=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=GESM Leave System <noreply@gesm.org>
TIME_ZONE=Asia/Manila

--- PRODUCTION (PostgreSQL) ---

SECRET_KEY=your-long-random-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DB_ENGINE=django.db.backends.postgresql
DB_NAME=gesm_leave
DB_USER=gesm_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gesm.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@gesm.org
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=GESM Leave System <noreply@gesm.org>
TIME_ZONE=Asia/Manila



5. FIRST LAUNCH


After running migrations, create the first HR account manually.
This account can then create all other admin accounts (HOA, HOD etc.)

python manage.py shell

>>> from accounts.models import User
>>> User.objects.create_user(
...     username='hr_admin',
...     email='put correct email',
...     password='put password',
...     role='hr',
...     is_active=True,
...     is_approved=True,
...     is_email_verified=True,
...     first_name='HR',
...     last_name='Admin',
... )
>>> print("HR account created!")

Then log in at http://127.0.0.1:8000 and change the password
immediately via the key icon in the navbar.



6. USER ROLES


ROLE                HOW CREATED                 DASHBOARD
-----------         ------------------          -----------------
teacher             Public registration         Employee dashboard
admin               Public registration         Employee dashboard
head_of_department  Public registration         HOD dashboard
head_of_school      Public registration         HOS dashboard
head_of_admin       Created by HR only          HOA dashboard
hr                  Created by HR only          HR dashboard
scheduling_team     Public registration or HR   Scheduling dashboard
calendar_access     Created by HR only          Scheduling dashboard

Note: All accounts (except HR-created ones) are inactive until
HR manually approves them from the HR dashboard.

7. FEATURES BY ROLE


--- TEACHER / HEAD OF DEPARTMENT ---
    - Submit leave requests (vacation, sick, emergency, etc.)
    - View own leave history and status
    - Back to Work notification (sends email to scheduling team + HOS + direct HOD)
    - Request Pay Slip (sends email to accounting@gesm.org)
    - Request Certificate of Employment (sends email to HR)
    - View their leave balance (absences counted up)

--- ADMIN ---
    - Same as teacher but approval goes through HOA
    - 6 leave categories with individual balances
    - Request Pay Slip and Certificate of Employment

--- HEAD OF DEPARTMENT (HOD) ---
    - All teacher features
    - View and approve/reject teachers' leave requests
    - View teachers in their department

--- HEAD OF SCHOOL (HOS) ---
    - Final approval for teacher and HOD leave requests
    - Can mark leave as Unpaid
    - View calendar of all teacher/HOD absences
    - View any teacher/HOD profile (overview)

--- HEAD OF ADMIN (HOA) ---
    - Final approval for admin and HR leave requests
    - Can mark admin leave as Unpaid
    - View any admin profile

--- HR ---
    - Full access to all leave requests
    - Approve/reject any pending request
    - Adjust leave balances (teachers and admins)
    - Edit users (reassign role, department, superior)
    - Create HOA, HR, Calendar Access accounts
    - File leave on behalf of employees (auto-approved)
    - Export all leaves as Excel file
    - Export calendar absences as Excel file
    - Reset all balances for new school year
    - View full calendar with unpaid leaves in red
    - Archives: view and download PDF attachments

--- SCHEDULING TEAM ---
    - View calendar of teacher/HOD absences (no unpaid/red)

--- CALENDAR ACCESS (Accounting) ---
    - Same calendar view as HR (with unpaid in red)
    - Download Excel of all absences with unpaid days detail



8. LEAVE BALANCE LOGIC


TEACHERS AND HOD:
    - Single balance: vacation_leave (30 days default)
    - ALL leave types (sick, vacation, emergency...) deduct from this one balance
    - If leave <= remaining days -> fully paid (blue on calendar)
    - If leave > remaining days -> AUTO-SPLIT into 2 entries:
        * Entry 1: paid portion (blue)
        * Entry 2: unpaid portion (red)
    - If HOS manually marks leave as Unpaid : remaining days ARE still deducted
      (it counts against the quota - unpaid is just a visual/payroll flag)
    - HR can add extra remaining days at any time
    - Annual reset: back to 30 days, no carry-over

ADMINS:
    - 6 separate balances by leave type:
        * Vacation Leave: 15 days
        * Sick Leave: 15 days
        * Emergency Leave: 3 days
        * Bereavement Leave: 5 days
        * Maternity/Paternity Leave: no limit
          (1 at account creation, then at annual reset, HR can modify in balance)
        * Others: no limit
          (1 at account creation, then at annual reset, HR can modify in balance)
    - Same split logic as teachers per category
    - Annual reset: unused vacation days carry over, others reset

CALENDAR COLORS:
    - Blue  = paid leave (approved)
    - Red   = unpaid leave (auto-split or manual)
    - Grey  = pending sick leave
    - Scheduling team: always blue (no red shown)


9. DEPLOYMENT (PRODUCTION)


1. Install PostgreSQL and create database:

   CREATE DATABASE gesm_leave;
   CREATE USER gesm_user WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE gesm_leave TO gesm_user;

2. Install psycopg2:
   pip install psycopg2-binary

3. Create .env with PostgreSQL settings (see Section 4)

4. Run migrations:
   python manage.py makemigrations
   python manage.py migrate

5. Collect static files:
   python manage.py collectstatic

6. Create first HR account (see Section 5)

7. Configure web server (nginx + gunicorn recommended):
   pip install gunicorn
   gunicorn hrapp.wsgi:application --bind 0.0.0.0:8000

8. Set ALLOWED_HOSTS to your domain in .env

Important: Set DEBUG=False in production!



10. RUNNING TESTS (not necessary : already ran before final push)


Run all tests:
python manage.py test accounts.tests leaves.tests dashboard.tests

Run a specific file:
python manage.py test accounts.tests

Run a specific class:
python manage.py test accounts.tests.LoginTests

Run a specific test:
python manage.py test accounts.tests.LoginTests.test_active_user_can_login

Total: ~212 tests covering registration, login security, leave submission,
approval chain, email notifications, balance logic, HR features,
calendar colors and URL security. Already ran before final push.


11. KNOWN ISSUES / NOTES


- The calendar language depends on the browser locale.
  Set USE_L10N=False in settings.py to force English.

- When deleting an approved leave, the balance is recalculated
  from scratch to avoid inconsistencies.

- The auto-split uses int(paid_days) for the split date calculation.
  For fractional remaining days (e.g. 14.5), use round() instead.

- In production, make sure noreply@gesm.org is authorized to send
  emails from your SMTP server.

- accounting@gesm.org must exist as a real email address for
  Pay Slip requests to be received.


================================================================
Built during internship at German European School Manila - APRIL/MAY 2026
================================================================
