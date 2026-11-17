# Database design

Status: not designed yet. Phase 2 will add the tables.

## Where the database lives

- Engine: SQLite.
- Local file: `BACKEND/database/ems.sqlite`.
- That file is created on your machine and is ignored by Git.
- The table definitions will be written in `BACKEND/database/schema.sql`.
- Fake development rows will be written in `BACKEND/database/seed.sql`.
- Flask will open the file through `BACKEND/app/db.py`.

Phase 1 leaves `schema.sql`, `seed.sql`, and `db.py` as placeholders. No tables, indexes, or rows exist yet.

The browser does not connect to SQLite. Only the Flask API will.

## Planned table groups

These names match the product scope. They are a checklist for Phase 2, not tables in the database today.

| Group | Will hold |
|---|---|
| Users and roles | Login accounts and the seven roles from the statement of work |
| Employees | People, employment status, department, designation, and manager |
| History | Earlier department, title, manager, and location values |
| Organization | Departments and job titles |
| JML | Joiner, mover, and leaver events plus checklists |
| Projects | Projects and assignment history |
| Skills | Skill catalogue and employee skills |
| Salary | Restricted pay history |
| Audit | Who changed which record, and when |

Confidential fields (salary, date of birth, emergency contact, and exit reason) will be omitted from general employee responses when the API is built. Phase 1 has no API responses yet.

See [architecture.md](architecture.md) for how this file fits the rest of the system.
