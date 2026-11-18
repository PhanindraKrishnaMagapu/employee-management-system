# Database Design – Employee Management System

**Status:** Phase 2 – Implemented and tested  
**Database Engine:** SQLite  
**Backend:** Python + Flask

## 1. Database Location

- Database file: `BACKEND/database/ems.sqlite`
- Schema file: `BACKEND/database/schema.sql`
- Seed data: `BACKEND/database/seed.sql`
- Additive migrations: `BACKEND/database/migrations/`
- Database connection and migration runner: `BACKEND/app/db.py`
- Automated tests: `BACKEND/tests/test_schema.py`, `test_rbac_permissions.py`

The SQLite database is created locally and excluded from Git using `.gitignore`.

The browser does not connect directly to SQLite. Database access will be handled through the Flask backend API.

## 2. Database Tables

The database contains 15 application tables.

| Table | Purpose |
|---|---|
| `roles` | Stores system roles such as HR Admin and Employee |
| `users` | Stores user login accounts |
| `user_roles` | Maps users to their assigned roles |
| `departments` | Stores company departments |
| `designations` | Stores employee job titles |
| `employees` | Stores employee information |
| `employee_history` | Maintains employee organizational history |
| `projects` | Stores project information |
| `project_assignments` | Tracks employee project assignments |
| `skills` | Stores available skills |
| `employee_skills` | Maps skills to employees |
| `salary_records` | Stores employee salary history |
| `jml_events` | Stores Joiner, Mover, and Leaver events |
| `checklist_items` | Stores JML process checklist items |
| `audit_logs` | Records system activities and changes |

## 3. Main Relationships

- Users and roles have a many-to-many relationship through `user_roles`.
- A user may be linked to one employee record through `users.employee_id`; the
  column is nullable and a unique index prevents one employee from being linked
  to several accounts. This link resolves self and manager-team scope.
- Employees belong to departments and designations.
- Employees can have a manager through the employee self-reference.
- Employee history records organizational changes.
- Employees and projects are connected through `project_assignments`.
- Employees and skills are connected through `employee_skills`.
- Salary records belong to employees.
- JML events belong to employees.
- Checklist items belong to JML events.
- Audit logs record actions performed in the system.

Foreign-key constraints are enabled whenever a database connection is opened.

## 4. Data Integrity

The database uses:

- Primary keys for record identification.
- Foreign keys to maintain relationships.
- Unique constraints for usernames, user emails, employee codes, official employee emails, department names, designation titles, project codes, and skill names, plus a unique index on `users.employee_id`.
- Check constraints for selected status and type fields.
- Indexes for commonly queried employee and relationship fields.

## 5. Demo Data

The development seed file inserts fictional sample records:

- 8 system roles (the seven original roles plus `Payroll Admin`)
- 7 demo users, all with `employee_id = NULL`
- 3 departments
- 5 designations
- 7 demo employees

Seed operations use `INSERT OR IGNORE` to avoid duplicate sample records when initialization is repeated.

The existing seed data has no explicit user-to-employee relationship. Names,
e-mails, and job titles are not sufficient evidence, so all demo mappings are
left `NULL` rather than guessed. Assign them deliberately when real linking is
required. `Payroll Admin` is seeded as a role but is never assigned to a demo
user automatically.

The seed file writes deliberately unusable placeholder hashes for the seven demo users. A development-only command, `python -m app.db demo-passwords`, replaces only those placeholders with Werkzeug hashes supplied interactively. It preserves existing valid hashes unless `--force` is given, refuses to run in production, and never writes a password to the repository. See `setup-guide.md`.

Only fictional development data should be used.

## 6. Confidential Information

The following information must receive appropriate access restrictions:

- Salary information
- Date of birth
- Emergency contact information
- Employee exit reasons

These fields must not be exposed in general employee API responses. The RBAC
foundation defines `EMPLOYEE_PUBLIC_FIELDS` as the allowlist for future
serializers; it excludes all restricted and salary fields.

`Payroll Admin` is the only role that grants salary permissions. HR Admin, CEO,
and all other roles need that extra role to read or manage salary records.

## 7. Database Initialization

From the `BACKEND` directory, initialize the database using:

```powershell
python -m app.db init
```

To initialize without inserting demo data:

```powershell
python -m app.db init --no-seed
```

### Applying the additive RBAC migration

Existing databases created before this change do not have the employee link or
the `Payroll Admin` role. Apply the additive migration with:

```powershell
python -m app.db migrate
```

The runner reads the SQL files in `BACKEND/database/migrations/` in order,
records completed migrations in `schema_migrations`, and skips an
`ALTER TABLE ... ADD COLUMN` when the column already exists. It is therefore
safe to re-run. The migration only adds a nullable column, a unique index, and
one role; it never drops or recreates tables, deletes rows, or changes password
hashes. Fresh databases created with `schema.sql` already contain all of these
objects and need no migration.

Use a copy of the database (or a temporary `DATABASE_PATH`) when trying a
migration. The local `BACKEND/database/ems.sqlite` must not be reinitialized,
and its demo password hashes must not be reset.

## 8. Automated Testing

Run the database tests from the `BACKEND` directory:

```powershell
python -m pytest tests/test_schema.py -v
```

Current Phase 2 test results:

- All 15 tables created successfully.
- Foreign-key enforcement verified.
- Demo employee and user records verified.
- Duplicate employee code rejected.
- Salary record requires an existing employee.
- Repeated database initialization does not duplicate demo records.

RBAC tests additionally verify role mappings, employee scope, manager cycles,
missing links, and that migration is idempotent and preserves existing rows and
password hashes. **Latest full backend result: 101 tests passed, 0 failed.**

## 9. Future Improvements

Later development phases will implement:

- Assigned-department scope for HR Executive and project scope for Project Manager.
- Employee CRUD APIs.
- Organization hierarchy.
- Joiner, Mover, and Leaver workflows.
- Project and skill management.
- Salary management.
- Reporting and audit functionality.

See `architecture.md` for the overall system architecture.
