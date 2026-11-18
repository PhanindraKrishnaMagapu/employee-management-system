"""Tests for employee CRUD endpoints and their RBAC enforcement.

Every test uses the isolated_db fixture through client, so the local
SQLite database is never opened by these requests.
"""

import pytest

from app.db import get_connection
from app.services.auth import hash_password
from app.services.authorization import EMPLOYEE_PUBLIC_FIELDS


PASSWORD = "EmployeeTest!234"
RESTRICTED_FIELDS = ("date_of_birth", "emergency_contact", "exit_reason")


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


def _user_id(username):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row["id"]
    finally:
        connection.close()


def _login_as(client, username):
    _set_password(username)
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.get_json()
    return response


def _payload(**overrides):
    payload = {
        "employee_code": "TEST100",
        "first_name": "Test",
        "last_name": "Employee",
        "official_email": "test.employee@example.invalid",
        "phone": "9000000099",
        "joining_date": "2026-01-15",
        "employment_type": "Full-time",
        "employment_status": "Active",
        "location": "Hyderabad",
        "department_id": 2,
        "designation_id": 3,
        "manager_id": 1,
    }
    payload.update(overrides)
    return payload


def _assert_public_employee(employee):
    assert set(employee) == set(EMPLOYEE_PUBLIC_FIELDS)
    for field in RESTRICTED_FIELDS:
        assert field not in employee


def _list_ids(response):
    return [employee["id"] for employee in response.get_json()["employees"]]


def test_unauthenticated_employee_endpoints_return_401(client):
    checks = [
        ("get", "/api/employees"),
        ("post", "/api/employees"),
        ("get", "/api/employees/1"),
        ("put", "/api/employees/1"),
        ("delete", "/api/employees/1"),
    ]

    for method, path in checks:
        if method in ("post", "put"):
            response = getattr(client, method)(path, json={})
        else:
            response = getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.get_json() == {
            "success": False,
            "message": "Authentication required",
        }


def test_hr_admin_can_create_employee(client):
    _login_as(client, "demo_hr_admin")

    response = client.post("/api/employees", json=_payload())
    body = response.get_json()

    assert response.status_code == 201, body
    assert body["success"] is True
    assert body["message"] == "Employee created"
    _assert_public_employee(body["employee"])
    assert body["employee"]["employee_code"] == "TEST100"
    assert body["employee"]["first_name"] == "Test"

    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT created_by, updated_by FROM employees WHERE id = ?",
            (body["employee"]["id"],),
        ).fetchone()
    finally:
        connection.close()
    assert row["created_by"] == _user_id("demo_hr_admin")
    assert row["updated_by"] == _user_id("demo_hr_admin")


@pytest.mark.parametrize("username", [
    "demo_ceo",
    "demo_hr_exec",
    "demo_dept_manager",
    "demo_project_manager",
    "demo_employee",
    "demo_sysadmin",
])
def test_create_requires_create_permission(client, username):
    _login_as(client, username)

    response = client.post("/api/employees", json=_payload())

    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "message": "Permission denied",
    }


def test_create_validation_and_conflicts(client):
    _login_as(client, "demo_hr_admin")

    bad_requests = [
        (client.post("/api/employees", json=[]), "JSON object"),
        (client.post("/api/employees", json=_payload(last_name="")), "Missing required"),
        (
            client.post(
                "/api/employees",
                json=_payload(official_email="not-an-email"),
            ),
            "valid email",
        ),
        (
            client.post("/api/employees", json=_payload(joining_date="2026-1-15")),
            "joining_date",
        ),
        (
            client.post("/api/employees", json=_payload(employment_status="Unknown")),
            "employment_status",
        ),
        (
            client.post("/api/employees", json=_payload(department_id=999)),
            "department_id",
        ),
        (
            client.post("/api/employees", json=_payload(date_of_birth="1990-01-01")),
            "Unsupported field",
        ),
        (
            client.post("/api/employees", json=_payload(created_by=1)),
            "Unsupported field",
        ),
    ]
    for response, expected_message in bad_requests:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]

    created = client.post("/api/employees", json=_payload())
    assert created.status_code == 201, created.get_json()

    duplicate_code = client.post(
        "/api/employees",
        json=_payload(official_email="different@example.invalid"),
    )
    duplicate_email = client.post(
        "/api/employees",
        json=_payload(employee_code="TEST101"),
    )
    assert duplicate_code.status_code == 409
    assert duplicate_email.status_code == 409
    assert duplicate_code.get_json()["success"] is False
    assert duplicate_email.get_json()["success"] is False


def test_list_employees_is_scoped_by_role(client):
    _login_as(client, "demo_hr_admin")
    hr_response = client.get("/api/employees")
    assert hr_response.status_code == 200
    assert len(_list_ids(hr_response)) == 7
    _assert_public_employee(hr_response.get_json()["employees"][0])

    _login_as(client, "demo_ceo")
    assert len(_list_ids(client.get("/api/employees"))) == 7

    _link("demo_employee", 7)
    _login_as(client, "demo_employee")
    assert _list_ids(client.get("/api/employees")) == [7]

    _login_as(client, "demo_hr_exec")
    assert _list_ids(client.get("/api/employees")) == []

    _link("demo_dept_manager", 4)
    _login_as(client, "demo_dept_manager")
    assert _list_ids(client.get("/api/employees")) == [4, 5, 7]


def test_get_employee_enforces_scope_and_missing_records(client):
    _link("demo_employee", 7)
    _login_as(client, "demo_employee")

    own = client.get("/api/employees/7")
    assert own.status_code == 200
    _assert_public_employee(own.get_json()["employee"])

    for employee_id in (6, 99999):
        response = client.get(f"/api/employees/{employee_id}")
        assert response.status_code == 404
        assert response.get_json() == {
            "success": False,
            "message": "Resource not found",
        }

    _login_as(client, "demo_hr_admin")
    assert client.get("/api/employees/3").status_code == 200

    _login_as(client, "demo_sysadmin")
    assert client.get("/api/employees/3").status_code == 403


def test_hr_admin_full_update_and_field_validation(client):
    _login_as(client, "demo_hr_admin")

    response = client.put(
        "/api/employees/1",
        json={
            "first_name": "Updated",
            "phone": "9000000111",
            "location": "Pune",
            "employment_status": "Active",
        },
    )
    assert response.status_code == 200, response.get_json()
    employee = response.get_json()["employee"]
    assert employee["first_name"] == "Updated"
    assert employee["phone"] == "9000000111"
    assert employee["location"] == "Pune"
    _assert_public_employee(employee)

    bad_updates = [
        ({"date_of_birth": "1990-01-01"}, "Unsupported field"),
        ({"created_by": 1}, "Unsupported field"),
        ({"manager_id": 1}, "manager_id cannot be the employee itself"),
        ({"employment_status": "Retired"}, "employment_status"),
    ]
    for payload, expected_message in bad_updates:
        bad = client.put("/api/employees/1", json=payload)
        assert bad.status_code == 400, bad.get_json()
        assert expected_message in bad.get_json()["message"]

    duplicate = client.put(
        "/api/employees/1",
        json={"official_email": "taylor.sharma@example.invalid"},
    )
    assert duplicate.status_code == 409

    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT updated_by FROM employees WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()
    assert row["updated_by"] == _user_id("demo_hr_admin")


def test_limited_and_self_update_permissions(client):
    _link("demo_dept_manager", 4)
    _login_as(client, "demo_dept_manager")

    allowed = client.put("/api/employees/5", json={"location": "Chennai"})
    assert allowed.status_code == 200, allowed.get_json()
    assert allowed.get_json()["employee"]["location"] == "Chennai"

    denied_field = client.put("/api/employees/5", json={"first_name": "No"})
    assert denied_field.status_code == 400
    out_of_scope = client.put("/api/employees/3", json={"location": "Pune"})
    assert out_of_scope.status_code == 404

    _link("demo_employee", 7)
    _login_as(client, "demo_employee")

    self_update = client.put("/api/employees/7", json={"phone": "9000000222"})
    assert self_update.status_code == 200, self_update.get_json()
    assert self_update.get_json()["employee"]["phone"] == "9000000222"

    denied_self_field = client.put("/api/employees/7", json={"location": "Pune"})
    assert denied_self_field.status_code == 400
    denied_other = client.put("/api/employees/6", json={"phone": "9000000333"})
    assert denied_other.status_code == 404


@pytest.mark.parametrize("username", [
    "demo_ceo",
    "demo_project_manager",
    "demo_sysadmin",
])
def test_update_requires_an_update_permission(client, username):
    _login_as(client, username)

    response = client.put("/api/employees/1", json={"phone": "9000000444"})

    assert response.status_code == 403


def test_delete_archives_employee_and_requires_archive_permission(client):
    _login_as(client, "demo_hr_admin")

    response = client.delete("/api/employees/3")
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {
        "success": True,
        "message": "Employee archived",
    }
    assert client.get("/api/employees/3").status_code == 404
    assert 3 not in _list_ids(client.get("/api/employees"))
    assert client.delete("/api/employees/3").status_code == 404

    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT archived_at, updated_by FROM employees WHERE id = 3"
        ).fetchone()
    finally:
        connection.close()
    assert row["archived_at"] is not None
    assert row["updated_by"] == _user_id("demo_hr_admin")

    _login_as(client, "demo_ceo")
    assert client.delete("/api/employees/4").status_code == 403

    _link("demo_employee", 7)
    _login_as(client, "demo_employee")
    assert client.delete("/api/employees/7").status_code == 403
