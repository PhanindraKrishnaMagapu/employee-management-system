# Database Design – Employee Management System

**Status:** Implemented and tested (287 backend tests passed)
**Database Engine:** SQLite
**Backend:** Python + Flask

## 1. Database Location

- Database file: `BACKEND/database/ems.sqlite`
- Schema file: `BACKEND/database/schema.sql`
- Seed data: `BACKEND/database/seed.sql`
- Additive migrations: `BACKEND/database/migrations/` (`001_rbac_scope_links.sql`, `002_project_manager_jml_scope.sql`)
- Database connection and migration runner: `BACKEND/app/db.py`
- Automated tests: `BACKEND/tests/`

The SQLite database is created locally and excluded from Git using `.gitignore`.

The browser does not connect directly to SQLite. Database access is handled through the Flask backend API.

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
  to several accounts. This link resolves self and manager-team scope and
  determines which user accounts are deactivated when a Leaver event completes.
- Employees belong to departments and designations.
- Employees can have a manager through the employee self-reference.
- Employee history records organizational changes, including completed Mover events.
- Projects have an optional owner through `projects.manager_id`, which references
  `employees(id)` and is indexed by `idx_projects_manager`. Project Manager
  access is restricted to projects owned by their linked employee record.
- Employees and projects are connected through `project_assignments`.
- Employees and skills are connected through `employee_skills`.
- Salary records belong to employees.
- JML events belong to employees. `jml_events.pending_changes` stores the JSON
  payload of a Mover's proposed changes until the event is completed; a
  cancelled Mover leaves the employee record unchanged.
- Checklist items belong to JML events.
- Audit logs record actions performed in the system, including safe salary
  create and update summaries.

Foreign-key constraints are enabled whenever a database connection is opened.

## 4. Data Integrity

The database uses:

- Primary keys for record identification.
- Foreign keys to maintain relationships.
- Unique constraints for usernames, user emails, employee codes, official employee emails, department names, designation titles, project codes, and skill names, plus a unique index on `users.employee_id`.
- Check constraints for selected status and type fields.
- Indexes for commonly queried employee and relationship fields, including
  `idx_projects_manager` for project ownership lookups.

Application-level rules validate JML status transitions, require all checklist
items (plus access-removal confirmation for a Leaver) before completion, and
reject direct or indirect reporting cycles when a manager is changed.

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
foundation defines `EMPLOYEE_PUBLIC_FIELDS` as the allowlist used by the current
employee, JML, project, and employee-skill serializers; it excludes all
restricted and salary fields.

`Payroll Admin` is the only role that grants salary permissions. HR Admin, CEO,
and all other roles need that extra role to read or manage salary records.

The salary module reuses the existing `salary_records` table without schema or
migration changes. Application-level validation enforces strict ISO dates,
non-overlapping periods per employee, a non-negative amount with at most two
decimal places, and a three-letter uppercase currency. Creating a later period
closes an earlier open-ended period the day before the new `effective_from`.
Archived employees keep readable history and cannot receive new records, but
existing records can still be corrected or closed with the same date and
overlap validation. There is no salary delete endpoint; history is closed by
setting `effective_to`. Every successful salary creation and update writes a
safe row to the existing `audit_logs` table containing only the actor, action,
table name, salary record id, and employee id; an automatic close writes a
separate `salary.update` row for the closed record in the same transaction as
the new record's `salary.create` row. No salary amounts, currency, effective
dates, bank details, or tax values are stored in the audit log.

## 7. Database Initialization

From the `BACKEND` directory, initialize the database using:

```powershell
python -m app.db init
```

To initialize without inserting demo data:

```powershell
python -m app.db init --no-seed
```

### Applying additive migrations

Existing databases created before these changes need two additive migrations:

| Migration | Changes |
|---|---|
| `001_rbac_scope_links.sql` | Adds `users.employee_id`, `idx_users_employee_id`, and the `Payroll Admin` role. |
| `002_project_manager_jml_scope.sql` | Adds `projects.manager_id` and its index for project ownership, plus `jml_events.pending_changes` for deferred Mover changes. It adds no JML scope column. |

Apply them from the `BACKEND` directory with:

```powershell
python -m app.db migrate
```

The runner reads the SQL files in `BACKEND/database/migrations/` in order,
records completed migrations in `schema_migrations`, and skips an
`ALTER TABLE ... ADD COLUMN` when the column already exists. It is therefore
safe to re-run. The migrations only add nullable columns, indexes, and one role;
they never drop or recreate tables, delete rows, or change password hashes.
Fresh databases created with `schema.sql` already contain all of these objects
and need no migration.

Use a copy of the database (or a temporary `DATABASE_PATH`) when trying a
migration. The local `BACKEND/database/ems.sqlite` must not be reinitialized,
and its demo password hashes must not be reset.

## 8. Automated Testing

Run the database tests from the `BACKEND` directory:

```powershell
python -m pytest tests/test_schema.py -v
```

Database tests verify:

- All 15 tables created successfully.
- Foreign-key enforcement verified.
- Demo employee and user records verified.
- Duplicate employee code rejected.
- Salary record requires an existing employee.
- Repeated database initialization does not duplicate demo records.

RBAC tests additionally verify role mappings, employee scope, manager cycles,
missing links, and that migrations are idempotent and preserve existing rows and
password hashes. Other suites cover employee CRUD, hierarchy, projects,
assignments, JML transitions and deferred Mover changes, skills, employee
skills, salary validation, and login throttling.

**Latest full backend result: 287 tests passed, 0 failed.**

## 9. Future Improvements

Later development phases may implement:

- Assigned-department scope for HR Executive.
- Reporting and an audit read interface.
- User and role administration screens.

Project Manager ownership scope, JML status handling, skills, employee skills,
and salary are already implemented.

See `architecture.md` for the overall system architecture.
