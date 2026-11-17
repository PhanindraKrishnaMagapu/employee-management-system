# Database Design – Employee Management System

**Status:** Phase 2 – Implemented and tested  
**Database Engine:** SQLite  
**Backend:** Python + Flask

## 1. Database Location

- Database file: `BACKEND/database/ems.sqlite`
- Schema file: `BACKEND/database/schema.sql`
- Seed data: `BACKEND/database/seed.sql`
- Database connection: `BACKEND/app/db.py`
- Automated tests: `BACKEND/tests/test_schema.py`

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
- Unique constraints for usernames, user emails, employee codes, official employee emails, department names, designation titles, project codes, and skill names.
- Check constraints for selected status and type fields.
- Indexes for commonly queried employee and relationship fields.

## 5. Demo Data

The development seed file inserts fictional sample records:

- 7 system roles
- 7 demo users
- 3 departments
- 5 designations
- 7 demo employees

Seed operations use `INSERT OR IGNORE` to avoid duplicate sample records when initialization is repeated.

The sample password hashes are temporary unusable placeholders. Authentication and proper password hashing will be implemented in the authentication phase.

Only fictional development data should be used.

## 6. Confidential Information

The following information must receive appropriate access restrictions:

- Salary information
- Date of birth
- Emergency contact information
- Employee exit reasons

These fields must not be exposed in general employee API responses.

Role-based authorization and field-level access controls will be implemented in later phases.

## 7. Database Initialization

From the `BACKEND` directory, initialize the database using:

```powershell
python -m app.db init
```

To initialize without inserting demo data:

```powershell
python -m app.db init --no-seed
```

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

**Latest result: 6 tests passed, 0 failed.**

## 9. Future Improvements

Later development phases will implement:

- Authentication and role-based access control.
- Employee CRUD APIs.
- Organization hierarchy.
- Joiner, Mover, and Leaver workflows.
- Project and skill management.
- Salary management.
- Reporting and audit functionality.

See `architecture.md` for the overall system architecture.
