# User guide

Status: login, dashboard, employee list/search, add, edit, soft archive, hierarchy, JML, projects, skills, employee skills, salary, and role-based access are implemented in the browser UI.

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

After five failed attempts for the same username from the same client within
300 seconds, sign-in is temporarily blocked and the page reports
"Too many login attempts. Please try again later." The block clears when the
window expires or after a successful login.

## Dashboard

The dashboard shows:

- **Total employees** – the number of active records returned by `GET /api/employees`.
- **Active employees** – the subset of those records with status `Active`.
- **Your access** – organization-wide access or assigned scope.
- Quick links to the employee list, hierarchy, skills, projects, JML, and salary
  screens available to the role, plus the add form where permitted.

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
`404` rather than revealing that it exists. A manager change that would create
a direct or indirect reporting cycle is rejected with `400`.

## Archive an employee

Use **Archive** in the employee list and confirm the prompt. The browser calls
`DELETE /api/employees/<id>`. This is a soft archive: the employee is marked
with `archived_at`, is hidden from lists and read endpoints, and related records
are not deleted. Only HR Admin has the archive action.

## Reporting hierarchy

Open **Hierarchy** to see the reporting tree built from the employee records
visible to your role. There is no separate hierarchy API; the page uses
`GET /api/employees` and arranges the results by each record's manager ID.
Employees whose manager is outside your scope appear as top-level entries.

## JML events

Open **JML** to view Joiner, Mover, and Leaver events for employees in your
scope. The list shows the employee, event type, effective date, status, and
checklist progress. HR Admin can select **Create JML event**; other roles have
read-only access.

The event form requires an employee, event type (`Joiner`, `Mover`, or
`Leaver`), and an effective date. A Leaver requires a reason. A Mover requires
a `changes` object with any of department ID, designation ID, manager ID, and
location; those changes are saved on the event and are not applied until the
event is completed.

The detail screen shows the checklist and, for HR Admin, buttons to mark items
complete/pending and a status selector. Status moves from **Pending** to
**In Progress**, **Completed**, or **Cancelled**, and from **In Progress** to
**Completed** or **Cancelled**. Completed and Cancelled are final. Completion
requires every checklist item to be completed; for a Leaver, the
**Access removal confirmed** item must also be completed. On completion:

- A Joiner sets the employee status to `Active`.
- A Mover applies the stored changes and records the old and new values in
  employee history; cancelling a Mover leaves the employee unchanged.
- A Leaver sets the employee status to `Exited` and deactivates user accounts
  linked to that employee.

The detail screen also shows the Mover's organization history after completion.

## Projects and assignments

Open **Projects** to see the projects visible to your role. HR Admin sees and
manages all projects. A Project Manager sees and manages only projects whose
manager is their linked employee record; CEO and Department Manager have
read-only project access. Out-of-scope projects are reported as missing.

HR Admin and Project Manager can create and edit projects from the project form.
A Project Manager's own employee ID is stored as the project manager; only HR
Admin can assign a different manager. The form accepts a project code, name,
description, status (`Planned`, `In Progress`, `Completed`, or `On Hold`), start
and end dates, and, for HR Admin, a manager ID.

The project detail screen lists assignments with allocation percentages.
Managers can assign an active employee from the project employee picker and
remove assignments. The Project Manager employee picker is the only place that
role sees employee records; the general employee and hierarchy screens remain
closed to it.
When a user has both Project Manager and HR Admin roles, the HR Admin grant
provides organization-wide project scope. Other roles combine additively for
endpoint permissions, while the project scope rule gives HR Admin its explicit
organization-wide behavior.

## Skills and employee skills

Open **Skills** to view the shared skill catalog. HR Admin can add and edit
skills by name and description; other roles have read-only access. Search
filters the loaded list by skill name or description.

On the employee list, the **Skills** action (where permitted) opens the
employee-skill screen. It shows skill assignments with proficiency level,
experience years, and last-verified date. Skill managers can assign a skill to
an active employee, update those three fields, and remove an assignment. The
employee and skill must be in scope, and duplicate assignments are rejected.

## Salaries

Open **Salaries** from the sidebar. The page loads `GET /api/salaries` and shows
salary periods visible to the current role. Payroll Admin sees organization-wide
salary records; other roles receive a permission error unless they also have the
Payroll Admin role. Salary pages use `/api/salaries` and
`/api/salaries/employees`, never the general employee API.

The list supports server-side search by employee code or name, an employee
filter, a currency filter, an active-on date, and pagination. Each row links to
the employee's salary history and, for salary managers, an edit form.

Select **Add salary** to create a period. Choose an employee, enter the annual
salary, a three-letter currency code (`INR` by default), the effective-from date,
and an optional effective-to date. `POST /api/salaries` validates the request and
rejects overlapping periods. Creating a later period automatically closes an
earlier open-ended period the day before the new start date.

Use **Edit** to correct a period. The employee cannot be changed; only the
amount, currency, and effective dates can be updated with
`PUT /api/salaries/<id>`. There is no delete action. To end a period, set its
effective-to date.

Salary history shows every period for one employee with a Current, Scheduled, or
Historical status. Archived employees keep readable salary history: new records
are rejected, but existing records can still be corrected or closed from the
history screen. The employee cannot be changed, and the same date and overlap
validation applies. Salary responses are marked `Cache-Control: no-store`, and
amounts are kept in page memory rather than browser storage or URLs.

Every successful salary creation or correction is recorded in the existing
audit log. When a new period automatically closes an earlier open-ended period,
the closed record gets its own update entry in addition to the new record's
create entry. Audit entries contain only the actor, action, salary record id,
and employee id; salary amounts, currency, effective dates, bank details, and
tax information are never written to the audit log.

This module does not perform bank transfers, tax calculations, statutory
payroll, payslip generation, deductions, or salary-structure processing.

## Messages and errors

Success and error messages appear at the top of the page. A `401` response
returns the user to sign-in. A `403` response means the role lacks the endpoint
permission. A `404` response means the record is missing, archived, or outside
the role's scope; this also applies to out-of-scope projects, JML events, skill
assignments, and employees. A `409` response means a duplicate employee
code/email, a duplicate project assignment or skill assignment, a duplicate
skill name, or an overlapping salary period. A `429` on sign-in means the login
throttle is active. A `400` covers invalid fields, invalid JML transitions or
incomplete checklists, invalid references, and reporting cycles.

Restricted fields (`date_of_birth`, `emergency_contact`, `exit_reason`) and
salary fields are not shown or returned by the general employee API. Salary
values appear only on the salary screens for roles with salary access.

## Roles and current restrictions

| Role | Access in the UI |
|---|---|
| `CEO` | Organization-wide employee read-only; JML, project, and skills screens; no add, edit, or archive controls. |
| `HR Admin` | All employees; add, full edit, archive, JML manage, project manage, and skills manage. No salary screen unless also `Payroll Admin`. |
| `HR Executive` | Linked employee record only; limited `phone` and `location` edit; JML and skills read. No add or archive. |
| `Department Manager` | Full reporting subtree; limited `phone` and `location` edit; JML, project, and skills read. No add or archive. |
| `Employee` | Own linked record; `phone` self-update; skills read. No add or archive. |
| `Project Manager` | Project read/manage only for projects where they are the linked manager, plus the project employee picker; no general employee records. |
| `System Admin` | Sign-in and dashboard only; technical admin APIs have no UI here. No business data. |
| `Payroll Admin` | Salary read/manage and salary employee picker; no general employee records. |

Scope is resolved by the backend. HR Admin and CEO can read all employee records;
Department Managers see their full reporting subtree; Employee and HR Executive
see only their linked employee record. A user without a linked record has no
scoped employee access. Payroll Admin uses a separate organization-wide salary
scope and does not receive general employee access. HR Admin can manage all
projects; a Project Manager is limited to projects owned by their linked
employee record.

The UI hides controls early for a better experience, but hiding a control is not
a security mechanism. Every `/api/*` request is evaluated by Flask's
default-deny guard; the only public exceptions are `GET /api/health` and
`POST /api/auth/login`. Unknown or undecorated API routes are denied.

## Current limitations

- Search applies only to records already returned for the user's scope, except
  salary search, which is performed by the API.
- Department, designation, and manager are numeric ID inputs.
- The dashboard has no separate API; employee counts come from
  `GET /api/employees`. Payroll Admin sees salary access instead of counts.
- Auth responses do not include an employee ID, so the UI cannot precisely
  identify the signed-in user's own record; the backend still rejects all
  out-of-scope reads and updates.
- Salary records cannot be deleted. Correct or close them with an update.
- Salary processing is limited to record keeping: no tax, payslips, bank
  transfers, deductions, or exports.
- Organization administration, reports, audit, users, and roles screens are not
  implemented in this phase.
