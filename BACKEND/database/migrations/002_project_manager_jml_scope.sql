-- Employee Management System
-- 002: Project manager ownership and deferred JML Mover changes
--
-- Apply with:  python -m app.db migrate   (from the BACKEND folder)
-- Do not execute this file directly: the runner skips ADD COLUMN statements
-- whose columns already exist and records the completed migration.
--
-- Additive only: no table, column, index or row is dropped or rewritten.

ALTER TABLE projects ADD COLUMN manager_id INTEGER REFERENCES employees(id);

CREATE INDEX IF NOT EXISTS idx_projects_manager ON projects(manager_id);

ALTER TABLE jml_events ADD COLUMN pending_changes TEXT;
