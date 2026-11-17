# Master Statement of Work (MASTER_SOW)
## Employee Management System

**Project name:** Employee Management System (EMS)  
**Document:** Master Statement of Work  
**Version:** 1.0  
**Status:** Initial project scope  
**Repository layout:** `UI/`, `BACKEND/`, `DOCS/`, `MASTER_SOW.md`

---

## 1. Project overview

Build a web-based Employee Management System (EMS) that allows an organization to manage its employees, organizational hierarchy, joiner-mover-leaver (JML) lifecycle, projects, salaries, skills, and reporting relationships.

The application must support role-based access so users can see and manage only the information permitted for their role.

## 2. Business objectives

1. Maintain a centralized employee database.
2. Manage employee onboarding, transfers/promotions, and exits (JML).
3. Maintain departments, designations, managers, and reporting hierarchy.
4. Assign employees to projects and track project roles.
5. Maintain employee skills and experience.
6. Maintain salary records with restricted access.
7. Provide HR, manager, and leadership dashboards and reports.
8. Keep an audit trail of important changes.

## 3. Scope and modules

### 3.1 Employee management (CRUD)

Implement Create, Read, Update, and Delete/archive operations for employee records.

Suggested employee fields:
- Employee ID (unique)
- First name, last name, and profile photo
- Official email and phone number
- Date of birth (collect only if required by company policy)
- Date of joining and employment status
- Department, designation, location, and employment type
- Reporting manager
- Work experience and employee skills
- Emergency contact (restricted access)

**Rules**
- Employee ID and official email must be unique.
- Prefer deactivation/archiving over permanent deletion.
- Record who created or updated a record and when.
- Validate required fields and email formats.

### 3.2 JML lifecycle

**Joiner**
- HR creates a pre-joining or new employee record.
- Assign employee ID, department, designation, location, and manager.
- Record joining date and onboarding status.
- Track onboarding checklist items and completion.

**Mover**
- HR-authorized users update department, designation, manager, location, or project assignment.
- Keep effective dates and previous values in the history.
- Where applicable, record promotion or transfer approval.

**Leaver**
- HR records resignation/termination date and reason with restricted access.
- Track exit checklist, asset return, and access-removal confirmation.
- Change the employee status to `Exited` after the approved exit process.
- Preserve historical employee, project, and payroll records according to company retention policy.

### 3.3 Organization and reporting hierarchy

Support a configurable organization tree. A typical example is:

```text
CEO
└── Department Head / Director
    ├── HR Manager
    │   └── HR Executive
    ├── Engineering Manager
    │   ├── Team Lead
    │   │   ├── Employee
    │   │   └── Employee
    │   └── Team Lead
    │       └── Employee
    └── Project / Delivery Manager
        ├── Project Lead
        │   └── Project Team Members
        └── Project Lead
            └── Project Team Members
```

The actual hierarchy must be configurable. Do not assume every company has the same titles or number of management levels.

**Hierarchy requirements**
- Each employee may have one primary reporting manager at a time.
- The CEO/top-level role has no reporting manager.
- Prevent an employee from being assigned as their own manager.
- Prevent circular reporting relationships.
- Show the hierarchy as an expandable tree.
- Enforce permissions independently of the visual hierarchy.

### 3.4 Department and designation management

- Create, view, update, and archive departments.
- Create and update designations/job titles.
- Assign department heads and managers.
- Maintain department-to-employee relationships.

### 3.5 Project management

- Create and maintain projects.
- Store project name, code, description, client (if applicable), start/end dates, status, and project manager.
- Assign employees to projects with project roles and allocation dates.
- Track active, completed, and on-hold projects.
- Keep assignment history when employees move between projects.

### 3.6 Salary and payroll records

Salary data is confidential and must be restricted to authorized HR/payroll users and explicitly authorized leadership.

Suggested fields:
- Employee ID
- Effective date
- Salary structure / components
- Gross salary and applicable deductions
- Net salary
- Payment frequency and status

**Important:** This module is for maintaining salary records and reports. Actual bank transfers, tax calculations, statutory payroll compliance, and payslip generation are out of scope unless separately approved.

### 3.7 Skills management

- Maintain a reusable skills catalogue.
- Add multiple skills to each employee.
- Record proficiency level (for example: Beginner, Intermediate, Advanced, Expert).
- Record years/months of experience and last-verified date where appropriate.
- Search employees by skill and proficiency.

### 3.8 User accounts, roles, and permissions

Initial roles:
- **CEO:** organization-level read-only dashboard and approved reports.
- **HR Admin / HR Manager:** employee lifecycle and organization data administration; salary access only if explicitly granted.
- **HR Executive:** assigned HR operations with limited permissions.
- **Department Manager:** view their reporting organization and manage permitted team information.
- **Project Manager:** manage assigned projects and project team assignments.
- **Employee:** view their own profile and permitted self-service information.
- **System Admin:** technical configuration and user/role administration; business-data access should be limited and audited.

Use role-based access control (RBAC), and where needed, scope access by department, reporting line, or assigned project. Do not expose salary, personal, or exit information to ordinary employees or unauthorized managers.

## 4. Main application screens

### UI
1. Login and password reset
2. Dashboard
3. Employee directory and employee profile
4. Add/edit employee
5. Organization hierarchy tree
6. JML workflow and checklist
7. Departments and designations
8. Projects and project assignments
9. Skills catalogue and employee skills
10. Salary records (authorized roles only)
11. Reports and audit history
12. User and role administration

The UI should be responsive, accessible, and include clear loading, empty, validation, and error states.

## 5. Suggested technical architecture

The exact stack should be confirmed before implementation. Keep UI and backend separate.

- **UI:** web frontend (for example, React).
- **BACKEND:** REST API (for example, Node.js with Express, or another team-approved framework).
- **DATABASE:** relational database (for example, PostgreSQL or MySQL). Database migrations and seed data must be version-controlled under `BACKEND/` or documented in `DOCS/`.
- **Authentication:** secure session or token-based authentication, password hashing, and role-based authorization.
- **API documentation:** OpenAPI/Swagger or equivalent.
- **Testing:** unit, API/integration, and UI tests.

Do not commit passwords, API keys, database credentials, private certificates, or production employee data. Use `.env.example` with placeholder values and keep real `.env` files out of Git.

## 6. Repository structure

Use this structure in the GitHub repository:

```text
employee-management-system/
├── UI/
│   ├── README.md
│   └── (frontend source code)
├── BACKEND/
│   ├── README.md
│   └── (API source, database migrations, tests)
├── DOCS/
│   ├── architecture.md
│   ├── database-design.md
│   ├── api-documentation.md
│   ├── setup-guide.md
│   └── user-guide.md
├── MASTER_SOW.md
├── .gitignore
└── README.md
```

`DATABASE` is a logical system component, not necessarily a separate top-level repository folder. Store schema, migrations, and seed scripts in the backend, and explain the database design in `DOCS/database-design.md`. If the team explicitly wants a separate `DATABASE/` folder, agree that before creating it.

## 7. GitHub branching strategy

- `main`: stable, reviewed code only.
- Create feature branches from the latest `main`.
- Suggested branch names:
  - `feature/ui-login`
  - `feature/employee-crud`
  - `feature/jml-workflow`
  - `feature/org-hierarchy`
  - `feature/project-management`
  - `feature/salary-module`
  - `feature/skills-module`
  - `feature/rbac`
  - `bugfix/<short-description>`
  - `docs/<short-description>`

**Workflow**
1. Pull the latest `main`.
2. Create a new branch from `main`.
3. Make changes only for the assigned task.
4. Run tests and review the changes.
5. Push the branch to GitHub.
6. Open a Pull Request into `main`.
7. Obtain review/approval and resolve conflicts.
8. Merge only after checks pass.

Do not commit directly to `main` unless the repository owner explicitly permits it. Protect `main` with pull-request review and status checks where available.

## 8. Non-functional requirements

- Security: authentication, authorization, input validation, secure password storage, and protection against common web vulnerabilities.
- Privacy: least-privilege access to personal, salary, and exit data.
- Auditability: log important create/update/archive actions and role/permission changes.
- Reliability: handle API/database failures without corrupting records.
- Performance: paginate and search large employee/project lists.
- Maintainability: modular code, consistent naming, documentation, and automated tests.
- Backup and recovery: define database backup and restore procedures before production use.

## 9. Acceptance criteria

The initial release is acceptable when:
1. Authorized users can create, view, update, and archive employee records.
2. Duplicate employee IDs and official emails are rejected.
3. HR can record Joiner, Mover, and Leaver events with dates and history.
4. The organization hierarchy displays correct reporting relationships and blocks circular relationships.
5. Authorized users can create projects and assign employees.
6. Employees can have multiple skills and proficiency levels.
7. Salary information is inaccessible to unauthorized roles and access is tested.
8. Role permissions are enforced by the backend API, not only hidden in the UI.
9. Important changes are auditable.
10. Setup instructions, database schema/migrations, API documentation, and tests are provided.

## 10. Delivery phases

| Phase | Deliverables |
|---|---|
| 1. Planning | Confirm requirements, roles, workflows, and technology stack |
| 2. Foundation | Repository, UI/backend skeleton, database schema, authentication |
| 3. Core HR | Employee CRUD, departments, designations, organization tree |
| 4. Lifecycle | Joiner, Mover, Leaver workflows and history |
| 5. Operations | Projects, assignments, skills |
| 6. Confidential data | Salary records and restricted reports |
| 7. Quality | Testing, security review, audit logs, bug fixes |
| 8. Release | Documentation, deployment, handover |

## 11. Assumptions and decisions to confirm

Before implementation, the project owner must confirm:
- Final UI, backend, and database technologies.
- Whether the system is for one company or multiple companies.
- Exact job titles and organization levels.
- Which roles can view or edit salary information.
- Whether approval workflows are required for JML and salary changes.
- Payroll, attendance, leave, recruitment, and performance-management scope.
- Hosting, backup, retention, and deployment requirements.

## 12. Out of scope unless separately approved

- Full payroll processing and bank payment integration.
- Attendance devices and biometric integration.
- Leave management.
- Recruitment and applicant tracking.
- Performance appraisal.
- Email/SMS/WhatsApp integrations.
- Single sign-on and external HRMS integrations.

---

**Document owner:** Project team  
**Approval:** To be confirmed by the organization  
**Note:** This is an initial scope document. Confirm business rules, privacy requirements, and technical choices with the office/project owner before using real employee data.
