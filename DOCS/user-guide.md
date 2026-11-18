# User guide

Status: login, dashboard, employee list/search, add, edit, soft archive, and role-based access are implemented in the browser UI.

The UI is served by Flask. Start the application as described in
[setup-guide.md](setup-guide.md), then open <http://127.0.0.1:5000/>. Do not open
`UI/index.html` directly from the file system.

## Sign in and sign out

1. On the sign-in page, enter a provisioned username and password.
2. Select **Sign in**. The browser calls `POST /api/auth/login`. A successful
   login creates the server-side session and redirects to the dashboard.
3. Use **Log out** in the sidebar. The browser calls `POST /api/auth/logout`,
   clears the cached user details, and returns to the sign-in page.

Protected pages call `GET /api/auth/me` before rendering. An expired or invalid
session returns `401` and redirects to the sign-in page. Only non-sensitive user
details (id, username, email, and roles) are cached in the browser; the
authentication cookie is managed by Flask.

## Dashboard

The dashboard shows:

- **Total employees** – the number of active records returned by `GET /api/employees`.
- **Active employees** – the subset of those records with status `Active`.
- **Your access** – organization-wide access or assigned scope.
- Quick links to the employee list and, for permitted roles, the add form.

Counts are calculated in the browser from the records visible to the signed-in
user. There is no separate dashboard API endpoint.

## Employee list and search

Open **Employees** from the sidebar. The page loads `GET /api/employees` and
shows code, name, official email, phone, and employment status for records
visible to the current role.

The search box filters the loaded records by employee name, official email, or
employee code. Search is client-side; there is no backend search endpoint.

The **Add employee** link and the per-row **Edit** and **Archive** actions are
shown only when the role's UI capability map allows them. The backend still
checks every request and remains the security boundary.

## Add an employee

Select **Add employee**. The shared form calls `POST /api/employees`.

Required fields are employee code, first name, last name, official email,
joining date (`YYYY-MM-DD`), employment type, department ID, and designation ID.
Optional fields are phone, employment status, location, manager ID, and profile
photo path. Department, designation, and manager are numeric IDs because lookup
screens are not implemented in this phase.

A successful save shows a success message on the employee list. Duplicate codes
or emails, invalid references, and invalid field values are reported as errors.

## Edit an employee

Use the **Edit** link in the employee list. The page reads the record with
`GET /api/employees/<id>` and submits changes with `PUT /api/employees/<id>`.

Only fields permitted for the current role are displayed:

- HR Admin: all add/edit fields.
- HR Executive and Department Manager: `phone` and `location`.
- Employee: `phone` only.

A record outside the user's scope cannot be read or updated; the API returns
`404` rather than revealing that it exists.

## Archive an employee

Use **Archive** in the employee list and confirm the prompt. The browser calls
`DELETE /api/employees/<id>`. This is a soft archive: the employee is marked
with `archived_at`, is hidden from lists and read endpoints, and related records
are not deleted. Only HR Admin has the archive action.

## Messages and errors

Success and error messages appear at the top of the page. A `401` response
returns the user to sign-in. A `403` response means the role lacks the endpoint
permission. A `404` response means the record is missing, archived, or outside
the role's scope. A `409` response means the employee code or email already
exists.

Restricted fields (`date_of_birth`, `emergency_contact`, `exit_reason`) and
salary fields are not shown or returned by the employee API.

## Roles and current restrictions

| Role | Employee access in the UI |
|---|---|
| `CEO` | Organization-wide read-only; no add, edit, or archive controls. |
| `HR Admin` | All employees; add, full edit, and archive. No salary screen. |
| `HR Executive` | Linked record only in the current implementation; limited `phone` and `location` edit. No add or archive. |
| `Department Manager` | Full reporting subtree; limited `phone` and `location` edit. No add or archive. |
| `Employee` | Own linked record; `phone` self-update only. No add or archive. |
| `Project Manager` | Sign-in and dashboard only; no employee records in this phase. |
| `System Admin` | Sign-in and dashboard only; technical admin APIs have no UI here. |
| `Payroll Admin` | Sign-in and dashboard only; no employee or salary UI in this phase. |

Scope is resolved by the backend. HR Admin and CEO can read all records;
Department Managers see their full reporting subtree; Employee and HR Executive
see only their linked employee record. A user without a linked record has no
scoped employee access.

The UI hides controls early for a better experience, but hiding a control is not
a security mechanism. Every `/api/*` request is evaluated by Flask's
default-deny guard; the only public exceptions are `GET /api/health` and
`POST /api/auth/login`. Unknown or undecorated API routes are denied.

## Current limitations

- Search applies only to records already returned for the user's scope.
- Department, designation, and manager are numeric ID inputs.
- The dashboard has no separate API; counts come from `GET /api/employees`.
- Auth responses do not include an employee ID, so the UI cannot precisely
  identify the signed-in user's own record; the backend still rejects all
  out-of-scope reads and updates.
- Organization tree, departments/designations, JML, projects, skills, salary,
  reports, audit, users, and roles screens are not implemented in this phase.
