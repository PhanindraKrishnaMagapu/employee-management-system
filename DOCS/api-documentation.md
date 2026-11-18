# API documentation

Status: health, authentication, and employee CRUD endpoints, the RBAC foundation,
and the additive database migration are implemented. Payroll, project management,
and advanced reporting are not included.

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
| Dashboard | `GET /api/auth/me`, `GET /api/employees` | Validates the session and computes total/active counts from the scoped list. |
| Employee list and search | `GET /api/auth/me`, `GET /api/employees` | Renders visible records; search filters loaded records by name, email, or code in the browser. |
| Add employee | `POST /api/employees` | Creates a record when the role has `employees:create`. |
| Edit employee | `GET /api/employees/<id>`, `PUT /api/employees/<id>` | Prefills the form and submits only fields allowed for the role. |
| Archive employee | `DELETE /api/employees/<id>` | Soft-archives the record after confirmation; only HR Admin has the control. |

Every protected page calls `GET /api/auth/me` through `requireAuth()`. A `401`
redirects to the sign-in page, and a `403` displays a permission error. The
frontend role map hides controls that a role cannot use, but the backend checks
permissions and record scope on every request and remains the security boundary.

## Response format

Every response has a top-level `success` boolean. Failures also include `message`.
Successful responses that return one resource use a `user` or `employee` key;
list responses use `employees`.

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

Successful login clears any existing session, marks the session permanent, and stores only `user_id` in it.

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
rejected rather than ignored.

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
- `400`: malformed JSON, missing/invalid fields, unsupported fields, or an invalid reference.
- `401`: no valid session.
- `403`: the session is valid but lacks the endpoint permission.
- `404`: missing, archived, or out-of-scope employee.
- `409`: duplicate `employee_code` or `official_email`.

## Session security

- Session cookies are `HttpOnly` and `SameSite=Lax`.
- `Secure` is enabled only when `FLASK_ENV=production`.
- Login uses a permanent session with an 8-hour lifetime (`PERMANENT_SESSION_LIFETIME`).
- Non-permanent sessions still expire when the browser closes.
- Production startup refuses to run with the default development `FLASK_SECRET_KEY`.
  Set `FLASK_SECRET_KEY` to a unique value before deploying.

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

Using `404` for out-of-scope records prevents an authorized-looking caller from
enumerating records they may not see.

### Permission matrix

| Role | Employee records | Salary | Technical admin | Other |
|---|---|---|---|---|
| `CEO` | Organization-wide read-only | No | No | Org read, JML read, project read, reports |
| `HR Admin` | All employees; create, update, archive, JML | **No** unless also `Payroll Admin` | No | Org read, project read, reports |
| `HR Executive` | Self only until assigned scope is implemented | No | No | Limited HR update, org read, JML read |
| `Department Manager` | Full reporting subtree; limited team updates | No | No | Org read, JML read, project read |
| `Project Manager` | No employee record scope in this phase | No | No | Project read/manage; project scoping deferred |
| `Employee` | Own linked record and self-service updates | No | No | Org read |
| `System Admin` | **None** | **No** | Users, roles, audit read | No business data |
| `Payroll Admin` | None | **Salary read/manage** | No | Explicit grant only; never auto-assigned |

The browser UI exposes employee controls only for CEO, HR Admin, HR Executive,
Department Manager, and Employee. Project Manager, System Admin, and Payroll
Admin can sign in and see the dashboard, but have no employee records or
employee controls in this phase. Some backend permissions shown above have no
implemented API or screen yet.

Salary access is granted only by assigning the `Payroll Admin` role. No seeded
demo account receives it automatically. `users.employee_id` links a login to a
single employee record so self and team scope can be resolved; demo accounts
are left unlinked because the seed data has no explicit mapping.

The employee CRUD endpoints implement the explicit `EMPLOYEE_PUBLIC_FIELDS`
allowlist. `date_of_birth`, `emergency_contact`, `exit_reason`, and salary fields
are neither accepted in request bodies nor returned in responses, and queries do
not use `SELECT *`.

For testing, a blueprint is registered only inside the pytest fixture. It uses
the real decorators to verify permissions and record scope. It is never
registered by `create_app()`. The production employee API is the only business
API added in this phase; no salary API was added.
Project Manager project scoping is deferred; no `projects.manager_id` column or
project-scope logic exists yet.

## Future security work (not implemented in this phase)

- Rate limiting and account lockout for login attempts.
- CSRF protection for session-authenticated state-changing requests.
- Audit-log entries for login, logout, and failed authentication attempts.
- Input length limits for authentication fields.
- Project Manager database scope and assigned-department scope for HR Executive.

## Planned areas

Employee CRUD and its browser screens are documented above. There is no separate
dashboard endpoint; the dashboard derives its counts from `GET /api/employees`.
Organization, JML, projects, skills, salary, reports, and audit areas will be
documented here as their routes are added. New routes must use the authorization
decorators described above; do not expose real employee data through an
unprotected endpoint.

See [architecture.md](architecture.md).
