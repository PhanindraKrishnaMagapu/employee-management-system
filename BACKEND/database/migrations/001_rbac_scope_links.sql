-- Employee Management System
-- 001: Additive RBAC scope links
--
-- Apply with:  python -m app.db migrate   (from the BACKEND folder)
-- Do not execute this file directly: the runner decides whether each ALTER
-- TABLE statement is needed and records the completed migration.
--
-- This migration only adds a nullable column, a unique index and one role.
-- It never drops, recreates or deletes existing tables or data.

ALTER TABLE users ADD COLUMN employee_id INTEGER REFERENCES employees(id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id);

INSERT OR IGNORE INTO roles (name, description)
VALUES ('Payroll Admin', 'Explicit salary access grant');
