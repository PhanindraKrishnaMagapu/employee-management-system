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
index.html                     sign-in page
pages/dashboard.html           dashboard cards and quick actions
pages/employees.html           employee list and search
pages/employee-form.html       shared add/edit employee form
pages/hierarchy.html           reporting tree
pages/jml.html                 JML event list
pages/jml-form.html            create JML event
pages/jml-detail.html          JML checklist, status, and Mover history
pages/projects.html            project list and search
pages/project-form.html        shared add/edit project form
pages/project-detail.html      project summary and assignments
pages/skills.html              skill catalog list
pages/skill-form.html          shared add/edit skill form
pages/employee-skills.html     employee skill assignments
pages/salaries.html            salary list, search, filters, pagination
pages/salary-form.html         shared add/edit salary form
pages/employee-salaries.html   employee salary history
css/styles.css                 shared responsive styles
js/api.js                      fetch wrapper for relative API paths
js/auth.js                     login/logout, current-user checks, role gating
js/ui.js                       sidebar, messages, flash messages, redirects
js/pages/login.js              sign-in behavior
js/pages/dashboard.js          dashboard data loading
js/pages/employees.js          employee list, search, and archive behavior
js/pages/employee-form.js      employee add/edit behavior
js/pages/hierarchy.js          reporting tree built from the employee list
js/pages/jml.js                JML event list behavior
js/pages/jml-form.js           JML create behavior
js/pages/jml-detail.js         checklist, status, and history behavior
js/pages/projects.js           project list behavior
js/pages/project-form.js       project add/edit behavior
js/pages/project-detail.js     project assignment behavior
js/pages/skills.js             skill catalog behavior
js/pages/skill-form.js         skill add/edit behavior
js/pages/employee-skills.js    employee skill assignment behavior
js/pages/salaries.js           salary list, filters, and pagination
js/pages/salary-form.js        salary add/edit behavior
js/pages/employee-salaries.js  employee salary history behavior
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
| Hierarchy | `GET /api/employees`; builds the reporting tree in the browser from the scoped employee list. |
| JML event list | `GET /api/jml/events`; shows event type, employee, effective date, status, and checklist progress. |
| Create JML event | `POST /api/jml/events`; manager-only form with a default checklist. |
| JML detail | `GET /api/jml/events/<id>` plus checklist `PATCH` and status `PATCH`; shows Mover history. |
| Project list | `GET /api/projects`; shows scoped projects and assignment counts. |
| Project form | `GET /api/projects/<id>`, `POST /api/projects`, and `PUT /api/projects/<id>`; only HR Admin can choose a different project manager. |
| Project detail | `GET /api/projects/<id>`, `GET /api/projects/assignable-employees`, `POST /api/projects/<id>/assignments`, and assignment `DELETE`. |
| Skill catalog | `GET/POST /api/skills` and `PUT /api/skills/<skill_id>`; search filters the loaded list. |
| Employee skills | `GET/POST /api/employees/<employee_id>/skills` and assignment `PUT/DELETE`; fields depend on role. |
| Salaries | `GET /api/salaries` and `GET /api/salaries/employees`; server-side search, employee/currency/active-date filters, and pagination. |
| Add/edit salary | `POST /api/salaries` or `PUT /api/salaries/<id>`; the employee is immutable on edit. No delete action. |
| Employee salary history | `GET /api/salaries?employee_id=<id>`; shows Current, Scheduled, and Historical periods. |
| Logout | `POST /api/auth/logout`; clears cached user details and returns to sign-in. |

Success and error messages use the shared banner in `js/ui.js`. Cross-page
success messages use `sessionStorage`. A `401` response redirects to sign-in;
`403`, `404`, `409`, and `429` responses display the API message.

## Authentication and RBAC

`js/auth.js` calls `GET /api/auth/me` on protected pages and keeps only
non-sensitive user details in `sessionStorage`. The authentication cookie is an
`HttpOnly` Flask session cookie. Login clears the prior session and stores only
the user ID in the cookie-backed session; roles are reloaded by the backend on
each API request. Failed logins are throttled at five attempts per username and
client IP within 300 seconds. The throttle is process-local. Outside recognized
development environments, Flask requires a non-default `FLASK_SECRET_KEY` and
sets the cookie's `Secure` flag; production use therefore requires HTTPS.

The role map in `js/auth.js` mirrors backend capabilities so controls can be
hidden early:

- CEO: organization-wide read-only, plus JML, project, and skills read.
- HR Admin: read all, add, full edit, archive, JML manage, project manage, and
  skills manage.
- HR Executive and Department Manager: scoped read plus limited `phone` and
  `location` editing; JML and skills read.
- Employee: own linked record, `phone` self-update, and skills read.
- Project Manager: project read/manage only for projects owned by their linked
  employee record, plus the project employee picker; no general employee records.
- System Admin: no business data screens in this phase.
- Payroll Admin: salary read/manage and the salary employee picker; no general
  employee records.

Salary screens use `/api/salaries` and `/api/salaries/employees`, never
`/api/employees`. This lets Payroll Admin work without the general employee
permission. Salary amounts stay in page memory only; they are never written to
`sessionStorage`, `localStorage`, URLs, or flash messages. The API marks salary
responses `Cache-Control: no-store`.

This map is not a security boundary. The backend loads roles on each request,
enforces permissions, resolves record scope, and denies unknown or undecorated
`/api/*` routes. Department Managers see their full reporting subtree; Employee
and HR Executive see only their linked record. Out-of-scope records return
`404`.

Project ownership is stored in `projects.manager_id` (migration 002). HR Admin
can manage projects across the organization; a Project Manager is restricted to
projects owned by their linked employee record. A combined Project Manager and
HR Admin account receives the HR Admin project scope. JML status transitions,
checklist completion requirements, deferred Mover updates, and Leaver account
deactivation are enforced by the backend; see `DOCS/user-guide.md` for the
workflow.

## Current limitations

- Search is client-side over the records returned for the current user, except
  salary search, which is handled by the API.
- Department, designation, and manager are numeric ID inputs; no lookup screens
  exist yet.
- Auth responses do not include an employee ID, so the UI cannot identify the
  signed-in user's own record directly. The backend still blocks out-of-scope
  access.
- Salary records cannot be deleted; correct or close them by editing
  `effective_to`.
- Salary screens do not generate payslips, calculate tax, process bank
  transfers, or export data.
- Organization administration, reports, audit, users, and roles screens are not
  implemented yet.
