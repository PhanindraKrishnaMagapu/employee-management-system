# Architecture

Phase 1 establishes how the Employee Management System is split. It does not define database tables, REST resources, or login.

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
  app/auth          login and role checks (Phase 6)
  app/services      business rules
  app/models        SQL queries
        |
        v
SQLite file
  BACKEND/database/ems.sqlite
```

The browser never opens the database file. Flask is the only part of the system that reads and writes SQLite. Role checks will live in Flask even when a button is hidden in the page. Those checks are not implemented yet.

## Folder map

```text
employee-management-system/
├── UI/                 pages and static files
├── BACKEND/
│   ├── app/            Flask package
│   ├── database/       schema.sql, seed.sql, and the local SQLite file
│   └── tests/          automated tests (later phases)
└── DOCS/               architecture, database, API, setup, and user guides
```

| Path | Role in Phase 1 |
|---|---|
| `BACKEND/run.py` | Starts Flask on `127.0.0.1:5000` |
| `BACKEND/app/__init__.py` | Builds the Flask app and, later, registers blueprints |
| `BACKEND/app/config.py` | Reads `FLASK_SECRET_KEY`, `DATABASE_PATH`, and `FLASK_ENV` |
| `BACKEND/app/db.py` | Reserved for the SQLite connection. It does not open a database yet |
| `BACKEND/app/models/` | Future SQL helpers |
| `BACKEND/app/routes/` | Future REST endpoints |
| `BACKEND/app/services/` | Future business rules |
| `BACKEND/app/auth/` | Future login and role checks |
| `BACKEND/database/schema.sql` | Placeholder. Tables are added in Phase 2 |
| `BACKEND/database/seed.sql` | Placeholder. Fake rows are added in Phase 2 |
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
| 2 | Tables, foreign keys, and fake seed data |
| 3 | First REST read endpoints |
| 4 | Shared pages and styles that call the API |
| 5 | Employee create, read, update, and archive |
| 6 | Login and role-based access |
| 7–11 | Hierarchy, JML, projects, skills, salary, reports, and audit |
| 12 | Full test pass and local deployment with Waitress |

`requirements.txt` already lists Flask, pytest, and Waitress so later phases use the same install file. Waitress is not wired up in Phase 1. Local startup uses Flask's development server through `python run.py`.
