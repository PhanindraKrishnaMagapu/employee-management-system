"""Unit tests for RBAC permissions, employee scope and the safe migration.

Every fixture points the database at a temporary file; the local development
SQLite database is never opened here.
"""

import sqlite3

import pytest

from app.auth import permissions as perms
from app.auth.context import CurrentUser
from app.db import apply_migrations, get_connection
from app.services import authorization
from app.services.auth import hash_password


PASSWORD = "RbacUnit!234"


def _users():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, username, email, password_hash, is_active "
            "FROM users ORDER BY id"
        ).fetchall()
        return [tuple(row) for row in rows]
    finally:
        connection.close()


def _roles_for(username):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            JOIN users u ON u.id = ur.user_id
            WHERE u.username = ?
            ORDER BY r.name
            """,
            (username,),
        ).fetchall()
        return [row["name"] for row in rows]
    finally:
        connection.close()


def _seeded_roles():
    connection = get_connection()
    try:
        return {
            row["name"]
            for row in connection.execute("SELECT name FROM roles")
        }
    finally:
        connection.close()


def _user(roles, employee_id=None):
    return CurrentUser(
        id=1,
        username="test_user",
        email="test@example.invalid",
        employee_id=employee_id,
        roles=tuple(roles),
        permissions=perms.permissions_for_roles(roles),
    )


def _connection():
    return get_connection()


def _set_manager(employee_id, manager_id):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET manager_id = ? WHERE id = ?",
            (manager_id, employee_id),
        )
        connection.commit()
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Permission map
# ---------------------------------------------------------------------------

def test_every_seeded_role_has_an_intentional_mapping(isolated_db):
    seeded = _seeded_roles()

    assert seeded == set(perms.ROLE_PERMISSIONS)
    assert perms.ROLE_PAYROLL_ADMIN in seeded
    for role in seeded:
        assert isinstance(perms.ROLE_PERMISSIONS[role], frozenset)
        assert perms.ROLE_PERMISSIONS[role]


def test_unknown_role_receives_no_permissions():
    assert perms.permissions_for_roles(["Not A Role"]) == frozenset()
    assert perms.permissions_for_roles([None]) == frozenset()
    assert perms.has_permission("Not A Role", perms.PERMISSION_USER_MANAGE) is False


def test_system_admin_has_no_employee_or_salary_access():
    granted = perms.permissions_for_roles(perms.ROLE_SYSTEM_ADMIN)

    assert perms.PERMISSION_USER_MANAGE in granted
    assert perms.PERMISSION_ROLE_MANAGE in granted
    assert perms.PERMISSION_AUDIT_READ in granted
    assert not granted & {
        perms.PERMISSION_EMPLOYEE_READ_ALL,
        perms.PERMISSION_EMPLOYEE_READ_SCOPE,
        perms.PERMISSION_SALARY_READ,
        perms.PERMISSION_SALARY_MANAGE,
    }


def test_hr_admin_has_no_salary_without_payroll_admin():
    granted = perms.permissions_for_roles(perms.ROLE_HR_ADMIN)

    assert perms.PERMISSION_EMPLOYEE_CREATE in granted
    assert perms.PERMISSION_EMPLOYEE_ARCHIVE in granted
    assert perms.PERMISSION_SALARY_READ not in granted
    assert perms.PERMISSION_SALARY_MANAGE not in granted


def test_payroll_admin_receives_only_the_intended_salary_permissions():
    granted = perms.permissions_for_roles(perms.ROLE_PAYROLL_ADMIN)

    assert granted == frozenset({
        perms.PERMISSION_SALARY_READ,
        perms.PERMISSION_SALARY_MANAGE,
    })


def test_multiple_roles_combine_using_union():
    granted = perms.permissions_for_roles([
        perms.ROLE_HR_ADMIN,
        perms.ROLE_PAYROLL_ADMIN,
    ])

    assert perms.PERMISSION_EMPLOYEE_CREATE in granted
    assert perms.PERMISSION_SALARY_READ in granted
    assert perms.PERMISSION_USER_MANAGE not in granted
    assert granted == (
        perms.ROLE_PERMISSIONS[perms.ROLE_HR_ADMIN]
        | perms.ROLE_PERMISSIONS[perms.ROLE_PAYROLL_ADMIN]
    )


def test_has_any_and_has_all_helpers():
    roles = [perms.ROLE_SYSTEM_ADMIN, perms.ROLE_PAYROLL_ADMIN]

    assert perms.has_any_permission(
        roles, [perms.PERMISSION_USER_MANAGE, perms.PERMISSION_SALARY_READ]
    )
    assert perms.has_all_permissions(
        roles, [perms.PERMISSION_USER_MANAGE, perms.PERMISSION_SALARY_READ]
    )
    assert not perms.has_any_permission(roles, [perms.PERMISSION_EMPLOYEE_CREATE])
    assert not perms.has_all_permissions(
        perms.ROLE_SYSTEM_ADMIN,
        [perms.PERMISSION_USER_MANAGE, perms.PERMISSION_SALARY_READ],
    )


def test_demo_user_roles_are_unchanged_by_rbac_mapping(isolated_db):
    expected = {
        "demo_ceo": [perms.ROLE_CEO],
        "demo_hr_admin": [perms.ROLE_HR_ADMIN],
        "demo_hr_exec": [perms.ROLE_HR_EXECUTIVE],
        "demo_dept_manager": [perms.ROLE_DEPARTMENT_MANAGER],
        "demo_project_manager": [perms.ROLE_PROJECT_MANAGER],
        "demo_employee": [perms.ROLE_EMPLOYEE],
        "demo_sysadmin": [perms.ROLE_SYSTEM_ADMIN],
    }

    for username, roles in expected.items():
        assert _roles_for(username) == roles


# ---------------------------------------------------------------------------
# Employee record scope
# ---------------------------------------------------------------------------

def test_employee_scope_is_self_only(isolated_db):
    user = _user([perms.ROLE_EMPLOYEE], employee_id=7)
    connection = _connection()
    try:
        assert authorization.employee_scope(user, connection) == frozenset({7})
        assert authorization.can_access_employee(user, 7, connection)
        assert not authorization.can_access_employee(user, 6, connection)
    finally:
        connection.close()


def test_missing_employee_link_denies_self_and_team_access(isolated_db):
    for role in (perms.ROLE_EMPLOYEE, perms.ROLE_DEPARTMENT_MANAGER):
        user = _user([role], employee_id=None)
        connection = _connection()
        try:
            assert authorization.employee_scope(user, connection) == frozenset()
            assert not authorization.can_access_employee(user, 7, connection)
            assert not authorization.can_access_employee(user, 4, connection)
        finally:
            connection.close()


def test_department_manager_can_access_full_reporting_subtree(isolated_db):
    user = _user([perms.ROLE_DEPARTMENT_MANAGER], employee_id=4)
    connection = _connection()
    try:
        scope = authorization.employee_scope(user, connection)

        assert scope == frozenset({4, 5, 7})
        assert authorization.can_access_employee(user, 5, connection)
        assert authorization.can_access_employee(user, 7, connection)
        assert not authorization.can_access_employee(user, 3, connection)
        assert not authorization.can_access_employee(user, 1, connection)
    finally:
        connection.close()


def test_manager_cycle_cannot_cause_infinite_traversal(isolated_db):
    # Employee 5 reports to 4, so pointing 4 at 5 creates a cycle.
    _set_manager(4, 5)
    user = _user([perms.ROLE_DEPARTMENT_MANAGER], employee_id=4)
    connection = _connection()
    try:
        assert authorization.reporting_subtree(4, connection) == frozenset({4, 5, 7})
        assert authorization.can_access_employee(user, 7, connection)
        assert not authorization.can_access_employee(user, 3, connection)
    finally:
        connection.close()


def test_excessive_manager_depth_is_capped(isolated_db, monkeypatch):
    monkeypatch.setattr(authorization, "MAX_SUBTREE_DEPTH", 1)
    connection = _connection()
    try:
        assert authorization.reporting_subtree(1, connection) == frozenset({1, 2, 4, 6})
    finally:
        connection.close()


def test_org_wide_roles_do_not_require_an_employee_link(isolated_db):
    connection = _connection()
    try:
        for role in (perms.ROLE_HR_ADMIN, perms.ROLE_CEO):
            user = _user([role])
            assert authorization.employee_scope(user, connection) is None
            assert authorization.can_access_employee(user, 3, connection)
    finally:
        connection.close()


def test_project_manager_has_no_project_scope_helper(isolated_db):
    user = _user([perms.ROLE_PROJECT_MANAGER], employee_id=5)
    connection = _connection()
    try:
        assert not perms.has_permission(
            user.roles, perms.PERMISSION_EMPLOYEE_READ_SCOPE
        )
        assert authorization.employee_scope(user, connection) == frozenset({5})
    finally:
        connection.close()


def test_restricted_fields_are_not_in_the_public_allowlist():
    allowed = set(authorization.EMPLOYEE_PUBLIC_FIELDS)

    assert not allowed & authorization.RESTRICTED_EMPLOYEE_FIELDS
    assert not allowed & authorization.SALARY_FIELDS
    assert "date_of_birth" in authorization.RESTRICTED_EMPLOYEE_FIELDS
    assert "exit_reason" in authorization.RESTRICTED_EMPLOYEE_FIELDS


# ---------------------------------------------------------------------------
# Migration (temporary databases only)
# ---------------------------------------------------------------------------

def _make_legacy_database():
    """Downgrade a temp DB to the pre-RBAC shape and add a real hash."""

    connection = get_connection()
    try:
        connection.execute("DROP INDEX IF EXISTS idx_users_employee_id")
        connection.execute("ALTER TABLE users DROP COLUMN employee_id")
        connection.execute("DELETE FROM roles WHERE name = 'Payroll Admin'")
        connection.execute("DROP TABLE IF EXISTS schema_migrations")
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(PASSWORD), "demo_ceo"),
        )
        connection.commit()
    finally:
        connection.close()


def _snapshot():
    connection = get_connection()
    try:
        tables = [
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            "tables": tables,
            "users": _users(),
            "employees": [tuple(row) for row in connection.execute(
                "SELECT * FROM employees ORDER BY id"
            )],
            "roles": [tuple(row) for row in connection.execute(
                "SELECT * FROM roles ORDER BY id"
            )],
            "user_roles": [tuple(row) for row in connection.execute(
                "SELECT * FROM user_roles ORDER BY user_id, role_id"
            )],
        }
    finally:
        connection.close()


def test_migration_is_additive_idempotent_and_preserves_data(isolated_db):
    _make_legacy_database()
    before = _snapshot()

    first = apply_migrations()
    after_first = _snapshot()

    assert first["applied"] == ["001_rbac_scope_links"]
    assert first["skipped"] == []
    assert "schema_migrations" not in before["tables"]
    assert set(after_first["tables"]) == set(before["tables"]) | {"schema_migrations"}
    assert after_first["users"] == before["users"]
    assert after_first["employees"] == before["employees"]
    assert after_first["user_roles"] == before["user_roles"]
    assert {row for row in after_first["roles"] if row[1] == perms.ROLE_PAYROLL_ADMIN}
    assert _roles_for("demo_ceo") == [perms.ROLE_CEO]

    second = apply_migrations()
    assert second == {"applied": [], "skipped": ["001_rbac_scope_links"]}
    assert _snapshot() == after_first

    connection = get_connection()
    try:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        indexes = {row["name"] for row in connection.execute("PRAGMA index_list(users)")}
        fks = list(connection.execute("PRAGMA foreign_key_list(users)"))
        payroll_count = connection.execute(
            "SELECT COUNT(*) FROM roles WHERE name = ?", (perms.ROLE_PAYROLL_ADMIN,)
        ).fetchone()[0]
    finally:
        connection.close()

    assert "employee_id" in columns
    assert "idx_users_employee_id" in indexes
    assert any(fk[2] == "employees" and fk[3] == "employee_id" for fk in fks)
    assert payroll_count == 1


def test_migration_preserves_existing_password_hashes(isolated_db):
    _make_legacy_database()
    before = _users()
    original_hash = next(row[3] for row in before if row[1] == "demo_ceo")
    assert original_hash.count("$") >= 2

    apply_migrations()
    apply_migrations()

    after = _users()
    assert after == before
    assert next(row[3] for row in after if row[1] == "demo_ceo") == original_hash


def test_migration_enforces_unique_employee_link_and_foreign_key(isolated_db):
    _make_legacy_database()
    apply_migrations()

    connection = get_connection()
    try:
        connection.execute("UPDATE users SET employee_id = 7 WHERE username = 'demo_employee'")
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE users SET employee_id = 7 WHERE username = 'demo_ceo'"
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE users SET employee_id = 99999 WHERE username = 'demo_ceo'"
            )
        connection.rollback()
    finally:
        connection.close()


def test_migration_cli_command_is_repeatable(monkeypatch, isolated_db, capsys):
    import app.db as db_module

    _make_legacy_database()
    monkeypatch.setattr("sys.argv", ["app.db", "migrate"])

    db_module.main()
    first_output = capsys.readouterr().out
    db_module.main()
    second_output = capsys.readouterr().out

    assert "001_rbac_scope_links" in first_output
    assert "Already applied" in second_output
