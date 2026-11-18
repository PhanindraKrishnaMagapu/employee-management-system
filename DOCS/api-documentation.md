# API documentation

Status: health and authentication endpoints, the RBAC foundation, and the additive
database migration are implemented. Business endpoints are still planned.

## Conventions

- Base URL on your machine: `http://127.0.0.1:5000`
- The frontend reads that address from `UI/js/api.js` (`API_BASE_URL`).
- All API responses are JSON with `Content-Type: application/json`.
- HTML stays in `UI/`. Flask does not render the product pages.
- Routes are Flask blueprints under `BACKEND/app/routes/`, registered from `BACKEND/app/__init__.py`.

## Response format

Every response has a top-level `success` boolean. Failures also include `message`.
Successful responses that return a resource include that resource in a `user` key.

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

Salary access is granted only by assigning the `Payroll Admin` role. No seeded
demo account receives it automatically. `users.employee_id` links a login to a
single employee record so self and team scope can be resolved; demo accounts
are left unlinked because the seed data has no explicit mapping.

General employee responses must use an explicit field allowlist. `date_of_birth`,
`emergency_contact`, `exit_reason`, and salary fields must never appear in
general employee responses, and sensitive queries must not use `SELECT *`.

For testing, a blueprint is registered only inside the pytest fixture. It uses
the real decorators to verify permissions and record scope. It is never
registered by `create_app()`, and no employee or salary business API was added.
Project Manager project scoping is deferred; no `projects.manager_id` column or
project-scope logic exists yet.

## Future security work (not implemented in this phase)

- Rate limiting and account lockout for login attempts.
- CSRF protection for session-authenticated state-changing requests.
- Audit-log entries for login, logout, and failed authentication attempts.
- Input length limits for authentication fields.
- Project Manager database scope and assigned-department scope for HR Executive.

## Planned areas

Employee, organization, JML, projects, skills, salary, dashboard, reports, and audit
areas will be documented here as their routes are added. New routes must use the
authorization decorators described above; do not expose real employee data through
an unprotected endpoint.

See [architecture.md](architecture.md).
