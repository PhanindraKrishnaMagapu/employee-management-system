# Employee Management System - UI

## Overview

This folder contains the browser interface for the Employee Management System.
It uses plain HTML, CSS, and JavaScript. There is no build step and no Node.js
runtime in the project.

## Serving the UI

Flask serves both this UI and the API from the same origin. From `BACKEND/`,
run `python run.py`, then open <http://127.0.0.1:5000/>. Do not open
`UI/index.html` with a `file://` URL; page routes and relative API URLs require
the Flask server.

`BACKEND/app/routes/ui.py` maps:

| Browser URL | Source |
|---|---|
| `/` | `UI/index.html` |
| `/pages/<filename>` | `UI/pages/<filename>` |
| `/css/<filename>` | `UI/css/<filename>` |
| `/js/<filename>` | `UI/js/<filename>` |

Only `.html`, `.css`, and `.js` files are served. These routes contain no
business logic.

`js/api.js` uses an empty `API_BASE_URL`, relative `/api/...` paths, and
`credentials: "same-origin"`. The Flask session cookie is therefore sent with
each request without CORS or a proxy. See `DOCS/api-documentation.md` for the
endpoint contract.

## Current layout

```text
index.html                  sign-in page
pages/dashboard.html        dashboard cards and quick actions
pages/employees.html        employee list and search
pages/employee-form.html    shared add/edit form
css/styles.css              shared responsive styles
js/api.js                   fetch wrapper for relative API paths
js/auth.js                  login/logout, current-user checks, role gating
js/ui.js                    sidebar, messages, flash messages, redirect handling
js/pages/login.js           sign-in behavior
js/pages/dashboard.js       dashboard data loading
js/pages/employees.js       list, search, and archive behavior
js/pages/employee-form.js   add/edit behavior
```

## Implemented screens

| Screen | Behavior |
|---|---|
| Login | `POST /api/auth/login`; redirects to the dashboard on success. |
| Dashboard | Calls `GET /api/employees` and shows total/active counts for the user's scope. |
| Employee list | Calls `GET /api/employees` and renders code, name, email, phone, and status. |
| Search | Filters loaded records by employee name, email, or employee code in the browser. |
| Add employee | `POST /api/employees`; available only to roles with create permission. |
| Edit employee | `GET /api/employees/<id>` prefill plus `PUT /api/employees/<id>`; fields depend on role. |
| Archive employee | `DELETE /api/employees/<id>` after confirmation; soft archive, not permanent deletion. |
| Logout | `POST /api/auth/logout`; clears cached user details and returns to sign-in. |

Success and error messages use the shared banner in `js/ui.js`. Cross-page
success messages use `sessionStorage`. A `401` response redirects to sign-in;
`403`, `404`, and `409` responses display the API message.

## Authentication and RBAC

`js/auth.js` calls `GET /api/auth/me` on protected pages and keeps only
non-sensitive user details in `sessionStorage`. The authentication cookie is an
`HttpOnly` Flask session cookie.

The role map in `js/auth.js` mirrors backend capabilities so controls can be
hidden early:

- CEO: organization-wide read-only.
- HR Admin: read all, add, full edit, and archive.
- HR Executive and Department Manager: scoped read plus limited `phone` and
  `location` editing.
- Employee: own linked record plus `phone` self-update.
- Project Manager, System Admin, and Payroll Admin: no employee screens in this
  phase.

This map is not a security boundary. The backend loads roles on each request,
enforces permissions, resolves record scope, and denies unknown or undecorated
`/api/*` routes. Department Managers see their full reporting subtree; Employee
and HR Executive see only their linked record. Out-of-scope records return
`404`.

## Current limitations

- Search is client-side over the records returned for the current user.
- Department, designation, and manager are numeric ID inputs; no lookup screens
  exist yet.
- Auth responses do not include an employee ID, so the UI cannot identify the
  signed-in user's own record directly. The backend still blocks out-of-scope
  access.
- Salary, organization tree, departments/designations, JML, projects, skills,
  reports, audit, users, and roles screens are not implemented yet.
