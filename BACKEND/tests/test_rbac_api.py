"""API tests for RBAC enforcement using a test-only Flask blueprint.

The blueprint is registered only by the ``rbac_client`` fixture in conftest.
No employee or salary business endpoint is added to the production app.
"""

from app.db import get_connection
from app.services.auth import hash_password


PASSWORD = "RbacApi!234"


def _set_password(username):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(PASSWORD), username),
        )
        connection.commit()
    finally:
        connection.close()


def _login_as(client, username):
    _set_password(username)
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.get_json()
    return response


def _user_id(username):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()["id"]
    finally:
        connection.close()


def _role_id(name):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT id FROM roles WHERE name = ?", (name,)
        ).fetchone()["id"]
    finally:
        connection.close()


def _link(username, employee_id):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET employee_id = ? WHERE username = ?",
            (employee_id, username),
        )
        connection.commit()
    finally:
        connection.close()


def _add_role(username, role_name):
    connection = get_connection()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (_user_id(username), _role_id(role_name)),
        )
        connection.commit()
    finally:
        connection.close()


def _remove_role(username, role_name):
    connection = get_connection()
    try:
        connection.execute(
            "DELETE FROM user_roles WHERE user_id = ? AND role_id = ?",
            (_user_id(username), _role_id(role_name)),
        )
        connection.commit()
    finally:
        connection.close()


def _replace_roles(username, role_names):
    connection = get_connection()
    try:
        connection.execute(
            "DELETE FROM user_roles WHERE user_id = ?", (_user_id(username),)
        )
        for name in role_names:
            connection.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
                (_user_id(username), _role_id(name)),
            )
        connection.commit()
    finally:
        connection.close()


def _set_active(username, is_active):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET is_active = ? WHERE username = ?",
            (is_active, username),
        )
        connection.commit()
    finally:
        connection.close()


def _delete_user(username):
    connection = get_connection()
    try:
        user_id = _user_id(username)
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()


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
# Public and authentication-only endpoints
# ---------------------------------------------------------------------------

def test_public_health_and_login_work_without_session(rbac_client):
    health = rbac_client.get("/api/health")

    assert health.status_code == 200
    assert health.get_json()["database"] == "connected"

    login = _login_as(rbac_client, "demo_employee")
    assert login.get_json()["success"] is True
    assert login.get_json()["user"]["roles"] == ["Employee"]


def test_logout_and_me_require_authentication(rbac_client):
    expected = {"success": False, "message": "Authentication required"}

    logout = rbac_client.post("/api/auth/logout")
    me = rbac_client.get("/api/auth/me")

    assert logout.status_code == 401
    assert me.status_code == 401
    assert logout.get_json() == expected
    assert me.get_json() == expected


def test_logout_after_login_remains_successful(rbac_client):
    _login_as(rbac_client, "demo_ceo")

    response = rbac_client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "message": "Logout successful"}
    assert rbac_client.get("/api/auth/me").status_code == 401


def test_authenticated_endpoint_allows_a_user_without_roles(rbac_client):
    _replace_roles("demo_employee", [])
    _login_as(rbac_client, "demo_employee")

    assert rbac_client.get("/api/rbac-test/authenticated").status_code == 200
    assert rbac_client.get("/api/rbac-test/users").status_code == 403


# ---------------------------------------------------------------------------
# 401 / 403 / 404 semantics and default-deny
# ---------------------------------------------------------------------------

def test_unauthenticated_requests_return_401(rbac_client):
    paths = [
        "/api/rbac-test/users",
        "/api/rbac-test/employee/7",
        "/api/rbac-test/salary",
        "/api/rbac-test/open",
        "/api/does-not-exist",
    ]

    for path in paths:
        response = rbac_client.get(path)
        assert response.status_code == 401, path
        assert response.get_json() == {
            "success": False,
            "message": "Authentication required",
        }


def test_authenticated_unauthorized_requests_return_403(rbac_client):
    _login_as(rbac_client, "demo_employee")

    response = rbac_client.get("/api/rbac-test/users")

    assert response.status_code == 403
    assert response.get_json() == {"success": False, "message": "Permission denied"}


def test_default_deny_blocks_undecorated_and_unknown_endpoints(rbac_client):
    _login_as(rbac_client, "demo_ceo")

    undecorated = rbac_client.get("/api/rbac-test/open")
    unknown = rbac_client.get("/api/does-not-exist")

    assert undecorated.status_code == 403
    assert unknown.status_code == 403
    assert undecorated.get_json() == {"success": False, "message": "Permission denied"}


def test_out_of_scope_and_missing_records_return_404(rbac_client):
    _link("demo_employee", 7)
    _login_as(rbac_client, "demo_employee")

    out_of_scope = rbac_client.get("/api/rbac-test/employee/6")
    missing = rbac_client.get("/api/rbac-test/employee/99999")
    own = rbac_client.get("/api/rbac-test/employee/7")

    assert out_of_scope.status_code == 404
    assert missing.status_code == 404
    assert out_of_scope.get_json() == {
        "success": False,
        "message": "Resource not found",
    }
    assert own.status_code == 200
    assert own.get_json()["employee_id"] == 7


# ---------------------------------------------------------------------------
# Role permissions through real decorators
# ---------------------------------------------------------------------------

def test_system_admin_cannot_access_employee_or_salary_data(rbac_client):
    _login_as(rbac_client, "demo_sysadmin")

    assert rbac_client.get("/api/rbac-test/users").status_code == 200
    assert rbac_client.get("/api/rbac-test/employee/1").status_code == 403
    assert rbac_client.get("/api/rbac-test/salary").status_code == 403
    assert rbac_client.get("/api/rbac-test/hr-create").status_code == 403


def test_hr_admin_can_manage_salary_without_payroll_role(rbac_client):
    _login_as(rbac_client, "demo_hr_admin")

    assert rbac_client.get("/api/rbac-test/employee/3").status_code == 200
    assert rbac_client.post("/api/rbac-test/hr-create").status_code == 200
    assert rbac_client.get("/api/rbac-test/salary").status_code == 200


def test_role_change_takes_effect_on_the_next_request(rbac_client):
    _login_as(rbac_client, "demo_ceo")

    assert rbac_client.get("/api/rbac-test/users").status_code == 403

    _add_role("demo_ceo", "System Admin")
    first_after_change = rbac_client.get("/api/rbac-test/users")
    assert first_after_change.status_code == 200

    _remove_role("demo_ceo", "System Admin")
    assert rbac_client.get("/api/rbac-test/users").status_code == 403


def test_payroll_admin_has_only_salary_permissions(rbac_client):
    _replace_roles("demo_project_manager", ["Payroll Admin"])
    _login_as(rbac_client, "demo_project_manager")

    assert rbac_client.get("/api/rbac-test/salary").status_code == 200
    assert rbac_client.get("/api/rbac-test/employee/5").status_code == 403
    assert rbac_client.get("/api/rbac-test/users").status_code == 403
    assert rbac_client.get("/api/rbac-test/hr-create").status_code == 403


def test_demo_roles_are_not_automatically_granted_payroll_admin(rbac_client):
    for username in (
        "demo_ceo",
        "demo_hr_admin",
        "demo_hr_exec",
        "demo_dept_manager",
        "demo_project_manager",
        "demo_employee",
        "demo_sysadmin",
    ):
        assert "Payroll Admin" not in _login_as(rbac_client, username).get_json()["user"]["roles"]
        expected = 200 if username == "demo_hr_admin" else 403
        assert rbac_client.get("/api/rbac-test/salary").status_code == expected


def test_multiple_roles_combine_permissions(rbac_client):
    _link("demo_employee", 7)
    _add_role("demo_employee", "Payroll Admin")
    _login_as(rbac_client, "demo_employee")

    assert rbac_client.get("/api/rbac-test/salary").status_code == 200
    assert rbac_client.get("/api/rbac-test/employee/7").status_code == 200
    assert rbac_client.get("/api/rbac-test/users").status_code == 403


def test_any_and_all_permission_decorators(rbac_client):
    _login_as(rbac_client, "demo_ceo")

    assert rbac_client.get("/api/rbac-test/report").status_code == 200
    assert rbac_client.get("/api/rbac-test/either").status_code == 403
    assert rbac_client.get("/api/rbac-test/both").status_code == 403

    _login_as(rbac_client, "demo_sysadmin")
    assert rbac_client.get("/api/rbac-test/either").status_code == 200
    assert rbac_client.get("/api/rbac-test/both").status_code == 200


# ---------------------------------------------------------------------------
# Employee record scope
# ---------------------------------------------------------------------------

def test_employee_can_read_only_their_own_linked_record(rbac_client):
    _link("demo_employee", 7)
    _login_as(rbac_client, "demo_employee")

    assert rbac_client.get("/api/rbac-test/employee/7").status_code == 200
    assert rbac_client.get("/api/rbac-test/employee/6").status_code == 404


def test_missing_employee_link_denies_self_access(rbac_client):
    _login_as(rbac_client, "demo_employee")

    assert rbac_client.get("/api/rbac-test/employee/7").status_code == 404


def test_department_manager_sees_full_reporting_subtree(rbac_client):
    _link("demo_dept_manager", 4)
    _login_as(rbac_client, "demo_dept_manager")

    for employee_id in (4, 5, 7):
        assert rbac_client.get(f"/api/rbac-test/employee/{employee_id}").status_code == 200

    for employee_id in (1, 2, 3, 6):
        assert rbac_client.get(f"/api/rbac-test/employee/{employee_id}").status_code == 404


def test_manager_cycle_does_not_break_scope_checks(rbac_client):
    _set_manager(4, 5)
    _link("demo_dept_manager", 4)
    _login_as(rbac_client, "demo_dept_manager")

    assert rbac_client.get("/api/rbac-test/employee/5").status_code == 200
    assert rbac_client.get("/api/rbac-test/employee/7").status_code == 200
    assert rbac_client.get("/api/rbac-test/employee/3").status_code == 404


def test_hr_admin_and_ceo_have_organization_wide_employee_read(rbac_client):
    _login_as(rbac_client, "demo_hr_admin")
    assert rbac_client.get("/api/rbac-test/employee/3").status_code == 200

    _login_as(rbac_client, "demo_ceo")
    assert rbac_client.get("/api/rbac-test/employee/6").status_code == 200


# ---------------------------------------------------------------------------
# Invalid sessions
# ---------------------------------------------------------------------------

def test_inactive_user_cannot_use_an_existing_session(rbac_client):
    _login_as(rbac_client, "demo_ceo")
    _set_active("demo_ceo", 0)

    assert rbac_client.get("/api/auth/me").status_code == 401
    assert rbac_client.get("/api/rbac-test/users").status_code == 401


def test_deleted_user_cannot_use_an_existing_session(rbac_client):
    _login_as(rbac_client, "demo_ceo")
    _delete_user("demo_ceo")

    assert rbac_client.get("/api/auth/me").status_code == 401
    assert rbac_client.get("/api/rbac-test/users").status_code == 401
