# Architecture

This document describes how the Employee Management System is split. The
database, health API, authentication API, employee CRUD API, and RBAC foundation
are implemented; other business APIs are still to be added.

The product scope remains in [MASTER_SOW.md](../MASTER_SOW.md).

## Confirmed stack

| Layer | Technology | Where it lives |
|---|---|---|
| Frontend | HTML, CSS, and JavaScript | `UI/` |
| Backend | Python and Flask | `BACKEND/` |
| Database | SQLite, one local file | `BACKEND/database/ems.sqlite` (created in Phase 2, not committed) |
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

## Folder map

```text
employee-management-system/
├── UI/
│   ├── index.html              sign-in page
│   ├── pages/                  dashboard, employee list, and add/edit form
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
| `BACKEND/app/routes/ui.py` | Same-origin static serving for HTML, CSS, and JS |
| `BACKEND/app/services/` | Password authentication, employee validation/serialization, and scope rules |
| `BACKEND/app/auth/` | Permission map, per-request user context, authorization decorators |
| `BACKEND/database/schema.sql` | Fresh-database schema, including `users.employee_id` |
| `BACKEND/database/seed.sql` | Fictional demo rows; no guessed user-employee links |
| `BACKEND/database/migrations/` | Additive, idempotent migrations for existing databases |
| `BACKEND/.env.example` | Placeholder settings safe to commit |
| `UI/index.html` | Sign-in page served at `/` |
| `UI/pages/*.html` | Dashboard, employee list, and shared add/edit form |
| `UI/css/styles.css` | Shared responsive layout and messages |
| `UI/js/api.js` | `fetch` helper using relative `/api/...` URLs and same-origin credentials |
| `UI/js/auth.js` | Login/logout, current-user checks, and role-based UI gating |
| `UI/js/ui.js` | Shell, navigation, message, and redirect helpers |
| `UI/js/pages/*.js` | Page behavior for login, dashboard, list, and employee form |

## Configuration and secrets

Local settings belong in `BACKEND/.env`, copied from `BACKEND/.env.example`.

- Commit `.env.example` only.
- Do not commit `.env`.
- Do not commit `ems.sqlite` or other SQLite files. The SQL scripts in `BACKEND/database/` stay in Git.
- Do not put real employee, salary, or exit data in the repository.

`config.py` reads environment variables. A relative `DATABASE_PATH` is resolved from the `BACKEND/` folder. The development secret key fallback `dev-only-change-me` is only for a local skeleton. Replace it before any real use.

## Implemented and deferred work

| Area | Status |
|---|---|
| Database schema, foreign keys, and fictional seed data | Implemented |
| Health, login, logout, and current-user APIs | Implemented |
| Permission map, decorators, default-deny, and employee scope | Implemented |
| Employee create, read, update, and soft archive APIs | Implemented |
| Same-origin UI serving and shared responsive shell | Implemented |
| Login, dashboard, employee list/search, add, edit, and archive screens | Implemented |
| Organization hierarchy, departments/designations, JML, projects, skills | Deferred |
| Salary, reports, audit, users, and roles screens/APIs | Deferred |
| Waitress deployment | Deferred |

`requirements.txt` lists Flask, pytest, and Waitress. Local startup currently uses Flask's development server through `python run.py`; Waitress is not wired into `run.py`.
