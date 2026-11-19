"""Tests for JML endpoints, RBAC, scope, validation, and transaction safety.

Every test uses the isolated_db fixture through client, so the local SQLite
database is never opened by these requests.
"""

import json

import pytest

from app.auth import permissions as perms
from app.db import get_connection
from app.services.auth import hash_password
from app.services.authorization import (
    EMPLOYEE_PUBLIC_FIELDS,
    RESTRICTED_EMPLOYEE_FIELDS,
    SALARY_FIELDS,
)


PASSWORD = "JMLTest!234"
ALL_FORBIDDEN_FIELDS = RESTRICTED_EMPLOYEE_FIELDS | SALARY_FIELDS


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


def _login_as(client, username):
    _set_password(username)
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.get_json()
    return response


def _create_scoped_manager(monkeypatch, employee_id):
    """Create a test-only role that has jml:manage but limited employee scope."""

    username = "scoped_jml_manager"
    role_name = "Scoped JML Manager"
    connection = get_connection()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO roles (id, name, description) VALUES (?, ?, ?)",
            (99, role_name, "Test role with manage permission and employee scope"),
        )
        connection.execute(
            "INSERT OR IGNORE INTO users "
            "(id, username, email, password_hash, employee_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (99, username, "scoped-jml@example.invalid", "placeholder", employee_id),
        )
        connection.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (99, 99),
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setitem(
        perms.ROLE_PERMISSIONS,
        role_name,
        frozenset({perms.PERMISSION_JML_MANAGE}),
    )
    return username


def _event_payload(event_type="Joiner", **overrides):
    payload = {
        "employee_id": 6,
        "event_type": event_type,
        "effective_date": "2026-12-01",
    }
    if event_type == "Mover":
        payload["changes"] = {"location": "Pune"}
    if event_type == "Leaver":
        payload["reason"] = "Resignation"
    payload.update(overrides)
    return payload


def _create_event(client, event_type="Joiner", **overrides):
    return client.post("/api/jml/events", json=_event_payload(event_type, **overrides))


def _created_event(response):
    assert response.status_code == 201, response.get_json()
    return response.get_json()["event"]


def _complete_checklist(client, event_id):
    """Mark every checklist item of an event as completed."""

    detail = client.get(f"/api/jml/events/{event_id}")
    assert detail.status_code == 200, detail.get_json()
    for item in detail.get_json()["checklist_items"]:
        response = client.patch(
            f"/api/jml/events/{event_id}/checklist/{item['id']}",
            json={"status": "Completed"},
        )
        assert response.status_code == 200, response.get_json()
    return client.get(f"/api/jml/events/{event_id}")


def _db_counts():
    connection = get_connection()
    try:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("jml_events", "checklist_items", "employee_history")
        )
    finally:
        connection.close()


def _employee_row(employee_id):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
    finally:
        connection.close()


def _assert_public_employee(employee):
    assert set(employee) == set(EMPLOYEE_PUBLIC_FIELDS)


def _assert_no_forbidden_fields(body):
    text = json.dumps(body)
    for field in ALL_FORBIDDEN_FIELDS:
        assert f'"{field}"' not in text


def test_unauthenticated_jml_endpoints_return_401(client):
    checks = [
        (client.get("/api/jml/events"), "GET list"),
        (client.get("/api/jml/events/1"), "GET detail"),
        (client.post("/api/jml/events", json={}), "POST"),
        (client.patch("/api/jml/events/1", json={"status": "Completed"}), "PATCH event"),
        (
            client.patch(
                "/api/jml/events/1/checklist/1", json={"status": "Completed"}
            ),
            "PATCH checklist",
        ),
    ]

    for response, label in checks:
        assert response.status_code == 401, label
        assert response.get_json()["message"] == "Authentication required"


@pytest.mark.parametrize("username", [
    "demo_employee",
    "demo_project_manager",
    "demo_sysadmin",
])
def test_users_without_jml_permissions_are_denied(client, username):
    _login_as(client, username)

    assert client.get("/api/jml/events").status_code == 403
    assert _create_event(client).status_code == 403


def test_ceo_can_read_but_not_manage_jml(client):
    _login_as(client, "demo_ceo")

    assert client.get("/api/jml/events").status_code == 200
    assert _create_event(client).status_code == 403


def test_hr_admin_can_read_and_manage_jml(client):
    _login_as(client, "demo_hr_admin")

    initial = client.get("/api/jml/events")
    assert initial.status_code == 200, initial.get_json()
    assert initial.get_json()["events"] == []

    created = _created_event(_create_event(client))
    listed = client.get("/api/jml/events")
    assert listed.status_code == 200
    assert [event["id"] for event in listed.get_json()["events"]] == [created["id"]]

    detail = client.get(f"/api/jml/events/{created['id']}")
    assert detail.status_code == 200, detail.get_json()
    assert len(detail.get_json()["checklist_items"]) == 3

    updated = client.patch(
        f"/api/jml/events/{created['id']}",
        json={"status": "In Progress"},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["event"]["status"] == "In Progress"


def test_read_endpoints_enforce_employee_scope(client):
    _login_as(client, "demo_hr_admin")
    own_event = _created_event(_create_event(client, employee_id=7))
    other_event = _created_event(_create_event(client, employee_id=6))

    _link("demo_hr_exec", 7)
    _login_as(client, "demo_hr_exec")
    listed = client.get("/api/jml/events")
    assert listed.status_code == 200
    assert [event["id"] for event in listed.get_json()["events"]] == [own_event["id"]]

    assert client.get(f"/api/jml/events/{other_event['id']}").status_code == 404
    assert client.get(f"/api/jml/events/{own_event['id']}").status_code == 200
    assert client.patch(
        f"/api/jml/events/{own_event['id']}", json={"status": "Completed"}
    ).status_code == 403


def test_manage_endpoints_enforce_employee_scope(client, monkeypatch):
    _login_as(client, "demo_hr_admin")
    scoped_event = _created_event(_create_event(client, employee_id=7))
    other_event = _created_event(_create_event(client, employee_id=6))
    connection = get_connection()
    try:
        other_item_id = connection.execute(
            "SELECT id FROM checklist_items WHERE jml_event_id = ? ORDER BY id LIMIT 1",
            (other_event["id"],),
        ).fetchone()["id"]
    finally:
        connection.close()

    username = _create_scoped_manager(monkeypatch, 7)
    _login_as(client, username)

    assert _create_event(client, employee_id=7).status_code == 201
    assert _create_event(client, employee_id=6).status_code == 404

    assert client.patch(
        f"/api/jml/events/{other_event['id']}", json={"status": "Completed"}
    ).status_code == 404
    assert client.patch(
        f"/api/jml/events/{other_event['id']}/checklist/{other_item_id}",
        json={"status": "Completed"},
    ).status_code == 404

    allowed = client.patch(
        f"/api/jml/events/{scoped_event['id']}", json={"status": "In Progress"}
    )
    assert allowed.status_code == 200, allowed.get_json()


def test_joiner_creation_and_completion(client):
    _login_as(client, "demo_hr_admin")
    assert _employee_row(6)["employment_status"] == "Pre-joining"

    created = _created_event(_create_event(client, employee_id=6, event_type="Joiner"))
    assert created["event_type"] == "Joiner"
    assert created["status"] == "Pending"
    assert created["checklist_total"] == 3
    assert created["checklist_done"] == 0

    detail = client.get(f"/api/jml/events/{created['id']}")
    assert detail.status_code == 200
    assert len(detail.get_json()["checklist_items"]) == 3
    assert _employee_row(6)["employment_status"] == "Pre-joining"

    in_progress = client.patch(
        f"/api/jml/events/{created['id']}", json={"status": "In Progress"}
    )
    assert in_progress.status_code == 200
    assert _employee_row(6)["employment_status"] == "Pre-joining"

    _complete_checklist(client, created["id"])
    completed = client.patch(
        f"/api/jml/events/{created['id']}", json={"status": "Completed"}
    )
    assert completed.status_code == 200, completed.get_json()
    assert completed.get_json()["event"]["status"] == "Completed"
    assert _employee_row(6)["employment_status"] == "Active"


def test_mover_updates_employee_and_records_history(client):
    _login_as(client, "demo_hr_admin")
    changes = {
        "department_id": 3,
        "designation_id": 5,
        "manager_id": 2,
        "location": "Pune",
    }

    created = _created_event(_create_event(
        client,
        employee_id=4,
        event_type="Mover",
        reason="Transfer to Finance",
        changes=changes,
    ))
    assert created["event_type"] == "Mover"
    assert created["checklist_total"] == 4

    # Changes are deferred: creating the event must not alter the employee.
    employee = _employee_row(4)
    assert employee["department_id"] == 2
    assert employee["designation_id"] == 3
    assert employee["manager_id"] == 1
    assert employee["location"] == "Hyderabad"
    assert _db_counts()[2] == 0

    detail = client.get(f"/api/jml/events/{created['id']}")
    assert detail.status_code == 200
    assert detail.get_json()["history"] == []

    _complete_checklist(client, created["id"])
    completed = client.patch(
        f"/api/jml/events/{created['id']}", json={"status": "Completed"}
    )
    assert completed.status_code == 200, completed.get_json()

    employee = _employee_row(4)
    assert employee["department_id"] == 3
    assert employee["designation_id"] == 5
    assert employee["manager_id"] == 2
    assert employee["location"] == "Pune"

    connection = get_connection()
    try:
        history = connection.execute(
            "SELECT * FROM employee_history WHERE employee_id = 4"
        ).fetchall()
    finally:
        connection.close()
    assert len(history) == 1
    assert history[0]["old_department_id"] == 2
    assert history[0]["new_department_id"] == 3
    assert history[0]["old_designation_id"] == 3
    assert history[0]["new_designation_id"] == 5
    assert history[0]["old_manager_id"] == 1
    assert history[0]["new_manager_id"] == 2
    assert history[0]["old_location"] == "Hyderabad"
    assert history[0]["new_location"] == "Pune"
    assert history[0]["effective_date"] == "2026-12-01"
    assert history[0]["change_reason"] == "Transfer to Finance"

    detail = client.get(f"/api/jml/events/{created['id']}")
    assert len(detail.get_json()["history"]) == 1
    assert _employee_row(4)["employment_status"] == "Active"


def test_leaver_creation_and_completion(client):
    _login_as(client, "demo_hr_admin")
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET exit_reason = ? WHERE id = 7",
            ("Untouched restricted field",),
        )
        connection.commit()
    finally:
        connection.close()

    created = _created_event(_create_event(
        client,
        employee_id=7,
        event_type="Leaver",
        reason="Resignation accepted",
    ))
    assert created["checklist_total"] == 4
    assert created["reason"] == "Resignation accepted"

    connection = get_connection()
    try:
        stored = connection.execute(
            "SELECT reason FROM jml_events WHERE id = ?", (created["id"],)
        ).fetchone()
    finally:
        connection.close()
    assert stored["reason"] == "Resignation accepted"
    assert _employee_row(7)["exit_reason"] == "Untouched restricted field"

    _complete_checklist(client, created["id"])
    completed = client.patch(
        f"/api/jml/events/{created['id']}", json={"status": "Completed"}
    )
    assert completed.status_code == 200, completed.get_json()
    assert _employee_row(7)["employment_status"] == "Exited"
    assert _employee_row(7)["exit_reason"] == "Untouched restricted field"


def test_checklist_status_updates_progress_and_timestamps(client):
    _login_as(client, "demo_hr_admin")
    created = _created_event(_create_event(client, event_type="Leaver"))
    event_id = created["id"]

    detail = client.get(f"/api/jml/events/{event_id}")
    item = detail.get_json()["checklist_items"][0]
    assert item["status"] == "Pending"
    assert item["completed_at"] is None

    completed = client.patch(
        f"/api/jml/events/{event_id}/checklist/{item['id']}",
        json={"status": "Completed"},
    )
    assert completed.status_code == 200, completed.get_json()
    body = completed.get_json()
    assert body["checklist_item"]["status"] == "Completed"
    assert body["checklist_item"]["completed_at"] is not None
    assert body["event"]["checklist_done"] == 1

    reopened = client.patch(
        f"/api/jml/events/{event_id}/checklist/{item['id']}",
        json={"status": "Pending"},
    )
    assert reopened.status_code == 200
    assert reopened.get_json()["checklist_item"]["completed_at"] is None
    assert reopened.get_json()["event"]["checklist_done"] == 0


def test_create_validation_rejects_bad_dates_types_and_fields(client):
    _login_as(client, "demo_hr_admin")

    bad_requests = [
        (_create_event(client, effective_date="2026-1-15"), "effective_date"),
        (_create_event(client, effective_date="not-a-date"), "YYYY-MM-DD"),
        (_create_event(client, event_type="Transfer"), "event_type"),
        (_create_event(client, employee_id=0), "employee_id"),
        (_create_event(client, event_type="Mover", changes=None), "changes"),
        (_create_event(client, event_type="Leaver", reason=None), "reason"),
        (_create_event(client, employee_id=99999), "Resource not found"),
    ]
    for response, expected_message in bad_requests:
        assert response.status_code in (400, 404), response.get_json()
        assert expected_message in json.dumps(response.get_json())

    unsupported = client.post(
        "/api/jml/events",
        json=_event_payload(employment_status="Active"),
    )
    assert unsupported.status_code == 400
    assert "Unsupported field" in unsupported.get_json()["message"]


def test_invalid_status_updates_are_rejected(client):
    _login_as(client, "demo_hr_admin")
    event = _created_event(_create_event(client))
    item_id = client.get(
        f"/api/jml/events/{event['id']}"
    ).get_json()["checklist_items"][0]["id"]

    bad_event_status = client.patch(
        f"/api/jml/events/{event['id']}", json={"status": "Done"}
    )
    assert bad_event_status.status_code == 400
    assert "status must be one of" in bad_event_status.get_json()["message"]

    bad_checklist_status = client.patch(
        f"/api/jml/events/{event['id']}/checklist/{item_id}",
        json={"status": "In Progress"},
    )
    assert bad_checklist_status.status_code == 400
    assert "status must be one of" in bad_checklist_status.get_json()["message"]

    missing_status = client.patch(
        f"/api/jml/events/{event['id']}", json={}
    )
    assert missing_status.status_code == 400


def test_failed_mover_creation_rolls_back_all_changes(client):
    _login_as(client, "demo_hr_admin")
    initial_counts = _db_counts()
    initial_employee = _employee_row(4)

    invalid_manager = _create_event(
        client,
        employee_id=4,
        event_type="Mover",
        changes={"manager_id": 99999},
    )
    assert invalid_manager.status_code == 400, invalid_manager.get_json()
    assert _db_counts() == initial_counts
    assert _employee_row(4)["manager_id"] == initial_employee["manager_id"]

    self_manager = _create_event(
        client,
        employee_id=4,
        event_type="Mover",
        changes={"manager_id": 4},
    )
    assert self_manager.status_code == 400
    assert "itself" in self_manager.get_json()["message"]
    assert _db_counts() == initial_counts
    assert _employee_row(4)["manager_id"] == initial_employee["manager_id"]


def test_exit_reason_is_visible_only_to_manage_permission(client):
    _login_as(client, "demo_hr_admin")
    event = _created_event(_create_event(
        client,
        employee_id=7,
        event_type="Leaver",
        reason="Confidential exit details",
    ))

    list_body = client.get("/api/jml/events").get_json()
    assert all("reason" not in item for item in list_body["events"])

    admin_detail = client.get(f"/api/jml/events/{event['id']}").get_json()
    assert admin_detail["event"]["reason"] == "Confidential exit details"

    _login_as(client, "demo_ceo")
    ceo_list = client.get("/api/jml/events").get_json()
    assert all("reason" not in item for item in ceo_list["events"])
    ceo_detail = client.get(f"/api/jml/events/{event['id']}")
    assert ceo_detail.status_code == 200
    assert "reason" not in ceo_detail.get_json()["event"]
    assert "Confidential exit details" not in json.dumps(ceo_detail.get_json())

    _link("demo_hr_exec", 7)
    _login_as(client, "demo_hr_exec")
    executive_detail = client.get(f"/api/jml/events/{event['id']}")
    assert executive_detail.status_code == 200
    assert "reason" not in executive_detail.get_json()["event"]
    assert "Confidential exit details" not in json.dumps(executive_detail.get_json())


def test_jml_responses_never_expose_restricted_fields(client):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET date_of_birth = ?, emergency_contact = ?, "
            "exit_reason = ? WHERE id = 7",
            ("1990-01-01", "Secret contact", "Secret exit reason"),
        )
        connection.execute(
            "INSERT INTO salary_records "
            "(employee_id, annual_salary, currency, effective_from) "
            "VALUES (?, ?, ?, ?)",
            (7, 900000, "INR", "2026-01-01"),
        )
        connection.commit()
    finally:
        connection.close()

    _login_as(client, "demo_hr_admin")
    event = _created_event(_create_event(
        client,
        employee_id=7,
        event_type="Leaver",
        reason="Restricted reason value",
    ))

    responses = [
        client.get("/api/jml/events"),
        client.get(f"/api/jml/events/{event['id']}"),
        client.patch(
            f"/api/jml/events/{event['id']}", json={"status": "In Progress"}
        ),
    ]
    for response in responses:
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        _assert_no_forbidden_fields(body)
        event_body = body["event"] if "event" in body else body["events"][0]
        _assert_public_employee(event_body["employee"])


def test_event_status_transitions_are_enforced(client):
    _login_as(client, "demo_hr_admin")

    cancelled = _created_event(_create_event(client))
    assert client.patch(
        f"/api/jml/events/{cancelled['id']}", json={"status": "Cancelled"}
    ).status_code == 200
    reopened = client.patch(
        f"/api/jml/events/{cancelled['id']}", json={"status": "In Progress"}
    )
    assert reopened.status_code == 400
    assert "Cannot change status from Cancelled" in reopened.get_json()["message"]

    completed = _created_event(_create_event(client))
    _complete_checklist(client, completed["id"])
    assert client.patch(
        f"/api/jml/events/{completed['id']}", json={"status": "Completed"}
    ).status_code == 200
    reopened = client.patch(
        f"/api/jml/events/{completed['id']}", json={"status": "In Progress"}
    )
    assert reopened.status_code == 400
    assert "Cannot change status from Completed" in reopened.get_json()["message"]

    pending = _created_event(_create_event(client))
    assert client.patch(
        f"/api/jml/events/{pending['id']}", json={"status": "In Progress"}
    ).status_code == 200
    assert client.patch(
        f"/api/jml/events/{pending['id']}", json={"status": "Cancelled"}
    ).status_code == 200


def test_completion_requires_all_checklist_items(client):
    _login_as(client, "demo_hr_admin")
    event = _created_event(_create_event(client, employee_id=6))

    blocked = client.patch(
        f"/api/jml/events/{event['id']}", json={"status": "Completed"}
    )
    assert blocked.status_code == 400
    assert "All checklist items must be completed" in blocked.get_json()["message"]
    assert _employee_row(6)["employment_status"] == "Pre-joining"

    _complete_checklist(client, event["id"])
    assert client.patch(
        f"/api/jml/events/{event['id']}", json={"status": "Completed"}
    ).status_code == 200
    assert _employee_row(6)["employment_status"] == "Active"


def test_leaver_completion_deactivates_only_linked_user(client):
    _link("demo_employee", 7)
    _login_as(client, "demo_employee")
    _link("demo_ceo", 1)
    _login_as(client, "demo_ceo")
    _login_as(client, "demo_hr_admin")

    event = _created_event(_create_event(
        client, employee_id=7, event_type="Leaver", reason="Resignation"
    ))
    early = client.patch(
        f"/api/jml/events/{event['id']}", json={"status": "Completed"}
    )
    assert early.status_code == 400

    _complete_checklist(client, event["id"])
    assert client.patch(
        f"/api/jml/events/{event['id']}", json={"status": "Completed"}
    ).status_code == 200

    connection = get_connection()
    try:
        active = {
            row["username"]: row["is_active"]
            for row in connection.execute(
                "SELECT username, is_active FROM users WHERE username IN (?, ?)",
                ("demo_employee", "demo_ceo"),
            )
        }
    finally:
        connection.close()
    assert active["demo_employee"] == 0
    assert active["demo_ceo"] == 1

    client.post("/api/auth/logout")
    denied = client.post(
        "/api/auth/login",
        json={"username": "demo_employee", "password": PASSWORD},
    )
    assert denied.status_code == 401, denied.get_json()


def test_cancelled_mover_leaves_employee_unchanged(client):
    _login_as(client, "demo_hr_admin")
    initial = _employee_row(4)
    event = _created_event(_create_event(
        client,
        employee_id=4,
        event_type="Mover",
        changes={"location": "Pune", "manager_id": 2},
    ))

    assert client.patch(
        f"/api/jml/events/{event['id']}", json={"status": "Cancelled"}
    ).status_code == 200
    current = _employee_row(4)
    assert current["location"] == initial["location"]
    assert current["manager_id"] == initial["manager_id"]
    assert _db_counts()[2] == 0


def test_mover_rejects_indirect_manager_cycle(client):
    _login_as(client, "demo_hr_admin")
    response = _create_event(
        client,
        employee_id=1,
        event_type="Mover",
        changes={"manager_id": 5},
    )
    assert response.status_code == 400, response.get_json()
    assert "circular reporting" in response.get_json()["message"]
