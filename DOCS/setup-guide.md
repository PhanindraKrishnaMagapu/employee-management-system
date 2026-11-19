# Setup Guide – Employee Management System

**Current Status:** Database, authentication, RBAC, employee CRUD, hierarchy,
JML, projects, skills, employee skills, salary, and browser UI implemented

This guide explains how to set up the Employee Management System on Windows using PowerShell.

## Requirements

- Python 3.10 or newer
- Git
- PowerShell
- Visual Studio Code or another code editor

## 1. Clone the Repository

```powershell
git clone https://github.com/PhanindraKrishnaMagapu/employee-management-system.git
cd employee-management-system
```

## 2. Create a Virtual Environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again.

## 3. Install Backend Dependencies

```powershell
cd BACKEND
python -m pip install -r requirements.txt
```

Installed packages include:

- Flask – Backend framework
- pytest – Automated testing
- Waitress – Production WSGI server for a later deployment phase

## 4. Configure Environment Variables

Copy the example file:

```powershell
copy .env.example .env
```

Edit `.env` and replace the secret-key placeholder with a long random value.

Example configuration:

```dotenv
FLASK_SECRET_KEY=replace-with-a-long-random-string
DATABASE_PATH=database/ems.sqlite
FLASK_ENV=development
```

`FLASK_SECRET_KEY` must be set to a non-default value outside explicit local
development environments. Recognized development values for `FLASK_ENV` are
`development`, `dev`, `local`, `test`, and `testing`; with an unset or any other
value, startup fails if the key is missing or still `dev-only-change-me`.
Session cookies are `HttpOnly` and `SameSite=Lax`, and the `Secure` flag is
enabled outside those development environments. Use HTTPS when `Secure` is on.

Do not commit `.env` to Git.

The application currently reads environment variables from the shell. It does not automatically load `.env`.

PowerShell configuration example:

```powershell
$env:FLASK_SECRET_KEY = "replace-with-a-long-random-string"
$env:DATABASE_PATH = "database/ems.sqlite"
$env:FLASK_ENV = "development"
```

Relative database paths are resolved from the `BACKEND` directory.

## 5. Initialize the SQLite Database

From the `BACKEND` directory, run:

```powershell
python -m app.db init
```

This command:

- Creates the SQLite database if it does not exist.
- Creates all 15 application tables.
- Enables foreign-key enforcement through database connections.
- Inserts fictional development seed data.

The database is stored at:

```text
BACKEND/database/ems.sqlite
```

To create tables without inserting demo data:

```powershell
python -m app.db init --no-seed
```

### Apply additive migrations to an existing database

Databases created before the RBAC links, project ownership, and deferred JML
Mover changes need the
additive migrations. From the `BACKEND` directory, run:

```powershell
python -m app.db migrate
```

Migration `001_rbac_scope_links.sql` adds `users.employee_id` and the
`Payroll Admin` role. Migration `002_project_manager_jml_scope.sql` adds
`projects.manager_id`, `idx_projects_manager`, and
`jml_events.pending_changes`. The runner is idempotent: it records completed
migrations in `schema_migrations` and skips columns that already exist.
Fresh databases created with `python -m app.db init` already include these
objects and do not need this command. Use a copy or a temporary `DATABASE_PATH`
when testing migrations. A migration changes the database selected by
`DATABASE_PATH`; do not run it against the existing local project database
unless that migration has been explicitly approved. Do not reinitialize the
local development database.

### Demo account passwords (development only)

The seed script writes deliberately unusable placeholder hashes. To make the seven fictional demo accounts loggable, run:

```powershell
python -m app.db demo-passwords
```

The command asks for the password twice using a hidden interactive prompt. It never prints the password or a hash, and it never stores a password in the repository.

- Accounts that already have a valid hash are preserved. Use `--force` only when you deliberately want to replace them.
- Only the seven exact demo usernames are changed. No employee, role, or other data is touched.
- The command refuses to run when `FLASK_ENV=production`.
- After writing, it verifies authentication for every account it updated.

For automation only, read the password from a shell environment variable and confirm with `--yes`:

```powershell
$env:EMS_DEMO_PASSWORD = "<choose-a-fictional-demo-password>"
python -m app.db demo-passwords --password-env EMS_DEMO_PASSWORD --yes
```

Do not commit that value, and never use a real employee password.

## 6. Run Automated Database Tests

From the `BACKEND` directory:

```powershell
python -m pytest tests/ -v
```

The database-focused tests check:

1. All 15 tables are created.
2. Foreign keys are enabled.
3. Demo employees and users are inserted.
4. Duplicate employee codes are rejected.
5. Salary records require an existing employee.
6. Repeated initialization does not duplicate demo records.
7. Demo password provisioning, hash preservation, `--force`, production refusal, rollback, and authentication verification.

At the latest recorded verification, the complete backend suite passed:
**287 passed, 0 failed.** The
suite also covers employee CRUD, hierarchy, JML transitions and deferred Mover
changes, project ownership and assignments, skills, employee skills, salary
validation, RBAC, and login throttling.

Tests use temporary databases and do not modify the local development database. If pytest cannot access its default temporary folder, pass `--basetemp` with a writable path, for example `python -m pytest tests/ -v --basetemp C:\Temp\pytest-ems`.

## 7. Start the Flask Application

From the `BACKEND` directory:

```powershell
python run.py
```

The development server listens on:

```text
http://127.0.0.1:5000
```

Open <http://127.0.0.1:5000/> in a browser. Flask serves both the API and the UI from this same origin, so the session cookie works without CORS or a separate frontend server. Stop the server using `Ctrl + C`.

Implemented API areas are:

- `GET /api/health` – API and database availability.
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` – session authentication.
- `GET /api/employees`, `POST /api/employees`, `GET/PUT/DELETE /api/employees/<id>` – RBAC-protected employee CRUD.
- `GET /api/projects`, `POST /api/projects`, `GET /api/projects/assignable-employees`, `GET/PUT /api/projects/<id>`, `GET /api/projects/<id>/employees`, `POST /api/projects/<id>/assignments`, `DELETE /api/projects/<id>/assignments/<assignment_id>` – project and assignment management.
- `GET /api/jml/events`, `POST /api/jml/events`, `GET/PATCH /api/jml/events/<event_id>`, `PATCH /api/jml/events/<event_id>/checklist/<item_id>` – Joiner, Mover, and Leaver events.
- `GET /api/skills`, `POST /api/skills`, `PUT /api/skills/<skill_id>` – skill catalog.
- `GET/POST /api/employees/<employee_id>/skills`, `PUT/DELETE /api/employees/<employee_id>/skills/<assignment_id>` – employee skill assignments.
- `GET /api/salaries`, `POST /api/salaries`, `GET /api/salaries/employees`, `GET/PUT /api/salaries/<salary_id>` – salary records and history.

See `DOCS/api-documentation.md` for request and response details.

## 8. Frontend

The frontend files live in `UI/`, but they are served through Flask. Do not open `UI/index.html` with a `file://` URL; use the address from section 7.

| Browser URL | Served file |
|---|---|
| `/` | `UI/index.html` (login) |
| `/pages/dashboard.html` | `UI/pages/dashboard.html` |
| `/pages/employees.html` | `UI/pages/employees.html` |
| `/pages/employee-form.html` | `UI/pages/employee-form.html` |
| `/pages/hierarchy.html` | `UI/pages/hierarchy.html` |
| `/pages/jml.html`, `/pages/jml-form.html`, `/pages/jml-detail.html` | JML event list, create, and detail screens |
| `/pages/projects.html`, `/pages/project-form.html`, `/pages/project-detail.html` | Project list, create/edit, and detail screens |
| `/pages/skills.html`, `/pages/skill-form.html`, `/pages/employee-skills.html` | Skill catalog and employee skill screens |
| `/pages/salaries.html`, `/pages/salary-form.html`, `/pages/employee-salaries.html` | Salary list, create/edit, and employee history screens |
| `/css/styles.css` | `UI/css/styles.css` |
| `/js/...` | JavaScript helpers and page scripts under `UI/js/` |

The same-origin routes are registered in `BACKEND/app/routes/ui.py`. They only deliver static `.html`, `.css`, and `.js` files; they do not query the database or implement business logic.

Browser pages call relative `/api/...` URLs through `UI/js/api.js`. Its `API_BASE_URL` is empty and each request uses `credentials: "same-origin"`, so no absolute backend URL or CORS configuration is needed. The UI includes login/logout, the dashboard, employee list and add/edit/soft archive, the reporting hierarchy, JML events with checklists, projects and assignments, skills and employee skills, and salary records with history. See `DOCS/user-guide.md` for the user-facing steps and RBAC behavior.

## 9. Important Git and Security Notes

The following files and folders must not be committed:

- `.venv/`
- `BACKEND/.env`
- `BACKEND/database/ems.sqlite`

Only fictional development records should be used.

Never commit real employee personal information, salary data, passwords, or secret keys.

## 10. Project Documentation

Refer to:

- `MASTER_SOW.md` – Project requirements and scope.
- `DOCS/architecture.md` – System architecture.
- `DOCS/database-design.md` – Database tables and relationships.
- `DOCS/api-documentation.md` – API documentation.
- `DOCS/user-guide.md` – Application usage guide.
