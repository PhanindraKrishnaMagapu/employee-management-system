# API documentation

Status: health, authentication, employee CRUD, hierarchy data, JML, project
management, skills, employee skills, and salary endpoints are implemented.
Reports, an audit read API, and user/role administration APIs are not included.

## Conventions

- Base URL on your machine: `http://127.0.0.1:5000`
- The browser UI is served from that same origin. Start Flask with `python run.py`
  from `BACKEND/` and open <http://127.0.0.1:5000/>.
- Frontend requests use relative paths such as `/api/employees`. `UI/js/api.js`
  keeps `API_BASE_URL` empty and sends `credentials: "same-origin"`, so no CORS
  configuration or second frontend server is needed. External clients may use
  the absolute base URL above.
- All API responses are JSON with `Content-Type: application/json`.
- HTML, CSS, and JavaScript remain in `UI/`. Flask serves those files as static
  assets through the UI blueprint; no server-side templates are used.
- API routes are Flask blueprints under `BACKEND/app/routes/`, registered from
  `BACKEND/app/__init__.py`.

## Browser UI integration

The UI blueprint in `BACKEND/app/routes/ui.py` serves only `.html`, `.css`, and
`.js` files from `UI/`:

| Browser URL | Source |
|---|---|
| `/` | `UI/index.html` |
| `/pages/<filename>` | `UI/pages/<filename>` |
| `/css/<filename>` | `UI/css/<filename>` |
| `/js/<filename>` | `UI/js/<filename>` |

These routes deliver static files only. They do not query the database or
implement business logic.

| Screen | API calls | Behavior |
|---|---|---|
| Login | `POST /api/auth/login` | Creates the session and redirects to the dashboard. |
| Logout | `POST /api/auth/logout` | Destroys the session and clears cached user details. |
| Dashboard | `GET /api/auth/me`, `GET /api/employees` | Validates the session and computes total/active counts from the scoped list. Payroll Admin skips the employee call and sees salary access only. |
| Employee list and search | `GET /api/auth/me`, `GET /api/employees` | Renders visible records; search filters loaded records by name, email, or code in the browser. |
| Add employee | `POST /api/employees` | Creates a record when the role has `employees:create`. |
| Edit employee | `GET /api/employees/<id>`, `PUT /api/employees/<id>` | Prefills the form and submits only fields allowed for the role. |
| Archive employee | `DELETE /api/employees/<id>` | Soft-archives the record after confirmation; only HR Admin has the control. |
| Hierarchy | `GET /api/employees` | Builds the reporting tree in the browser from the already scoped employee list; there is no separate hierarchy API. |
| JML events | `GET /api/jml/events`, `POST /api/jml/events`, `GET/PATCH /api/jml/events/<event_id>`, `PATCH /api/jml/events/<event_id>/checklist/<item_id>` | Creates events, tracks checklist items, and shows Mover history. |
| Projects | `GET/POST /api/projects`, `GET/PUT /api/projects/<id>`, `GET /api/projects/assignable-employees`, `GET /api/projects/<id>/employees`, `POST /api/projects/<id>/assignments`, `DELETE /api/projects/<id>/assignments/<assignment_id>` | Lists and manages owned projects, the employee picker, and assignments. |
| Skills catalog | `GET/POST /api/skills`, `PUT /api/skills/<skill_id>` | Maintains the shared skill list. |
| Employee skills | `GET/POST /api/employees/<employee_id>/skills`, `PUT/DELETE /api/employees/<employee_id>/skills/<assignment_id>` | Assigns, updates, and removes employee skills within record scope. |
| Salaries | `GET /api/salaries`, `GET /api/salaries/employees` | Lists salary records with server-side search, filters, and pagination. |
| Salary form | `GET /api/salaries/<id>`, `POST /api/salaries`, `PUT /api/salaries/<id>` | Creates or edits one salary period. The employee is immutable on update. |
| Employee salary history | `GET /api/salaries?employee_id=<id>` | Shows the salary periods for one employee. Salary pages never call `/api/employees`. |

Every protected page calls `GET /api/auth/me` through `requireAuth()`. A `401`
redirects to the sign-in page, and a `403` displays a permission error. The
frontend role map hides controls that a role cannot use, but the backend checks
permissions and record scope on every request and remains the security boundary.

## Response format

Every response has a top-level `success` boolean. Failures also include `message`.
Responses that return resources use keys such as `user`, `employee`, `employees`,
`event`, `events`, `project`, `projects`, `skill`, `skills`, `assignment`,
`assignments`, `salary`, or `salaries` as appropriate.

Success:

```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "demo_ceo",
    "email": "ceo@example.invalid",
    "roles": ["CEO"]
  }
}
```

Failure:

```json
{ "success": false, "message": "Invalid username or password" }
```

`GET /api/auth/me` returns `{ "success": true, "user": { ... } }` without a `message`.
`GET /api/health` adds a `database` field with values `connected` or `disconnected`.

The earlier Phase 1 `{ "data": ..., "error": ... }` envelope was a plan and is not
used by the implemented endpoints.

## Implemented endpoints

### `GET /api/health`

Reports API and database availability.

- `200`: `{ "success": true, "message": "Employee Management System API is running", "database": "connected" }`
- `503`: `{ "success": false, "message": "Database connection failed", "database": "disconnected" }`

### `POST /api/auth/login`

Authenticates a user and creates a session.

Request body:

```json
{ "username": "demo_ceo", "password": "<demo password>" }
```

- `200`: `{ "success": true, "message": "Login successful", "user": { "id": ..., "username": ..., "email": ..., "roles": [...] } }`
- `400`: missing, empty, non-string fields, malformed JSON, or a JSON body that is not an object. Message: `"Username and password are required"`.
- `401`: unknown username, wrong password, inactive account, or a placeholder password hash. Message: `"Invalid username or password"` for all cases.
- `429`: too many failed attempts. Message: `"Too many login attempts. Please try again later."`

Failed attempts are throttled per `(client IP, username)`: five failures in a
300-second window block further attempts until the window expires. A successful
login clears the counter. Unknown and inactive usernames are verified against a
dummy password hash so response timing does not reveal whether an account exists.

Successful login clears any existing session, marks the session permanent, and stores only `user_id` in it.
The session cookie is `HttpOnly`, `SameSite=Lax`, and expires after the
configured eight-hour permanent-session lifetime. `FLASK_SECRET_KEY` must be a
non-default value whenever `FLASK_ENV` is not one of the explicitly recognized
development values; see [setup-guide.md](setup-guide.md#4-configure-environment-variables).
The in-memory login throttle applies to this process and is not shared between
multiple application workers.

### `POST /api/auth/logout`

Destroys the current session. A valid session is required.

- `200`: `{ "success": true, "message": "Logout successful" }`
- `401`: no valid authenticated user. Message: `"Authentication required"`.

### `GET /api/auth/me`

Returns the currently authenticated user.

- `200`: `{ "success": true, "user": { "id": ..., "username": ..., "email": ..., "roles": [...] } }`
- `401`: no session, or a session whose user was deleted or deactivated. Message: `"Authentication required"`. The stale session is cleared in that case.

Roles are returned as an alphabetically sorted list of role names. Returning roles
does not grant access by itself; authorization checks are separate.

### Employee CRUD endpoints

All employee endpoints require a session and are protected by the default-deny
guard. Permissions and record scope are described in
[Authorization (RBAC)](#authorization-rbac).

| Method | Path | Required permission | Success |
|---|---|---|---|
| `GET` | `/api/employees` | any employee read permission | `200` with `{ "success": true, "employees": [...] }` |
| `GET` | `/api/employees/<id>` | any employee read permission | `200` with `{ "success": true, "employee": { ... } }` |
| `POST` | `/api/employees` | `employees:create` | `201` with the created `employee` |
| `PUT` | `/api/employees/<id>` | one employee update permission | `200` with the updated `employee` |
| `DELETE` | `/api/employees/<id>` | `employees:archive` | `200` with `"Employee archived"` |

Required fields on create: `employee_code`, `first_name`, `last_name`,
`official_email`, `joining_date` (`YYYY-MM-DD`), `employment_type`,
`department_id`, and `designation_id`. Optional fields: `phone`,
`employment_status` (`Pre-joining`, `Active`, or `Exited`), `location`,
`manager_id`, and `profile_photo_path`. Unknown or unsupported fields are
rejected rather than ignored. A manager change is checked for direct and
indirect reporting cycles.

`PUT` is a partial update. The writable fields depend on the caller's grant:

- `employees:update` (HR Admin): all create fields.
- `employees:update:limited` (HR Executive, Department Manager): `phone` and `location`.
- `employees:update:self` (Employee): `phone` only.

Record scope still applies: HR Admin and CEO read across the organization,
Department Managers see their full reporting subtree, and Employee/HR Executive
see only their linked record. A missing record, an archived record, and a record
outside the caller's scope all return `404`.

`DELETE` archives the employee by setting `archived_at`; it does not remove
related rows or change user accounts. Archived employees are not returned by
read endpoints.

Responses never include `date_of_birth`, `emergency_contact`, `exit_reason`, or
salary fields, and those fields are rejected in request bodies.

Status codes:

- `200`: successful read, update, or archive.
- `201`: employee created.
- `400`: malformed JSON, missing/invalid fields, unsupported fields, an invalid reference, or a reporting cycle.
- `401`: no valid session.
- `403`: the session is valid but lacks the endpoint permission.
- `404`: missing, archived, or out-of-scope employee.
- `409`: duplicate `employee_code` or `official_email`.

There is no separate hierarchy API. The hierarchy screen builds its tree from
`GET /api/employees`, which already applies record scope.

### Project endpoints

Project routes require `projects:read` or `projects:manage`. Write routes require
`projects:manage`. HR Admin manages projects across the organization. A Project
Manager may view and manage only projects whose `manager_id` equals their linked
`users.employee_id`; CEO and Department Manager keep read-only visibility.
A missing or out-of-scope project returns `404`.

| Method | Path | Required permission | Success |
|---|---|---|---|
| `GET` | `/api/projects` | `projects:read` or `projects:manage` | `200` with `{ "success": true, "projects": [...] }` |
| `GET` | `/api/projects/assignable-employees` | `projects:manage` and `employees:read:all` | `200` with an active-employee picker |
| `GET` | `/api/projects/<id>` | `projects:read` or `projects:manage` | `200` with `project` and `assignments` |
| `GET` | `/api/projects/<id>/employees` | `projects:read` or `projects:manage` | `200` with `employees` and `assignments` |
| `POST` | `/api/projects` | `projects:manage` | `201` with the created `project` |
| `PUT` | `/api/projects/<id>` | `projects:manage` | `200` with the updated `project` |
| `POST` | `/api/projects/<id>/assignments` | `projects:manage` | `201` with the created `assignment` |
| `DELETE` | `/api/projects/<id>/assignments/<assignment_id>` | `projects:manage` | `200` with `"Employee assignment removed"` |

Project create fields: `project_code` and `name` are required. Optional fields:
`description`, `status`, `start_date`, `end_date`, and `manager_id`. `status` is
one of `Planned` (the default), `In Progress`, `Completed`, or `On Hold`. Dates
use strict `YYYY-MM-DD`, and `end_date` cannot be earlier than `start_date`.
`PUT` is a partial update of the same fields.

`manager_id` can be set only by HR Admin. When a Project Manager creates a
project, their linked employee id is stored as `manager_id` automatically; a
manager_id in their request is rejected, and an unlinked Project Manager account
cannot create a project.

Assignment create fields: `employee_id` and `start_date` are required;
`end_date` and `allocation_percentage` are optional. Allocation defaults to
`100` and must be greater than `0` and at most `100`. Assignments may reference
only active employees within the caller's employee scope. Duplicate assignments
return `409`.

Status codes:

- `200`: successful read, update, or removal.
- `201`: project or assignment created.
- `400`: malformed JSON, missing/invalid/unsupported fields, an invalid reference, or an invalid manager assignment.
- `401`: no valid session.
- `403`: the session lacks a project permission.
- `404`: missing or out-of-scope project, employee, or assignment.
- `409`: duplicate project code or duplicate employee assignment.

### JML event endpoints

JML routes require `jml:read` or `jml:manage`; write routes require `jml:manage`.
Events are visible only for employees in the caller's record scope.

| Method | Path | Required permission | Success |
|---|---|---|---|
| `GET` | `/api/jml/events` | `jml:read` or `jml:manage` | `200` with `{ "success": true, "events": [...] }` |
| `GET` | `/api/jml/events/<event_id>` | `jml:read` or `jml:manage` | `200` with `event`, `checklist_items`, and `history` |
| `POST` | `/api/jml/events` | `jml:manage` | `201` with the created `event` |
| `PATCH` | `/api/jml/events/<event_id>` | `jml:manage` | `200` with the updated `event` |
| `PATCH` | `/api/jml/events/<event_id>/checklist/<item_id>` | `jml:manage` | `200` with `checklist_item` and `event` |

Create fields: `employee_id`, `event_type`, and `effective_date` are required.
`event_type` is `Joiner`, `Mover`, or `Leaver`; `effective_date` uses strict
`YYYY-MM-DD`. `reason` is optional, except that it is required for a Leaver.
`changes` is allowed only for a Mover and is required in that case. A Mover's
`changes` object accepts `department_id`, `designation_id`, `manager_id`, and
`location`; references and reporting cycles are validated when the event is
created.

Each new event receives a default checklist: three items for a Joiner, four for
a Mover, and four for a Leaver. Checklist items use `Pending` or `Completed`
status; the event PATCH body and checklist PATCH body accept only `{ "status":
"..." }`.

Event status transitions:

- `Pending` to `In Progress`, `Completed`, or `Cancelled`.
- `In Progress` to `Completed` or `Cancelled`.
- `Completed` and `Cancelled` are terminal; no further transition is allowed.

Completion requires every checklist item to be `Completed`. A Leaver also
requires the `Access removal confirmed` item. The status change is re-validated
under the database write lock so a concurrent request cannot bypass the
transition table.

- A Joiner sets the employee's `employment_status` to `Active` on completion.
- A Leaver sets `employment_status` to `Exited` and deactivates only user
  accounts whose `users.employee_id` links them to that employee.
- Mover changes are stored in `jml_events.pending_changes` and applied only on
  completion, with a row in `employee_history`. Cancelling a Mover leaves the
  employee record unchanged.

An out-of-scope or missing event returns `404`. Mover history is included only
in the single-event response for Mover events. `reason` is included in event
responses only for callers with `jml:manage`.

Status codes:

- `200`: successful read or update.
- `201`: event created.
- `400`: malformed JSON, invalid fields, an invalid transition, an incomplete checklist, or an invalid reference.
- `401`: no valid session.
- `403`: the session lacks a JML permission.
- `404`: missing or out-of-scope employee, event, or checklist item.
- `409`: an invalid employee reference at completion time.

### Skill catalog endpoints

Skill routes require `skills:read` or `skills:manage`; write routes require
`skills:manage`.

| Method | Path | Required permission | Success |
|---|---|---|---|
| `GET` | `/api/skills` | `skills:read` or `skills:manage` | `200` with `{ "success": true, "skills": [...] }` |
| `POST` | `/api/skills` | `skills:manage` | `201` with the created `skill` |
| `PUT` | `/api/skills/<skill_id>` | `skills:manage` | `200` with the updated `skill` |

`GET /api/skills` accepts an optional `search` query parameter. `POST` requires
a non-empty `name`; `description` is optional. `PUT` is a partial update of
those fields. Duplicate skill names return `409`. A missing skill returns `404`.

### Employee skill endpoints

These routes require `skills:read` or `skills:manage`; write routes require
`skills:manage`. The employee must exist, be in the caller's record scope, and
be active for new assignments.

| Method | Path | Required permission | Success |
|---|---|---|---|
| `GET` | `/api/employees/<employee_id>/skills` | `skills:read` or `skills:manage` | `200` with `employee` and `assignments` |
| `POST` | `/api/employees/<employee_id>/skills` | `skills:manage` | `201` with the created `assignment` |
| `PUT` | `/api/employees/<employee_id>/skills/<assignment_id>` | `skills:manage` | `200` with the updated `assignment` |
| `DELETE` | `/api/employees/<employee_id>/skills/<assignment_id>` | `skills:manage` | `200` with `"Employee skill removed"` |

Assignment create fields: `skill_id` and `proficiency_level` are required;
`experience_years` defaults to `0`, and `last_verified` is optional. Proficiency
is one of `Beginner`, `Intermediate`, `Advanced`, or `Expert`. Dates use strict
`YYYY-MM-DD`, and `experience_years` must be a non-negative finite number. `PUT`
accepts only `proficiency_level`, `experience_years`, and `last_verified`;
`skill_id` is immutable on update. Duplicate assignments return `409`.

Status codes:

- `200`: successful read, update, or removal.
- `201`: assignment created.
- `400`: malformed JSON, invalid fields, an inactive employee, or an unknown skill.
- `401`: no valid session.
- `403`: the session lacks a skills permission.
- `404`: missing or out-of-scope employee or assignment.
- `409`: the employee already has this skill.

### Salary endpoints

Salary data is deliberately isolated from the general employee API. All salary
routes live under `/api/salaries`, require an explicit salary permission, and
return `Cache-Control: no-store`. Payroll Admin is the only role that grants
salary access; combined roles remain additive. Payroll Admin receives
organization-wide salary scope without receiving the general employee read
permission.

| Method | Path | Required permission | Success |
|---|---|---|---|
| `GET` | `/api/salaries` | `salary:read` or `salary:manage` | `200` with `salaries`, `total`, `limit`, and `offset` |
| `GET` | `/api/salaries/employees` | `salary:read` or `salary:manage` | `200` with a minimal non-archived employee picker |
| `GET` | `/api/salaries/<id>` | `salary:read` or `salary:manage` | `200` with the salary record |
| `POST` | `/api/salaries` | `salary:manage` | `201` with the created salary record |
| `PUT` | `/api/salaries/<id>` | `salary:manage` | `200` with the updated salary record |

There is no salary `DELETE` endpoint. Salary history is closed by setting
`effective_to` with `PUT`; records are never deleted.

Create fields: `employee_id`, `annual_salary`, `currency`, `effective_from`,
and `effective_to`. `currency` is optional and defaults to `INR`; when supplied
it is normalized to three uppercase letters. `effective_to` is optional.
`PUT` is a partial update and accepts only `annual_salary`, `currency`,
`effective_from`, and `effective_to`; `employee_id` is immutable. Unknown fields
such as `net_salary`, `tax`, `bank_account`, or `payslip` are rejected.

Validation:

- `annual_salary` must be a finite JSON number from `0` to `1,000,000,000` with
  at most two decimal places.
- `effective_from` and `effective_to` must be strict `YYYY-MM-DD` dates, and
  `effective_to` must be on or after `effective_from`.
- Salary periods for one employee must not overlap; a conflict returns `409`.
- Creating a period later than an existing open-ended period automatically
  closes the earlier period the day before the new `effective_from`.
- Archived employees retain readable salary history. New records are rejected
  with `400`; existing records may still be corrected or closed with `PUT`,
  subject to the same date and overlap validation. `employee_id` is immutable.
- A missing employee, missing salary record, or out-of-scope employee returns
  `404`.

List query parameters: `employee_id`, `search` (employee code, first name, last
name, or official email), `currency`, `active_on`, `effective_from` and
`effective_to` start-date bounds, `limit` (default `100`, maximum `500`), and
`offset`. Records are ordered by `effective_from` descending, then `id`
descending.

Salary responses use an explicit salary allowlist plus a minimal employee
summary containing only `id`, `employee_code`, `first_name`, `last_name`,
`official_email`, `employment_status`, `department_id`, and `designation_id`.
Restricted employee fields, phone, and all other employee fields are never
included. Salary fields remain absent from `/api/employees` responses and are
rejected in employee create/update bodies.

Every successful salary creation and update writes rows to the existing
`audit_logs` table in the same transaction. The audit row stores only the actor
user id, action (`salary.create` or `salary.update`), table name
(`salary_records`), salary record id, and a summary containing only the
employee id. When a create automatically closes an earlier open-ended period,
the request writes a separate `salary.update` row for the closed record and a
`salary.create` row for the new record, both in that same transaction. Amounts,
currency, effective dates, bank details, tax information, and other salary
values are never written to the audit log. Failed writes do not create audit
rows.

Status codes:

- `200`: successful read or update.
- `201`: salary record created.
- `400`: malformed JSON, missing/invalid/unsupported fields, invalid date range,
  or a new record for an archived employee.
- `401`: no valid session.
- `403`: the session lacks a salary permission.
- `404`: missing employee or salary record.
- `409`: overlapping salary period.

## Session security

- Session cookies are `HttpOnly` and `SameSite=Lax`.
- `Secure` is enabled outside explicit development environments.
- Startup refuses the default development `FLASK_SECRET_KEY` unless `FLASK_ENV`
  is one of `development`, `dev`, `local`, `test`, or `testing`. Set a unique
  `FLASK_SECRET_KEY` for any other environment.
- Login uses a permanent session with an 8-hour lifetime (`PERMANENT_SESSION_LIFETIME`).
- Non-permanent sessions still expire when the browser closes.
- Login failures are throttled to five attempts per 300 seconds per client IP
  and username.

## Authorization (RBAC)

The session stores only `user_id`. On every request, the active user and their
roles are loaded from the database and cached in `flask.g` for that request.
Roles and permissions are never stored in the session, so a role change takes
effect on the next request without logging in again. Multiple roles combine as
a union of permissions; there is no deny-overrides rule.

### Default-deny policy

All `/api/*` routes require authentication and an explicit authorization
decorator. The only public routes are `GET /api/health` and
`POST /api/auth/login`. `GET /api/auth/me` and `POST /api/auth/logout` require
authentication but no specific permission. Every other route must use one of
`require_permission`, `require_any_permission`, `require_all_permissions`, or
`require_authentication`. Undecorated or unknown API routes are denied rather
than being accidentally public.

| Status | Meaning | JSON |
|---|---|---|
| `401` | No valid authenticated user (unauthenticated, inactive, or deleted) | `{ "success": false, "message": "Authentication required" }` |
| `403` | Authenticated user lacks the endpoint permission, or the route is not explicitly authorized | `{ "success": false, "message": "Permission denied" }` |
| `404` | The requested record is missing or exists but is outside the user's scope | `{ "success": false, "message": "Resource not found" }` |
| `429` | Login throttled after five failures in 300 seconds | `{ "success": false, "message": "Too many login attempts. Please try again later." }` |

Using `404` for out-of-scope records prevents an authorized-looking caller from
enumerating records they may not see.

### Permission matrix

| Role | Employee records | Salary | Technical admin | Other |
|---|---|---|---|---|
| `CEO` | Organization-wide read-only | No | No | Org read, JML read, project read, skills read, reports |
| `HR Admin` | All employees; create, update, archive, JML | **No** unless also `Payroll Admin` | No | Org read, project read/manage all projects, skills manage, reports |
| `HR Executive` | Self only until assigned scope is implemented | No | No | Limited HR update, org read, JML read, skills read |
| `Department Manager` | Full reporting subtree; limited team updates | No | No | Org read, JML read, project read, skills read |
| `Project Manager` | No general employee record scope; project employee picker only | No | No | Project read/manage for projects where `manager_id` is their linked employee |
| `Employee` | Own linked record and self-service updates | No | No | Org read, skills read |
| `System Admin` | **None** | **No** | Users, roles, audit read | No business data |
| `Payroll Admin` | None | **Salary read/manage** | No | Explicit grant only; never auto-assigned |

The browser UI exposes employee controls only for CEO, HR Admin, HR Executive,
Department Manager, and Employee. Salary screens are shown only when the user
has a salary capability. Project Manager, System Admin, and Payroll Admin can
sign in but do not receive general employee records; Project Manager sees project
screens and Payroll Admin sees salary screens.

Salary access is granted only by assigning the `Payroll Admin` role. No seeded
demo account receives it automatically. `users.employee_id` links a login to a
single employee record so self and team scope can be resolved; demo accounts
are left unlinked because the seed data has no explicit mapping.

Payroll Admin resolves salary scope through a salary-specific helper, not the
shared employee scope. This keeps `/api/employees` closed while allowing
organization-wide salary access. Because `/api/salaries` is outside the
`/api/employees` Project Manager carve-out, combined roles such as
`Project Manager` + `Payroll Admin` receive salary access without gaining
general employee access.

Project scoping uses `projects.manager_id`, added by migration 002. HR Admin can
read and manage all projects. A Project Manager can read and manage only
projects whose `manager_id` equals their linked `users.employee_id`; CEO and
Department Manager retain read-only visibility. The `employees:read:all` grant
on the Project Manager role is used only by the project employee picker and does
not change general employee record scope. Roles are additive; a user who also
has HR Admin receives the HR Admin organization-wide project scope. Migration
002 also adds `jml_events.pending_changes`, which stores proposed Mover fields
until event completion; it does not introduce a separate JML employee-scope
column.

The employee CRUD endpoints implement the explicit `EMPLOYEE_PUBLIC_FIELDS`
allowlist. `date_of_birth`, `emergency_contact`, `exit_reason`, and salary fields
are neither accepted in request bodies nor returned in responses, and queries do
not use `SELECT *`. Salary endpoints use their own explicit salary and minimal
employee-summary allowlists.

For testing, a blueprint is registered only inside the pytest fixture. It uses
the real decorators to verify permissions and record scope. It is never
registered by `create_app()`. The production employee, project, JML, skill, and
salary APIs are all protected by the same default-deny guard.

## Future security work (not implemented in this phase)

- CSRF protection for session-authenticated state-changing requests.
- Audit-log entries for login, logout, and failed authentication attempts.
- Input length limits for authentication fields.
- Assigned-department scope for HR Executive.

## Planned areas

Employee CRUD, JML, project management, skills, employee skills, and salary are
documented above. There is no separate dashboard or hierarchy endpoint; the
dashboard derives its employee counts from `GET /api/employees`, skips that call
for salary-only roles, and the hierarchy screen builds its tree from the same
list. Organization, reports, audit, users, and roles areas will be documented
here as their routes are added. New routes must use the authorization decorators
described above; do not expose real employee data through an unprotected
endpoint.

See [architecture.md](architecture.md).
