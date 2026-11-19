# Architecture

This document describes how the Employee Management System is split. The
database, health API, authentication API, employee CRUD API, RBAC foundation,
hierarchy, JML, project management, skills, employee skills, and salary modules
are implemented. Salary creates and updates also write safe audit rows. Reports,
an audit read API/screen, and user/role administration are still to be added.

The product scope remains in [MASTER_SOW.md](../MASTER_SOW.md).

## Confirmed stack

| Layer | Technology | Where it lives |
|---|---|---|
| Frontend | HTML, CSS, and JavaScript | `UI/` |
| Backend | Python and Flask | `BACKEND/` |
| Database | SQLite, one local file | `BACKEND/database/ems.sqlite` (created locally, not committed) |
| API | REST, JSON over HTTP | Flask blueprints under `BACKEND/app/routes/` |
| Version control | Git and GitHub | repository root |

Node.js and Express are not part of this project.

## Request path

```text
Browser
  GET /, /pages/..., /css/..., /js/...
  served from UI/ by Flask's UI blueprint
        |
        |  fetch("/api/...") with same-origin session cookie
        v
Flask (BACKEND/)
  app/routes        UI file serving and REST API URLs/methods
  app/auth          permission map, per-request user context, decorators
  app/services      business rules and employee scope checks
  app/models        reserved for SQL helpers
        |
        v
SQLite file
  BACKEND/database/ems.sqlite
```

Flask serves the browser UI and the API from one origin (`127.0.0.1:5000` in
local development). `UI/js/api.js` uses an empty `API_BASE_URL`, relative
`/api/...` paths, and `credentials: "same-origin"`. No CORS configuration,
development proxy, or absolute frontend-to-backend URL is required.

The browser never opens the database file. Flask is the only part of the system
that reads and writes SQLite. Authorization is enforced in Flask even if a UI
element is hidden; UI filtering is never treated as a security control.

Every `/api/*` request is denied by default. Only `GET /api/health` and
`POST /api/auth/login` are public. `GET /api/auth/me` and `POST /api/auth/logout`
need a valid session; all other routes need an explicit authorization decorator.
Roles are read from the database on each request and cached only for that
request (`flask.g`), never in the session. Endpoint denial returns `403`; a
record outside the caller's scope returns `404`.

Salary data uses a dedicated `/api/salaries` namespace instead of the general
employee namespace. Payroll Admin resolves salary scope through a salary-specific
helper, so it receives organization-wide salary access without
`employees:read:all`. The Project Manager employee carve-out therefore does not
block combined roles such as `Project Manager` + `Payroll Admin`. Salary
responses use explicit salary and minimal employee-summary allowlists and are
marked `Cache-Control: no-store`.

Project access is additionally scoped by `projects.manager_id`: HR Admin keeps
organization-wide project management, while a Project Manager may read and
manage only projects whose `manager_id` equals their linked `users.employee_id`.
CEO and Department Manager retain read-only project visibility. Out-of-scope
projects return `404`. The project employee picker is the only reason a
Project Manager receives the employee read grant; the general employee and
hierarchy APIs remain closed to that role.

JML events keep an explicit status table (`Pending` to `In Progress`,
`Completed`, or `Cancelled`; `In Progress` to `Completed` or `Cancelled`).
Completed and Cancelled are terminal. A status change is validated under the
database write lock. Completion requires every checklist item; a Leaver also
requires "Access removal confirmed" and deactivates only user accounts linked
to that employee. Mover changes are stored in `jml_events.pending_changes` and
are applied, with history, only when the event reaches `Completed`; cancelling
a Mover leaves the employee unchanged. Manager updates are checked for direct
and indirect reporting cycles.

Login is throttled to five failed attempts per 300 seconds per client IP and
username. The throttle is held in process memory for this single-app setup.
Unknown and inactive usernames are verified against a dummy password hash so
response timing does not reveal account existence. Successful login clears the
session before storing only `user_id`; the session cookie is `HttpOnly`,
`SameSite=Lax`, and permanent for the configured eight-hour lifetime.

## Folder map

```text
employee-management-system/
├── UI/
│   ├── index.html              sign-in page
│   ├── pages/                  dashboard and employee, hierarchy, JML, project, skill, and salary screens
│   ├── css/styles.css          shared responsive styles
│   └── js/                     API, auth, shell helpers, and per-page scripts
├── BACKEND/
│   ├── app/                    Flask package, including app/auth and app/services
│   ├── database/               schema.sql, seed.sql, migrations/, and the local SQLite file
│   └── tests/                  automated tests, including RBAC and employee API tests
└── DOCS/                       architecture, database, API, setup, and user guides
```

| Path | Current role |
|---|---|
| `BACKEND/run.py` | Starts Flask on `127.0.0.1:5000` |
| `BACKEND/app/__init__.py` | Builds the app, registers API/UI blueprints, enforces default-deny on `/api/*` |
| `BACKEND/app/config.py` | Reads `FLASK_SECRET_KEY`, `DATABASE_PATH`, and `FLASK_ENV` |
| `BACKEND/app/db.py` | SQLite connection, `init`, `migrate`, and demo-password commands |
| `BACKEND/app/models/` | Reserved for SQL helpers; current queries live in services |
| `BACKEND/app/routes/health.py` | Health endpoint |
| `BACKEND/app/routes/auth.py` | Login, logout, and current-user endpoints |
| `BACKEND/app/routes/employees.py` | Employee list, read, create, update, and archive endpoints |
| `BACKEND/app/routes/jml.py` | JML event endpoints |
| `BACKEND/app/routes/projects.py` | Project and assignment endpoints |
| `BACKEND/app/routes/skills.py` | Skill catalog endpoints |
| `BACKEND/app/routes/employee_skills.py` | Employee skill assignment endpoints |
| `BACKEND/app/routes/salaries.py` | Salary record endpoints with salary-specific scope |
| `BACKEND/app/routes/ui.py` | Same-origin static serving for HTML, CSS, and JS |
| `BACKEND/app/services/` | Authentication, validation/serialization, scope, JML, project, skill, and salary rules |
| `BACKEND/app/auth/` | Permission map, per-request user context, authorization decorators |
| `BACKEND/database/schema.sql` | Fresh-database schema, including `users.employee_id` |
| `BACKEND/database/seed.sql` | Fictional demo rows; no guessed user-employee links |
| `BACKEND/database/migrations/` | Additive, idempotent migrations for existing databases |
| `BACKEND/.env.example` | Placeholder settings safe to commit |
| `UI/index.html` | Sign-in page served at `/` |
| `UI/pages/*.html` | Dashboard, employee, hierarchy, JML, project, skill, and salary screens |
| `UI/css/styles.css` | Shared responsive layout and messages |
| `UI/js/api.js` | `fetch` helper using relative `/api/...` URLs and same-origin credentials |
| `UI/js/auth.js` | Login/logout, current-user checks, and role-based UI gating |
| `UI/js/ui.js` | Shell, navigation, message, and redirect helpers |
| `UI/js/pages/*.js` | Page behavior for login, dashboard, employee, hierarchy, JML, project, skill, and salary screens |

## Configuration and secrets

Local settings belong in `BACKEND/.env`, copied from `BACKEND/.env.example`.

- Commit `.env.example` only.
- Do not commit `.env`.
- Do not commit `ems.sqlite` or other SQLite files. The SQL scripts in `BACKEND/database/` stay in Git.
- Do not put real employee, salary, or exit data in the repository.

`config.py` reads `FLASK_SECRET_KEY`, `DATABASE_PATH`, and `FLASK_ENV`. A
relative `DATABASE_PATH` is resolved from the `BACKEND/` folder. The fallback
secret key `dev-only-change-me` and the defaults are permitted only when
`FLASK_ENV` is one of `development`, `dev`, `local`, `test`, or `testing`.
Outside those explicit development environments, startup fails unless
`FLASK_SECRET_KEY` is set to a non-default value. Session cookies are always
`HttpOnly` and `SameSite=Lax`, and `Secure` is enabled outside development.
Use a strong, unique secret and HTTPS outside local development; the app does
not load `.env` automatically, so configure environment variables in the shell
or deployment environment.

## Implemented and deferred work

| Area | Status |
|---|---|
| Database schema, foreign keys, and fictional seed data | Implemented |
| Health, login, logout, and current-user APIs | Implemented |
| Permission map, decorators, default-deny, and employee scope | Implemented |
| Employee create, read, update, and soft archive APIs | Implemented |
| Same-origin UI serving and shared responsive shell | Implemented |
| Login, dashboard, employee list/search, add, edit, and archive screens | Implemented |
| Organization hierarchy, departments/designations, JML, projects, skills, and employee skills | Implemented |
| JML status transitions, checklist requirements, Mover pending changes, and Leaver deactivation | Implemented |
| Manager-cycle checks and Project Manager ownership scope | Implemented |
| Salary record list, create, update, history, and picker APIs and screens | Implemented |
| Safe audit logging for salary create and update | Implemented |
| Login throttling and hardened session cookies | Implemented |
| Migration 001 (user links) and migration 002 (project ownership and deferred JML Mover changes) | Implemented |
| Reports, audit read API/screens, users, and roles | Deferred |
| Waitress deployment | Deferred |

`requirements.txt` lists Flask, pytest, and Waitress. Local startup currently uses Flask's development server through `python run.py`; Waitress is not wired into `run.py`.
