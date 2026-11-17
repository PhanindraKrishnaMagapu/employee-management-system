# Employee Management System

Web application for managing employees, organization hierarchy, joiner-mover-leaver events, projects, skills, and restricted salary records. The backend is Python.

The full scope is in [MASTER_SOW.md](MASTER_SOW.md). How the pieces connect is in [DOCS/architecture.md](DOCS/architecture.md).

## Confirmed technology stack

| Layer | Choice |
|---|---|
| Frontend | HTML, CSS, and JavaScript |
| Backend | Python and Flask |
| Database | SQLite (one local file for the first version) |
| API | REST API (JSON) |
| Version control | Git and GitHub |

The browser sends requests to Flask. Flask is the only part of the system that opens the SQLite file.

## Repository layout

```text
UI/           HTML, CSS, and JavaScript
BACKEND/      Flask application, SQL scripts, and tests
DOCS/         Architecture, database, API, setup, and user guides
```

## Current progress

Phase 1 (architecture and folders) is in place. Database tables, REST endpoints, and login are later phases. See [DOCS/setup-guide.md](DOCS/setup-guide.md) for local setup.
