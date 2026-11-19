"""Current-user profile API security and permission tests.

All mutations in these tests use the isolated temporary database fixture.
"""

from app.db import get_connection
from app.services.auth import hash_password


PASSWORD = "ProfileTest!234"


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


def _login(client, username):
    _set_password(username)
    response = client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200


def _link_employee(username, employee_id):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET employee_id = ? WHERE username = ?",
            (employee_id, username),
        )
        connection.commit()
    finally:
        connection.close()


def test_profile_requires_authentication(client):
    response = client.get("/api/profile")

    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "message": "Authentication required",
    }


def test_profile_returns_only_the_session_linked_employee(client):
    _link_employee("demo_employee", 6)
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET date_of_birth = ? WHERE id = ?",
            ("1995-06-12", 6),
        )
        connection.commit()
    finally:
        connection.close()
    _login(client, "demo_employee")

    response = client.get("/api/profile?employee_id=1")
    body = response.get_json()

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert body["user"] == {
        "username": "demo_employee",
        "email": "employee@example.invalid",
        "roles": ["Employee"],
        "account_status": "Active",
    }
    assert body["employee"]["employee_code"] == "DEMO006"
    assert body["employee"]["first_name"] == "Avery"
    assert body["employee"]["date_of_birth"] == "1995-06-12"
    assert body["employee"]["department"] == "Finance"
    assert body["employee"]["designation"] == "Accountant"
    assert body["employee"]["manager_name"] == "Alex Morgan"
    assert "id" not in body["employee"]
    assert "salary" not in body
    assert "editable_fields" in body
    assert "password_hash" not in str(body)
    assert "employee_id" not in body["user"]


def test_profile_without_linked_employee_returns_account_only(client):
    _login(client, "demo_sysadmin")

    response = client.get("/api/profile")
    body = response.get_json()

    assert response.status_code == 200
    assert body["employee"] is None
    assert body["editable_fields"] == []
    assert "salary" not in body
    assert "password_hash" not in str(body)


def test_profile_update_changes_only_own_authorized_phone(client):
    _link_employee("demo_employee", 6)
    _login(client, "demo_employee")

    response = client.put("/api/profile", json={"phone": "9000000999"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["employee"]["employee_code"] == "DEMO006"
    assert body["employee"]["phone"] == "9000000999"
    assert body["editable_fields"] == ["phone"]

    connection = get_connection()
    try:
        other = connection.execute(
            "SELECT phone FROM employees WHERE id = 1"
        ).fetchone()
        own = connection.execute(
            "SELECT phone FROM employees WHERE id = 6"
        ).fetchone()
    finally:
        connection.close()
    assert other["phone"] == "9000000001"
    assert own["phone"] == "9000000999"


def test_profile_update_rejects_client_supplied_employee_id(client):
    _link_employee("demo_employee", 6)
    _login(client, "demo_employee")

    response = client.put(
        "/api/profile", json={"employee_id": 1, "phone": "9000000998"}
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, phone FROM employees WHERE id IN (1, 6) ORDER BY id"
        ).fetchall()
    finally:
        connection.close()
    assert [(row["id"], row["phone"]) for row in rows] == [
        (1, "9000000001"),
        (6, "9000000006"),
    ]


def test_profile_update_requires_existing_employee_update_permission(client):
    _login(client, "demo_ceo")

    response = client.put("/api/profile", json={"phone": "9000000997"})

    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "message": "Permission denied",
    }


def test_salary_is_returned_only_with_salary_permission(client):
    _link_employee("demo_employee", 6)
    connection = get_connection()
    try:
        payroll_role = connection.execute(
            "SELECT id FROM roles WHERE name = 'Payroll Admin'"
        ).fetchone()["id"]
        user_id = connection.execute(
            "SELECT id FROM users WHERE username = 'demo_employee'"
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, payroll_role),
        )
        connection.execute(
            """
            INSERT INTO salary_records
                (employee_id, annual_salary, currency, effective_from)
            VALUES (?, ?, ?, ?)
            """,
            (6, 1250000, "INR", "2020-01-01"),
        )
        connection.commit()
    finally:
        connection.close()
    _login(client, "demo_employee")

    response = client.get("/api/profile")
    body = response.get_json()

    assert response.status_code == 200
    assert body["salary"] == {
        "annual_salary": 1250000.0,
        "currency": "INR",
        "effective_from": "2020-01-01",
        "effective_to": None,
    }
    assert "password_hash" not in str(body)
