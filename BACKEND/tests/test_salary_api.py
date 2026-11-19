"""Tests for salary record endpoints and salary-specific authorization.

Every test uses the isolated_db fixture through client, so the local SQLite
database is never opened by these requests.
"""

import json

import pytest

from app.auth import permissions as perms
from app.db import get_connection
from app.services import salaries as salary_service
from app.services.auth import hash_password
from app.services.authorization import (
    RESTRICTED_EMPLOYEE_FIELDS,
    SALARY_FIELDS,
)


PASSWORD = "SalaryTest!234"
ALL_ROLES = (
    perms.ROLE_CEO,
    perms.ROLE_HR_ADMIN,
    perms.ROLE_HR_EXECUTIVE,
    perms.ROLE_DEPARTMENT_MANAGER,
    perms.ROLE_PROJECT_MANAGER,
    perms.ROLE_EMPLOYEE,
    perms.ROLE_SYSTEM_ADMIN,
    perms.ROLE_PAYROLL_ADMIN,
)
DEMO_USER_BY_ROLE = {
    perms.ROLE_CEO: "demo_ceo",
    perms.ROLE_HR_ADMIN: "demo_hr_admin",
    perms.ROLE_HR_EXECUTIVE: "demo_hr_exec",
    perms.ROLE_DEPARTMENT_MANAGER: "demo_dept_manager",
    perms.ROLE_PROJECT_MANAGER: "demo_project_manager",
    perms.ROLE_EMPLOYEE: "demo_employee",
    perms.ROLE_SYSTEM_ADMIN: "demo_sysadmin",
}
PAYROLL_USERNAME = "test_salary_payroll_admin"
PAYROLL_USER_ID = 92


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


def _add_role(username, role_name):
    connection = get_connection()
    try:
        role = connection.execute(
            "SELECT id FROM roles WHERE name = ?", (role_name,)
        ).fetchone()
        user_id = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()["id"]
        connection.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, role["id"]),
        )
        connection.commit()
    finally:
        connection.close()


def _create_payroll_user():
    connection = get_connection()
    try:
        role = connection.execute(
            "SELECT id FROM roles WHERE name = ?", (perms.ROLE_PAYROLL_ADMIN,)
        ).fetchone()
        connection.execute(
            "INSERT OR REPLACE INTO users "
            "(id, username, email, password_hash, employee_id) "
            "VALUES (?, ?, ?, ?, NULL)",
            (
                PAYROLL_USER_ID,
                PAYROLL_USERNAME,
                "salary-test-payroll@example.invalid",
                "placeholder",
            ),
        )
        connection.execute(
            "DELETE FROM user_roles WHERE user_id = ?", (PAYROLL_USER_ID,)
        )
        connection.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (PAYROLL_USER_ID, role["id"]),
        )
        connection.commit()
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


def _login_role(client, role):
    if role == perms.ROLE_PAYROLL_ADMIN:
        _create_payroll_user()
        return _login_as(client, PAYROLL_USERNAME)
    return _login_as(client, DEMO_USER_BY_ROLE[role])


def _login_payroll(client):
    _create_payroll_user()
    return _login_as(client, PAYROLL_USERNAME)


def _salary_payload(**overrides):
    payload = {
        "employee_id": 7,
        "annual_salary": 1200000,
        "currency": "INR",
        "effective_from": "2026-04-01",
        "effective_to": None,
    }
    payload.update(overrides)
    return payload


def _create_salary(client, **overrides):
    return client.post("/api/salaries", json=_salary_payload(**overrides))


def _created_salary(response):
    assert response.status_code == 201, response.get_json()
    return response.get_json()["salary"]


def _assert_salary_shape(salary):
    assert set(salary) == set(salary_service.SALARY_RECORD_FIELDS) | {
        "employee"
    }
    assert set(salary["employee"]) == set(salary_service.SALARY_EMPLOYEE_FIELDS)


def _assert_no_restricted_fields(body):
    text = json.dumps(body)
    for field in RESTRICTED_EMPLOYEE_FIELDS:
        assert f'"{field}"' not in text
    assert "Secret contact" not in text
    assert "Secret exit reason" not in text


def _set_secret_employee_fields():
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET date_of_birth = ?, emergency_contact = ?, "
            "exit_reason = ?, phone = ? WHERE id = ?",
            ("1990-01-01", "Secret contact", "Secret exit reason", "9999999999", 7),
        )
        connection.commit()
    finally:
        connection.close()


def _archive_employee(employee_id):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET archived_at = CURRENT_TIMESTAMP WHERE id = ?",
            (employee_id,),
        )
        connection.commit()
    finally:
        connection.close()


def _set_employee_code(employee_id, code):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET employee_code = ? WHERE id = ?",
            (code, employee_id),
        )
        connection.commit()
    finally:
        connection.close()


def _salary_audit_rows():
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT id, actor_user_id, action, table_name, record_id, summary "
            "FROM audit_logs WHERE table_name = ? ORDER BY id",
            (salary_service.SALARY_AUDIT_TABLE,),
        ).fetchall()
    finally:
        connection.close()


def _audit_text(row):
    return " ".join(
        "" if row[column] is None else str(row[column])
        for column in ("action", "table_name", "summary")
    )


def _assert_audit_summary(row, employee_id):
    assert json.loads(row["summary"]) == {"employee_id": employee_id}


def _request(client, method, path):
    if method in ("POST", "PUT"):
        return client.open(path, method=method, json={})
    return client.open(path, method=method)


def test_unauthenticated_salary_endpoints_return_401(client):
    checks = [
        ("GET", "/api/salaries"),
        ("GET", "/api/salaries/employees"),
        ("GET", "/api/salaries/1"),
        ("POST", "/api/salaries"),
        ("PUT", "/api/salaries/1"),
    ]

    for method, path in checks:
        response = _request(client, method, path)
        assert response.status_code == 401, (method, path, response.get_json())
        assert response.get_json()["message"] == "Authentication required"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_salary_permissions_by_role(client, role):
    _login_role(client, role)

    listed = client.get("/api/salaries")
    picker = client.get("/api/salaries/employees")
    created = _create_salary(client)

    if role == perms.ROLE_PAYROLL_ADMIN:
        assert listed.status_code == 200, listed.get_json()
        assert listed.get_json()["salaries"] == []
        assert picker.status_code == 200, picker.get_json()
        assert created.status_code == 201, created.get_json()
    else:
        for response in (listed, picker, created):
            assert response.status_code == 403, response.get_json()
            assert response.get_json() == {
                "success": False,
                "message": "Permission denied",
            }


def test_combined_roles_add_salary_without_general_employee_access(client):
    _login_as(client, "demo_hr_admin")
    _add_role("demo_hr_admin", perms.ROLE_PAYROLL_ADMIN)
    _login_as(client, "demo_hr_admin")
    assert client.get("/api/salaries").status_code == 200
    assert _create_salary(client, employee_id=7).status_code == 201
    assert client.get("/api/employees").status_code == 200

    _add_role("demo_project_manager", perms.ROLE_PAYROLL_ADMIN)
    _login_as(client, "demo_project_manager")
    assert client.get("/api/salaries").status_code == 200
    assert client.get("/api/salaries/employees").status_code == 200
    assert _create_salary(client, employee_id=5).status_code == 201
    # The project-only employee grant must not become general employee access.
    assert client.get("/api/employees").status_code == 403

    _add_role("demo_employee", perms.ROLE_PAYROLL_ADMIN)
    _login_as(client, "demo_employee")
    assert client.get("/api/salaries").status_code == 200
    assert client.get("/api/salaries/employees").status_code == 200

    _add_role("demo_sysadmin", perms.ROLE_PAYROLL_ADMIN)
    _login_as(client, "demo_sysadmin")
    assert client.get("/api/salaries").status_code == 200
    assert client.get("/api/employees").status_code == 403


def test_payroll_admin_crud_picker_and_no_delete(client):
    _login_payroll(client)

    picker = client.get("/api/salaries/employees")
    assert picker.status_code == 200, picker.get_json()
    employees = picker.get_json()["employees"]
    assert [employee["id"] for employee in employees] == [1, 2, 3, 4, 5, 6, 7]
    for employee in employees:
        assert set(employee) == set(salary_service.SALARY_EMPLOYEE_FIELDS)

    created = _create_salary(client)
    salary = _created_salary(created)
    _assert_salary_shape(salary)
    assert salary["employee_id"] == 7
    assert salary["annual_salary"] == 1200000.0
    assert salary["currency"] == "INR"
    assert salary["effective_from"] == "2026-04-01"
    assert salary["effective_to"] is None
    assert salary["employee"]["employee_code"] == "DEMO007"
    assert created.get_json()["message"] == "Salary record created"

    listed = client.get("/api/salaries")
    assert listed.status_code == 200, listed.get_json()
    body = listed.get_json()
    assert body["total"] == 1
    assert body["limit"] == 100
    assert body["offset"] == 0
    _assert_salary_shape(body["salaries"][0])

    fetched = client.get(f"/api/salaries/{salary['id']}")
    assert fetched.status_code == 200, fetched.get_json()
    _assert_salary_shape(fetched.get_json()["salary"])

    updated = client.put(
        f"/api/salaries/{salary['id']}",
        json={
            "annual_salary": 1500000.25,
            "currency": "usd",
            "effective_to": "2027-03-31",
        },
    )
    assert updated.status_code == 200, updated.get_json()
    body = updated.get_json()["salary"]
    assert body["annual_salary"] == 1500000.25
    assert body["currency"] == "USD"
    assert body["effective_to"] == "2027-03-31"
    assert updated.get_json()["message"] == "Salary record updated"

    immutable = client.put(
        f"/api/salaries/{salary['id']}", json={"employee_id": 5}
    )
    assert immutable.status_code == 400
    assert "Unsupported field" in immutable.get_json()["message"]

    empty = client.put(f"/api/salaries/{salary['id']}", json={})
    assert empty.status_code == 400
    assert "At least one field" in empty.get_json()["message"]

    assert client.get("/api/salaries/99999").status_code == 404
    assert client.put("/api/salaries/99999", json={"annual_salary": 1}).status_code == 404

    deleted = client.delete(f"/api/salaries/{salary['id']}")
    assert deleted.status_code in (403, 404, 405)
    assert client.get(f"/api/salaries/{salary['id']}").status_code == 200


def test_creating_later_period_closes_previous_open_record(client):
    _login_payroll(client)

    first = _created_salary(_create_salary(
        client,
        annual_salary=1000000,
        effective_from="2026-01-01",
        effective_to=None,
    ))
    second = _created_salary(_create_salary(
        client,
        annual_salary=1200000,
        effective_from="2026-04-01",
        effective_to=None,
    ))
    third = _created_salary(_create_salary(
        client,
        annual_salary=1400000,
        effective_from="2026-07-01",
        effective_to=None,
    ))

    first_after = client.get(f"/api/salaries/{first['id']}").get_json()["salary"]
    second_after = client.get(f"/api/salaries/{second['id']}").get_json()["salary"]
    assert first_after["effective_to"] == "2026-03-31"
    assert second_after["effective_to"] == "2026-06-30"
    assert third["effective_to"] is None

    history = client.get(
        "/api/salaries", query_string={"employee_id": 7}
    ).get_json()
    assert [row["id"] for row in history["salaries"]] == [
        third["id"],
        second["id"],
        first["id"],
    ]


def test_auto_close_writes_safe_update_and_create_audit_entries(client):
    _login_payroll(client)

    first = _created_salary(_create_salary(
        client,
        annual_salary=1000000,
        currency="INR",
        effective_from="2026-01-01",
        effective_to=None,
    ))
    second = _created_salary(_create_salary(
        client,
        annual_salary=1200000,
        currency="USD",
        effective_from="2026-04-01",
        effective_to=None,
    ))

    rows = _salary_audit_rows()
    assert len(rows) == 3

    create_first, auto_close, create_second = rows
    assert create_first["action"] == salary_service.SALARY_AUDIT_CREATE
    assert create_first["record_id"] == first["id"]
    _assert_audit_summary(create_first, 7)

    assert auto_close["actor_user_id"] == PAYROLL_USER_ID
    assert auto_close["action"] == salary_service.SALARY_AUDIT_UPDATE
    assert auto_close["table_name"] == salary_service.SALARY_AUDIT_TABLE
    assert auto_close["record_id"] == first["id"]
    _assert_audit_summary(auto_close, 7)

    assert create_second["action"] == salary_service.SALARY_AUDIT_CREATE
    assert create_second["record_id"] == second["id"]
    _assert_audit_summary(create_second, 7)

    sensitive_values = (
        "1000000",
        "1200000",
        "INR",
        "USD",
        "2026-01-01",
        "2026-03-31",
        "2026-04-01",
        "annual_salary",
        "currency",
        "effective_from",
        "effective_to",
        "bank",
        "tax",
    )
    for row in rows:
        text = _audit_text(row)
        for value in sensitive_values:
            assert value not in text


def test_auto_close_audit_entries_roll_back_when_transaction_fails(
    client, monkeypatch
):
    _login_payroll(client)

    first = _created_salary(_create_salary(
        client,
        annual_salary=1000000,
        effective_from="2026-01-01",
        effective_to=None,
    ))
    assert len(_salary_audit_rows()) == 1

    original_log_create = salary_service.log_salary_create

    def fail_after_audit_writes(connection, actor_user_id, salary):
        original_log_create(connection, actor_user_id, salary)
        raise RuntimeError("forced failure after audit writes")

    monkeypatch.setattr(
        salary_service, "log_salary_create", fail_after_audit_writes
    )

    with pytest.raises(RuntimeError, match="forced failure after audit writes"):
        _create_salary(
            client,
            annual_salary=1200000,
            effective_from="2026-04-01",
            effective_to=None,
        )

    rows = _salary_audit_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == salary_service.SALARY_AUDIT_CREATE
    assert rows[0]["record_id"] == first["id"]

    connection = get_connection()
    try:
        previous = connection.execute(
            "SELECT effective_to FROM salary_records WHERE id = ?",
            (first["id"],),
        ).fetchone()
        total = connection.execute(
            "SELECT COUNT(*) AS total FROM salary_records"
        ).fetchone()["total"]
    finally:
        connection.close()

    assert previous["effective_to"] is None
    assert total == 1


def test_salary_overlap_conflicts_and_update_revalidation(client):
    _login_payroll(client)

    first = _created_salary(_create_salary(
        client,
        effective_from="2026-01-01",
        effective_to="2026-03-31",
    ))
    second = _created_salary(_create_salary(
        client,
        effective_from="2026-04-01",
        effective_to="2026-06-30",
    ))

    overlap_before = _create_salary(
        client, effective_from="2026-02-01", effective_to="2026-02-28"
    )
    assert overlap_before.status_code == 409
    assert overlap_before.get_json()["message"] == (
        "Salary period overlaps an existing record"
    )

    overlap_open = _create_salary(
        client, effective_from="2026-03-15", effective_to=None
    )
    assert overlap_open.status_code == 409

    duplicate_start = _create_salary(
        client, effective_from="2026-04-01", effective_to=None
    )
    assert duplicate_start.status_code == 409

    extends_overlap = client.put(
        f"/api/salaries/{first['id']}", json={"effective_to": "2026-05-01"}
    )
    assert extends_overlap.status_code == 409

    starts_overlap = client.put(
        f"/api/salaries/{second['id']}", json={"effective_from": "2026-03-31"}
    )
    assert starts_overlap.status_code == 409

    same_dates = client.put(
        f"/api/salaries/{second['id']}",
        json={"effective_from": "2026-04-01", "effective_to": "2026-06-30"},
    )
    assert same_dates.status_code == 200, same_dates.get_json()

    closed = client.put(
        f"/api/salaries/{second['id']}", json={"effective_to": "2026-05-31"}
    )
    assert closed.status_code == 200, closed.get_json()
    assert closed.get_json()["salary"]["effective_to"] == "2026-05-31"

    inverted = client.put(
        f"/api/salaries/{second['id']}", json={"effective_to": "2026-03-31"}
    )
    assert inverted.status_code == 400
    assert "on or after effective_from" in inverted.get_json()["message"]


def test_salary_create_and_update_validation(client):
    _login_payroll(client)
    salary = _created_salary(_create_salary(client))

    bad_creates = [
        (client.post("/api/salaries", json=[]), "JSON object"),
        (client.post("/api/salaries", json={}), "Missing required"),
        (
            client.post("/api/salaries", json=_salary_payload(employee_id=0)),
            "employee_id",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(employee_id="7")),
            "employee_id",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(employee_id=True)),
            "employee_id",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(annual_salary="100")),
            "non-negative finite",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(annual_salary=True)),
            "non-negative finite",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(annual_salary=-1)),
            "non-negative finite",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(annual_salary=123.456)),
            "two decimal places",
        ),
        (
            client.post(
                "/api/salaries",
                json=_salary_payload(annual_salary=1_000_000_001),
            ),
            "must not exceed",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(currency="IN")),
            "three-letter",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(currency=123)),
            "three-letter",
        ),
        (
            client.post(
                "/api/salaries", json=_salary_payload(effective_from="2026-1-1")
            ),
            "YYYY-MM-DD",
        ),
        (
            client.post(
                "/api/salaries", json=_salary_payload(effective_from="not-a-date")
            ),
            "YYYY-MM-DD",
        ),
        (
            client.post(
                "/api/salaries",
                json=_salary_payload(
                    effective_from="2026-04-01", effective_to="2026-03-31"
                ),
            ),
            "on or after effective_from",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(net_salary=1)),
            "Unsupported field",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(tax=1)),
            "Unsupported field",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(bank_account="1")),
            "Unsupported field",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(payslip="x")),
            "Unsupported field",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(id=1)),
            "Unsupported field",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(created_at="x")),
            "Unsupported field",
        ),
        (
            client.post("/api/salaries", json=_salary_payload(employee_name="x")),
            "Unsupported field",
        ),
    ]
    for response, expected_message in bad_creates:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]

    defaulted = _created_salary(_create_salary(
        client,
        employee_id=5,
        annual_salary=0,
        currency=None,
        effective_from="2026-01-01",
    ))
    assert defaulted["currency"] == "INR"
    assert defaulted["annual_salary"] == 0.0

    lower_currency = _created_salary(_create_salary(
        client,
        employee_id=4,
        currency="eur",
        effective_from="2026-01-01",
    ))
    assert lower_currency["currency"] == "EUR"

    bad_updates = [
        (
            client.put(f"/api/salaries/{salary['id']}", json={}),
            "At least one field",
        ),
        (
            client.put(f"/api/salaries/{salary['id']}", json={"employee_id": 5}),
            "Unsupported field",
        ),
        (
            client.put(f"/api/salaries/{salary['id']}", json={"annual_salary": "x"}),
            "non-negative finite",
        ),
        (
            client.put(f"/api/salaries/{salary['id']}", json={"currency": "I"}),
            "three-letter",
        ),
        (
            client.put(
                f"/api/salaries/{salary['id']}", json={"effective_from": "bad"}
            ),
            "YYYY-MM-DD",
        ),
    ]
    for response, expected_message in bad_updates:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]

    assert _create_salary(client, employee_id=99999).status_code == 404


def test_salary_amount_rejects_non_finite_values_directly():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(salary_service.SalaryValidationError):
            salary_service.validate_create_payload(
                _salary_payload(annual_salary=value)
            )


def test_salary_search_filters_pagination_and_query_validation(client):
    _login_payroll(client)
    _set_employee_code(7, "DEMO%7")
    _set_employee_code(5, "DEMO_5")

    first = _created_salary(_create_salary(
        client,
        employee_id=7,
        currency="INR",
        effective_from="2026-01-01",
        effective_to="2026-03-31",
    ))
    second = _created_salary(_create_salary(
        client,
        employee_id=5,
        currency="USD",
        effective_from="2026-04-01",
        effective_to="2026-06-30",
    ))
    third = _created_salary(_create_salary(
        client,
        employee_id=4,
        currency="EUR",
        effective_from="2026-07-01",
        effective_to=None,
    ))

    def listed(**params):
        response = client.get("/api/salaries", query_string=params)
        assert response.status_code == 200, response.get_json()
        return response.get_json()

    def ids(**params):
        return [row["id"] for row in listed(**params)["salaries"]]

    assert ids() == [third["id"], second["id"], first["id"]]
    assert ids(employee_id=7) == [first["id"]]
    assert ids(search="demo%7") == [first["id"]]
    assert ids(search="DEMO_5") == [second["id"]]
    assert ids(search="jamie") == [first["id"]]
    assert ids(search="das") == [first["id"]]
    assert ids(search="jamie.das@example.invalid") == [first["id"]]
    assert ids(search="%") == [first["id"]]
    assert ids(search="_") == [second["id"]]
    assert ids(currency="usd") == [second["id"]]
    assert ids(active_on="2026-02-15") == [first["id"]]
    assert ids(active_on="2026-05-01") == [second["id"]]
    assert ids(active_on="2026-08-01") == [third["id"]]
    assert ids(effective_from="2026-04-01") == [third["id"], second["id"]]
    assert ids(effective_to="2026-06-30") == [second["id"], first["id"]]

    page = listed(limit=2, offset=0)
    assert page["total"] == 3
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert [row["id"] for row in page["salaries"]] == [third["id"], second["id"]]

    tail = listed(limit=2, offset=2)
    assert [row["id"] for row in tail["salaries"]] == [first["id"]]

    capped = listed(limit=1000)
    assert capped["limit"] == 500
    assert capped["total"] == 3

    bad_queries = [
        {"employee_id": "abc"},
        {"employee_id": "0"},
        {"limit": "0"},
        {"limit": "abc"},
        {"offset": "-1"},
        {"offset": "abc"},
        {"active_on": "2026-02-30"},
        {"effective_from": "bad"},
        {"currency": "IN"},
        {"search": "x" * 201},
    ]
    for query in bad_queries:
        response = client.get("/api/salaries", query_string=query)
        assert response.status_code == 400, (query, response.get_json())


def test_salary_picker_search_and_archived_history(client):
    _login_payroll(client)
    salary = _created_salary(_create_salary(client))

    search = client.get(
        "/api/salaries/employees", query_string={"search": "jamie"}
    )
    assert search.status_code == 200, search.get_json()
    assert [employee["id"] for employee in search.get_json()["employees"]] == [7]

    _archive_employee(7)

    picker = client.get("/api/salaries/employees")
    assert picker.status_code == 200, picker.get_json()
    assert 7 not in [employee["id"] for employee in picker.get_json()["employees"]]

    listed = client.get("/api/salaries")
    assert listed.status_code == 200, listed.get_json()
    assert listed.get_json()["total"] == 1
    assert client.get(f"/api/salaries/{salary['id']}").status_code == 200

    blocked_create = _create_salary(client, effective_from="2027-01-01")
    assert blocked_create.status_code == 400
    assert "Archived employees" in blocked_create.get_json()["message"]

    corrected_update = client.put(
        f"/api/salaries/{salary['id']}",
        json={"annual_salary": 1, "effective_to": "2026-12-31"},
    )
    assert corrected_update.status_code == 200, corrected_update.get_json()
    assert corrected_update.get_json()["salary"]["annual_salary"] == 1
    assert corrected_update.get_json()["salary"]["effective_to"] == "2026-12-31"


def test_salary_create_and_update_write_safe_audit_logs(client):
    _login_payroll(client)
    salary = _created_salary(_create_salary(
        client,
        annual_salary=1234567.89,
        currency="USD",
        effective_from="2026-01-01",
        effective_to="2026-03-31",
    ))

    updated = client.put(
        f"/api/salaries/{salary['id']}",
        json={
            "annual_salary": 7654321.25,
            "currency": "EUR",
            "effective_from": "2026-02-01",
            "effective_to": "2026-04-30",
        },
    )
    assert updated.status_code == 200, updated.get_json()

    rows = _salary_audit_rows()
    assert len(rows) == 2
    create_row, update_row = rows

    assert create_row["actor_user_id"] == PAYROLL_USER_ID
    assert create_row["action"] == salary_service.SALARY_AUDIT_CREATE
    assert create_row["table_name"] == salary_service.SALARY_AUDIT_TABLE
    assert create_row["record_id"] == salary["id"]
    _assert_audit_summary(create_row, 7)

    assert update_row["actor_user_id"] == PAYROLL_USER_ID
    assert update_row["action"] == salary_service.SALARY_AUDIT_UPDATE
    assert update_row["table_name"] == salary_service.SALARY_AUDIT_TABLE
    assert update_row["record_id"] == salary["id"]
    _assert_audit_summary(update_row, 7)

    sensitive_values = (
        "1234567.89",
        "7654321.25",
        "USD",
        "EUR",
        "2026-01-01",
        "2026-03-31",
        "2026-02-01",
        "2026-04-30",
        "annual_salary",
        "currency",
        "effective_from",
        "effective_to",
        "bank",
        "tax",
        "payslip",
        "account",
    )
    for row in rows:
        text = _audit_text(row)
        for value in sensitive_values:
            assert value not in text


def test_failed_salary_writes_do_not_create_audit_entries(client):
    _login_payroll(client)
    salary = _created_salary(_create_salary(client))
    assert len(_salary_audit_rows()) == 1

    failed = [
        client.put(
            f"/api/salaries/{salary['id']}", json={"annual_salary": -1}
        ),
        client.put(
            f"/api/salaries/{salary['id']}", json={"employee_id": 5}
        ),
        client.put(
            f"/api/salaries/{salary['id']}", json={"effective_from": "bad"}
        ),
        _create_salary(client, effective_from="2026-04-01"),
        _create_salary(client, annual_salary=123.456),
    ]
    for response in failed:
        assert response.status_code in (400, 409), response.get_json()

    assert len(_salary_audit_rows()) == 1


def test_archived_employee_salary_corrections_are_allowed_and_audited(client):
    _login_payroll(client)
    first = _created_salary(_create_salary(
        client,
        annual_salary=1000000,
        effective_from="2026-01-01",
        effective_to="2026-03-31",
    ))
    second = _created_salary(_create_salary(
        client,
        annual_salary=1100000,
        effective_from="2026-04-01",
        effective_to="2026-06-30",
    ))

    _archive_employee(7)

    assert client.get(f"/api/salaries/{first['id']}").status_code == 200
    history = client.get(
        "/api/salaries", query_string={"employee_id": 7}
    )
    assert history.status_code == 200, history.get_json()
    assert history.get_json()["total"] == 2

    corrected = client.put(
        f"/api/salaries/{first['id']}",
        json={
            "annual_salary": 1300000.5,
            "currency": "usd",
            "effective_to": "2026-03-15",
        },
    )
    assert corrected.status_code == 200, corrected.get_json()
    corrected_body = corrected.get_json()["salary"]
    assert corrected_body["annual_salary"] == 1300000.5
    assert corrected_body["currency"] == "USD"
    assert corrected_body["effective_to"] == "2026-03-15"

    revalidated = client.put(
        f"/api/salaries/{second['id']}",
        json={"effective_from": "2026-04-01", "effective_to": "2026-06-30"},
    )
    assert revalidated.status_code == 200, revalidated.get_json()

    closed = client.put(
        f"/api/salaries/{second['id']}", json={"effective_to": "2026-05-31"}
    )
    assert closed.status_code == 200, closed.get_json()
    assert closed.get_json()["salary"]["effective_to"] == "2026-05-31"

    rows = _salary_audit_rows()
    assert [row["action"] for row in rows] == [
        salary_service.SALARY_AUDIT_CREATE,
        salary_service.SALARY_AUDIT_CREATE,
        salary_service.SALARY_AUDIT_UPDATE,
        salary_service.SALARY_AUDIT_UPDATE,
        salary_service.SALARY_AUDIT_UPDATE,
    ]
    for row in rows:
        assert row["actor_user_id"] == PAYROLL_USER_ID
        assert row["table_name"] == salary_service.SALARY_AUDIT_TABLE
        assert row["record_id"] in (first["id"], second["id"])
        _assert_audit_summary(row, 7)
        text = _audit_text(row)
        for value in (
            "1000000",
            "1100000",
            "1300000.5",
            "USD",
            "2026-01-01",
            "2026-03-31",
            "2026-04-01",
            "2026-06-30",
            "2026-03-15",
            "2026-05-31",
            "annual_salary",
            "currency",
            "effective_from",
            "effective_to",
            "bank",
            "tax",
        ):
            assert value not in text

    blocked_create = _create_salary(client, effective_from="2027-01-01")
    assert blocked_create.status_code == 400
    assert "Archived employees" in blocked_create.get_json()["message"]

    immutable = client.put(
        f"/api/salaries/{first['id']}", json={"employee_id": 5}
    )
    assert immutable.status_code == 400
    assert "Unsupported field" in immutable.get_json()["message"]

    assert len(_salary_audit_rows()) == 5


def test_archived_employee_salary_correction_rejects_invalid_dates_and_overlaps(
    client,
):
    _login_payroll(client)
    first = _created_salary(_create_salary(
        client,
        effective_from="2026-01-01",
        effective_to="2026-03-31",
    ))
    second = _created_salary(_create_salary(
        client,
        effective_from="2026-04-01",
        effective_to="2026-06-30",
    ))
    _archive_employee(7)
    before = len(_salary_audit_rows())

    invalid_date = client.put(
        f"/api/salaries/{first['id']}", json={"effective_from": "2026-02-30"}
    )
    assert invalid_date.status_code == 400

    inverted = client.put(
        f"/api/salaries/{first['id']}", json={"effective_to": "2025-12-31"}
    )
    assert inverted.status_code == 400
    assert "on or after effective_from" in inverted.get_json()["message"]

    overlap_end = client.put(
        f"/api/salaries/{first['id']}", json={"effective_to": "2026-04-01"}
    )
    assert overlap_end.status_code == 409

    overlap_start = client.put(
        f"/api/salaries/{second['id']}", json={"effective_from": "2026-03-31"}
    )
    assert overlap_start.status_code == 409

    empty = client.put(f"/api/salaries/{first['id']}", json={})
    assert empty.status_code == 400

    assert client.put(
        "/api/salaries/99999", json={"annual_salary": 1}
    ).status_code == 404

    assert len(_salary_audit_rows()) == before


def test_salary_audit_logging_requires_salary_manage(client):
    _login_payroll(client)
    salary = _created_salary(_create_salary(client))
    assert len(_salary_audit_rows()) == 1

    _login_as(client, "demo_hr_admin")
    denied_create = _create_salary(client, employee_id=5)
    denied_update = client.put(
        f"/api/salaries/{salary['id']}", json={"annual_salary": 1}
    )
    assert denied_create.status_code == 403
    assert denied_update.status_code == 403
    assert len(_salary_audit_rows()) == 1


def test_salary_responses_use_minimal_employee_allowlist(client):
    _set_secret_employee_fields()
    _login_payroll(client)
    salary = _created_salary(_create_salary(client))

    responses = [
        client.get("/api/salaries"),
        client.get(f"/api/salaries/{salary['id']}"),
        client.get("/api/salaries/employees"),
    ]
    for response in responses:
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        _assert_no_restricted_fields(body)
        assert '"phone"' not in json.dumps(body)

    for row in client.get("/api/salaries").get_json()["salaries"]:
        _assert_salary_shape(row)
        assert set(row["employee"]) == set(salary_service.SALARY_EMPLOYEE_FIELDS)

    picker_employee = client.get(
        "/api/salaries/employees"
    ).get_json()["employees"][6]
    assert set(picker_employee) == set(salary_service.SALARY_EMPLOYEE_FIELDS)
    assert picker_employee["id"] == 7


def test_general_employee_api_never_exposes_salary_fields(client):
    _login_payroll(client)
    _created_salary(_create_salary(client))

    _login_as(client, "demo_hr_admin")
    employees = client.get("/api/employees")
    assert employees.status_code == 200, employees.get_json()
    text = json.dumps(employees.get_json())
    for field in SALARY_FIELDS:
        assert f'"{field}"' not in text
    assert "1200000" not in text

    create_payload = {
        "employee_code": "DEMO099",
        "first_name": "Test",
        "last_name": "User",
        "official_email": "test.user@example.invalid",
        "joining_date": "2026-01-01",
        "employment_type": "Full-time",
        "department_id": 1,
        "designation_id": 1,
        "annual_salary": 100,
    }
    rejected_create = client.post("/api/employees", json=create_payload)
    assert rejected_create.status_code == 400
    assert "Unsupported field" in rejected_create.get_json()["message"]

    rejected_update = client.put(
        "/api/employees/7", json={"annual_salary": 100}
    )
    assert rejected_update.status_code == 400
    assert "Unsupported field" in rejected_update.get_json()["message"]


def test_salary_responses_are_not_cacheable(client):
    _login_payroll(client)
    salary = _created_salary(_create_salary(client))

    responses = [
        client.get("/api/salaries"),
        client.get("/api/salaries/employees"),
        client.get(f"/api/salaries/{salary['id']}"),
        client.put(f"/api/salaries/{salary['id']}", json={"annual_salary": 1}),
        client.get("/api/salaries/99999"),
    ]
    for response in responses:
        assert response.headers.get("Cache-Control") == "no-store"


def test_salary_permission_constants_and_role_grants():
    assert perms.PERMISSION_SALARY_READ == "salary:read"
    assert perms.PERMISSION_SALARY_MANAGE == "salary:manage"
    assert perms.PERMISSION_SALARY_READ in perms.ALL_PERMISSIONS
    assert perms.PERMISSION_SALARY_MANAGE in perms.ALL_PERMISSIONS

    assert perms.ROLE_PERMISSIONS[perms.ROLE_PAYROLL_ADMIN] == frozenset({
        perms.PERMISSION_SALARY_READ,
        perms.PERMISSION_SALARY_MANAGE,
    })
    for role in ALL_ROLES:
        if role == perms.ROLE_PAYROLL_ADMIN:
            continue
        assert not perms.permissions_for_roles((role,)) & {
            perms.PERMISSION_SALARY_READ,
            perms.PERMISSION_SALARY_MANAGE,
        }


def test_salary_scope_helper_grants_only_explicit_payroll_grant():
    class User:
        def __init__(self, roles, permissions, employee_id=None):
            self.roles = tuple(roles)
            self.permissions = frozenset(permissions)
            self.employee_id = employee_id

    connection = get_connection()
    try:
        payroll = User(
            (perms.ROLE_PAYROLL_ADMIN,),
            (perms.PERMISSION_SALARY_READ, perms.PERMISSION_SALARY_MANAGE),
        )
        assert salary_service.salary_employee_scope(payroll, connection) is None

        employee = User(
            (perms.ROLE_EMPLOYEE,),
            (perms.PERMISSION_EMPLOYEE_READ_SCOPE,),
            employee_id=7,
        )
        assert salary_service.salary_employee_scope(
            employee, connection
        ) == frozenset({7})

        unlinked = User((perms.ROLE_HR_EXECUTIVE,), (), employee_id=None)
        assert salary_service.salary_employee_scope(
            unlinked, connection
        ) == frozenset()
    finally:
        connection.close()
