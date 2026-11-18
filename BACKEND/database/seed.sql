
-- Employee Management System
-- Phase 2: Fake development seed data
-- No real employee information or usable passwords.

-- 1. Roles
INSERT OR IGNORE INTO roles (id, name, description) VALUES
(1, 'CEO', 'Chief Executive Officer'),
(2, 'HR Admin', 'Human Resources Administrator'),
(3, 'HR Executive', 'Human Resources Executive'),
(4, 'Department Manager', 'Department Manager'),
(5, 'Project Manager', 'Project Manager'),
(6, 'Employee', 'Standard Employee'),
(7, 'System Admin', 'System Administrator'),
(8, 'Payroll Admin', 'Explicit salary access grant');

-- 2. Departments
INSERT OR IGNORE INTO departments (id, name, description) VALUES
(1, 'Human Resources', 'HR Department'),
(2, 'Information Technology', 'IT Department'),
(3, 'Finance', 'Finance Department');

-- 3. Designations
INSERT OR IGNORE INTO designations (id, title, description) VALUES
(1, 'Chief Executive Officer', 'Company leadership'),
(2, 'HR Manager', 'Human Resources management'),
(3, 'Software Developer', 'Software development'),
(4, 'Project Manager', 'Project management'),
(5, 'Accountant', 'Finance and accounting');

-- 4. Users
-- Password hashes are deliberately unusable placeholders.
-- The development password tool replaces those placeholders; see setup-guide.md.
--
-- employee_id is left NULL for every demo account. The existing seed data has
-- no explicit user-to-employee relationship; matching by name, email or job
-- title would be a guess, so those mappings must be assigned deliberately.
INSERT OR IGNORE INTO users (id, username, email, password_hash, employee_id) VALUES
(1, 'demo_ceo', 'ceo@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL),
(2, 'demo_hr_admin', 'hradmin@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL),
(3, 'demo_hr_exec', 'hrexecutive@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL),
(4, 'demo_dept_manager', 'manager@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL),
(5, 'demo_project_manager', 'projectmanager@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL),
(6, 'demo_employee', 'employee@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL),
(7, 'demo_sysadmin', 'sysadmin@example.invalid', 'NOT_A_REAL_PASSWORD_HASH', NULL);

-- 5. Employees
-- All names, emails and contact details are fictional.
INSERT OR IGNORE INTO employees
(id, employee_code, first_name, last_name, official_email,
 phone, joining_date, employment_type, employment_status,
 location, department_id, designation_id, manager_id)
VALUES
(1, 'DEMO001', 'Alex', 'Morgan', 'alex.morgan@example.invalid',
 '9000000001', '2025-01-10', 'Full-time', 'Active',
 'Hyderabad', 2, 1, NULL),

(2, 'DEMO002', 'Taylor', 'Sharma', 'taylor.sharma@example.invalid',
 '9000000002', '2025-02-01', 'Full-time', 'Active',
 'Hyderabad', 1, 2, 1),

(3, 'DEMO003', 'Jordan', 'Reddy', 'jordan.reddy@example.invalid',
 '9000000003', '2025-03-01', 'Full-time', 'Active',
 'Hyderabad', 1, 2, 2),

(4, 'DEMO004', 'Casey', 'Kumar', 'casey.kumar@example.invalid',
 '9000000004', '2025-04-01', 'Full-time', 'Active',
 'Hyderabad', 2, 3, 1),

(5, 'DEMO005', 'Riley', 'Patel', 'riley.patel@example.invalid',
 '9000000005', '2025-05-01', 'Full-time', 'Active',
 'Hyderabad', 2, 4, 4),

(6, 'DEMO006', 'Avery', 'Rao', 'avery.rao@example.invalid',
 '9000000006', '2025-06-01', 'Full-time', 'Pre-joining',
 'Hyderabad', 3, 5, 1),

(7, 'DEMO007', 'Jamie', 'Das', 'jamie.das@example.invalid',
 '9000000007', '2025-07-01', 'Full-time', 'Active',
 'Hyderabad', 2, 3, 4);

-- 6. User-role mappings
INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES
(1, 1),
(2, 2),
(3, 3),
(4, 4),
(5, 5),
(6, 6),
(7, 7);
