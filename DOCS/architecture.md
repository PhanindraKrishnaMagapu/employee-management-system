# Architecture

This document describes how the Employee Management System is split. The
database, health API, authentication API, and RBAC foundation are implemented;
employee and other business APIs are still to be added.

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
Browser (UI/)
  HTML pages, CSS, and JavaScript
        |  fetch() sends JSON to http://127.0.0.1:5000
        v
Flask REST API (BACKEND/)
  app/routes        URLs and HTTP methods
  app/auth          permission map, per-request user context, decorators
  app/services      business rules
  app/models        SQL queries
        |
        v
SQLite file
  BACKEND/database/ems.sqlite
```

The browser never opens the database file. Flask is the only part of the system
that reads and writes SQLite. Authorization is enforced in Flask even if a UI
element is hidden; UI filtering is never treated as a security control.

Every `/api/*` request is denied by default. Only `GET /api/health` and
`POST /api/auth/login` are public. `GET /api/auth/me` and `POST /api/auth/logout`
need a valid session; all other routes need an explicit permission decorator.
Roles are read from the database on each request and cached only for that
request (`flask.g`), never in the session. Endpoint denial returns `403`; a
record outside the caller's scope returns `404`.

## Folder map

```text
employee-management-system/
├── UI/                 pages and static files
├── BACKEND/
│   ├── app/            Flask package, including app/auth and app/services
│   ├── database/       schema.sql, seed.sql, migrations/, and the local SQLite file
│   └── tests/          automated tests, including RBAC tests and a test-only blueprint
└── DOCS/               architecture, database, API, setup, and user guides
```

| Path | Role in Phase 1 |
|---|---|
| `BACKEND/run.py` | Starts Flask on `127.0.0.1:5000` |
| `BACKEND/app/__init__.py` | Builds the app, registers blueprints, enforces default-deny on `/api/*` |
| `BACKEND/app/config.py` | Reads `FLASK_SECRET_KEY`, `DATABASE_PATH`, and `FLASK_ENV` |
| `BACKEND/app/db.py` | SQLite connection, `init`, `migrate`, and demo-password commands |
| `BACKEND/app/models/` | Future SQL helpers |
| `BACKEND/app/routes/` | Health and authentication endpoints |
| `BACKEND/app/services/` | Password authentication and employee-scope rules |
| `BACKEND/app/auth/` | Permission map, per-request user context, authorization decorators |
| `BACKEND/database/schema.sql` | Fresh-database schema, including `users.employee_id` |
| `BACKEND/database/seed.sql` | Fictional demo rows; no guessed user-employee links |
| `BACKEND/database/migrations/` | Additive, idempotent migrations for existing databases |
| `BACKEND/.env.example` | Placeholder settings safe to commit |
| `UI/js/api.js` | Future home for all `fetch` calls. Base URL is `http://127.0.0.1:5000` |
| `UI/js/auth.js` | Future login helper |

## Configuration and secrets

Local settings belong in `BACKEND/.env`, copied from `BACKEND/.env.example`.

- Commit `.env.example` only.
- Do not commit `.env`.
- Do not commit `ems.sqlite` or other SQLite files. The SQL scripts in `BACKEND/database/` stay in Git.
- Do not put real employee, salary, or exit data in the repository.

`config.py` reads environment variables. A relative `DATABASE_PATH` is resolved from the `BACKEND/` folder. The development secret key fallback `dev-only-change-me` is only for a local skeleton. Replace it before any real use.

## What later phases add

| Phase | Adds |
|---|---|
| 2 | Tables, foreign keys, and fake seed data (implemented) |
| 3 | First REST read endpoints |
| 4 | Shared pages and styles that call the API |
| 5 | Employee create, read, update, and archive |
| 6 | Login and RBAC foundation (implemented: permission map, decorators, default-deny, additive migration) |
| 7–11 | Hierarchy, JML, projects, skills, salary, reports, and audit |
| 12 | Full test pass and local deployment with Waitress |

`requirements.txt` already lists Flask, pytest, and Waitress so later phases use the same install file. Waitress is not wired up in Phase 1. Local startup uses Flask's development server through `python run.py`.
