# API documentation

Status: health and authentication endpoints are implemented. The remaining areas are planned.

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

Destroys the current session. It is idempotent and does not require a session.

- `200`: `{ "success": true, "message": "Logout successful" }`

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

## Future security work (not implemented in this phase)

- Rate limiting and account lockout for login attempts.
- CSRF protection for session-authenticated state-changing requests.
- Role-based access control (RBAC) decorators for protected endpoints.
- Audit-log entries for login, logout, and failed authentication attempts.
- Input length limits for authentication fields.

## Planned areas

Employee, organization, JML, projects, skills, salary, dashboard, reports, and audit
areas will be documented here as their routes are added. Until authorization exists,
do not put real employee data behind this API.

See [architecture.md](architecture.md).
