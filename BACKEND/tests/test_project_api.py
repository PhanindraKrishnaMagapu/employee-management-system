"""Tests for project endpoints, RBAC, scoping, validation, and safety.

Every test uses the isolated_db fixture through client, so the local SQLite
database is never opened by these requests.
"""

import json

import pytest

from app.auth import permissions as perms
from app.auth.context import CurrentUser
from app.db import get_connection
from app.services import projects as project_service
from app.services.authorization import (
    EMPLOYEE_PUBLIC_FIELDS,
    RESTRICTED_EMPLOYEE_FIELDS,
    SALARY_FIELDS,
    employee_scope,
)
from app.services.auth import hash_password


PASSWORD = "ProjectsTest!234"
ALL_FORBIDDEN_FIELDS = RESTRICTED_EMPLOYEE_FIELDS | SALARY_FIELDS

READ_ROLES = frozenset({
    perms.ROLE_CEO,
    perms.ROLE_HR_ADMIN,
    perms.ROLE_DEPARTMENT_MANAGER,
    perms.ROLE_PROJECT_MANAGER,
})
MANAGE_ROLES = frozenset({
    perms.ROLE_HR_ADMIN,
    perms.ROLE_PROJECT_MANAGER,
})
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


def _login_as(client, username):
    _set_password(username)
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.get_json()
    return response


def _create_payroll_test_user():
    username = "test_payroll_admin"
    connection = get_connection()
    try:
        role = connection.execute(
            "SELECT id FROM roles WHERE name = ?", (perms.ROLE_PAYROLL_ADMIN,)
        ).fetchone()
        connection.execute(
            "INSERT OR REPLACE INTO users "
            "(id, username, email, password_hash, employee_id) "
            "VALUES (?, ?, ?, ?, NULL)",
            (91, username, "project-test-payroll@example.invalid", "placeholder"),
        )
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (91,))
        connection.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (91, role["id"]),
        )
        connection.commit()
    finally:
        connection.close()
    return username


def _login_role(client, role, employee_id=None):
    if role == perms.ROLE_PAYROLL_ADMIN:
        username = _create_payroll_test_user()
    else:
        username = DEMO_USER_BY_ROLE[role]
        if employee_id is not None:
            _link(username, employee_id)
    _login_as(client, username)
    return username


def _make_user(role, employee_id=None):
    return CurrentUser(
        id=1,
        username="scope-test",
        email="scope-test@example.invalid",
        roles=(role,),
        employee_id=employee_id,
        permissions=perms.permissions_for_roles((role,)),
    )


def _project_payload(**overrides):
    payload = {
        "project_code": "PRJ-100",
        "name": "Portal Refresh",
        "description": "Internal portal upgrade",
        "status": "Planned",
        "start_date": "2026-09-01",
        "end_date": "2026-12-15",
    }
    payload.update(overrides)
    return payload


def _create_project(client, **overrides):
    return client.post("/api/projects", json=_project_payload(**overrides))


def _created_project(response):
    assert response.status_code == 201, response.get_json()
    return response.get_json()["project"]


def _set_project_manager(project_id, employee_id):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE projects SET manager_id = ? WHERE id = ?",
            (employee_id, project_id),
        )
        connection.commit()
    finally:
        connection.close()


def _assignment_payload(**overrides):
    payload = {
        "employee_id": 5,
        "start_date": "2026-09-01",
        "end_date": "2026-12-15",
        "allocation_percentage": 50,
    }
    payload.update(overrides)
    return payload


def _request(client, method, path):
    if method in ("POST", "PUT"):
        return client.open(path, method=method, json={})
    return client.open(path, method=method)


def _assert_public_employee(employee):
    assert set(employee) == set(EMPLOYEE_PUBLIC_FIELDS)


def _assert_no_forbidden_fields(body):
    text = json.dumps(body)
    for field in ALL_FORBIDDEN_FIELDS:
        assert f'"{field}"' not in text


def _set_secret_employee_fields():
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE employees SET date_of_birth = ?, emergency_contact = ?, "
            "exit_reason = ? WHERE id = ?",
            ("1990-01-01", "Secret contact", "Secret exit reason", 7),
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


def test_unauthenticated_project_endpoints_return_401(client):
    checks = [
        ("GET", "/api/projects"),
        ("GET", "/api/projects/1"),
        ("POST", "/api/projects"),
        ("PUT", "/api/projects/1"),
        ("GET", "/api/projects/1/employees"),
        ("GET", "/api/projects/assignable-employees"),
        ("POST", "/api/projects/1/assignments"),
        ("DELETE", "/api/projects/1/assignments/1"),
    ]

    for method, path in checks:
        response = _request(client, method, path)
        assert response.status_code == 401, (method, path, response.get_json())
        assert response.get_json()["message"] == "Authentication required"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_project_read_access_by_role(client, role):
    _login_role(client, role)

    response = client.get("/api/projects")

    if role in READ_ROLES:
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["projects"] == []
    else:
        assert response.status_code == 403, response.get_json()


@pytest.mark.parametrize("role", ALL_ROLES)
def test_project_detail_and_employee_access_by_role(client, role):
    _login_role(client, perms.ROLE_HR_ADMIN)
    project = _created_project(_create_project(client))
    _link("demo_project_manager", 5)
    _set_project_manager(project["id"], 5)
    _login_role(client, role)

    detail = client.get(f"/api/projects/{project['id']}")
    employees = client.get(f"/api/projects/{project['id']}/employees")

    if role in READ_ROLES:
        assert detail.status_code == 200, detail.get_json()
        assert employees.status_code == 200, employees.get_json()
    else:
        assert detail.status_code == 403
        assert employees.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_project_management_endpoints_by_role(client, role):
    _login_role(client, perms.ROLE_HR_ADMIN)
    project = _created_project(_create_project(client))
    _link("demo_project_manager", 5)
    _set_project_manager(project["id"], 5)
    assignment = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(),
    )
    assert assignment.status_code == 201, assignment.get_json()
    assignment_id = assignment.get_json()["assignment"]["id"]

    _login_role(client, role)
    create = _create_project(client, project_code="PRJ-OTHER")
    update = client.put(
        f"/api/projects/{project['id']}", json={"status": "In Progress"}
    )
    assign = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=7),
    )
    remove = client.delete(
        f"/api/projects/{project['id']}/assignments/{assignment_id}"
    )

    if role in MANAGE_ROLES:
        assert create.status_code == 201, create.get_json()
        assert update.status_code == 200, update.get_json()
        assert assign.status_code == 201, assign.get_json()
        assert remove.status_code == 200, remove.get_json()
    else:
        assert create.status_code == 403
        assert update.status_code == 403
        assert assign.status_code == 403
        assert remove.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_assignable_employees_access_by_role(client, role):
    _login_role(client, role)

    response = client.get("/api/projects/assignable-employees")

    if role in MANAGE_ROLES:
        assert response.status_code == 200, response.get_json()
        assert len(response.get_json()["employees"]) == 6
    else:
        assert response.status_code == 403


def test_project_manager_does_not_gain_general_employee_hierarchy_or_jml_access(client):
    _login_role(client, perms.ROLE_PROJECT_MANAGER, employee_id=5)

    assert client.get("/api/employees").status_code == 403
    assert client.get("/api/employees/5").status_code == 403
    assert client.get("/api/jml/events").status_code == 403
    assert client.get("/api/projects/assignable-employees").status_code == 200

    granted = perms.permissions_for_roles((perms.ROLE_PROJECT_MANAGER,))
    for denied in (
        perms.PERMISSION_EMPLOYEE_READ_SCOPE,
        perms.PERMISSION_EMPLOYEE_CREATE,
        perms.PERMISSION_EMPLOYEE_UPDATE,
        perms.PERMISSION_EMPLOYEE_ARCHIVE,
        perms.PERMISSION_JML_READ,
        perms.PERMISSION_JML_MANAGE,
    ):
        assert denied not in granted


def test_combined_project_manager_and_employee_role_keeps_self_access(client):
    _link("demo_project_manager", 5)
    _add_role("demo_project_manager", perms.ROLE_EMPLOYEE)
    _login_as(client, "demo_project_manager")

    employees = client.get("/api/employees")

    assert employees.status_code == 200, employees.get_json()
    assert [employee["id"] for employee in employees.get_json()["employees"]] == [5]
    assert client.get("/api/projects/assignable-employees").status_code == 200


def test_project_employee_scope_helper_does_not_change_shared_scope(isolated_db):
    connection = get_connection()
    try:
        manager = _make_user(perms.ROLE_PROJECT_MANAGER, employee_id=5)
        department_manager = _make_user(
            perms.ROLE_DEPARTMENT_MANAGER, employee_id=4
        )
        hr_admin = _make_user(perms.ROLE_HR_ADMIN)

        # Project Managers get org-wide visibility only through the project
        # helper; employee_scope() still resolves their linked record.
        assert project_service.visible_employee_ids(manager, connection) is None
        assert employee_scope(manager, connection) == frozenset({5})

        assert project_service.visible_employee_ids(
            department_manager, connection
        ) == frozenset({4, 5, 7})
        assert employee_scope(department_manager, connection) == frozenset({4, 5, 7})

        assert project_service.visible_employee_ids(hr_admin, connection) is None
        assert employee_scope(hr_admin, connection) is None
    finally:
        connection.close()


def test_project_manager_employee_picker_includes_all_active_employees(client):
    _link("demo_project_manager", 5)
    _login_as(client, "demo_project_manager")

    response = client.get("/api/projects/assignable-employees")

    assert response.status_code == 200, response.get_json()
    employees = response.get_json()["employees"]
    assert [employee["id"] for employee in employees] == [1, 2, 3, 4, 5, 7]
    for employee in employees:
        assert employee["employment_status"] == "Active"
        _assert_public_employee(employee)


def test_hr_admin_project_crud_and_code_conflicts(client):
    _login_as(client, "demo_hr_admin")

    created = _created_project(_create_project(client))
    assert set(created) == set(project_service.PROJECT_FIELDS) | {
        "assignment_count"
    }
    assert created["project_code"] == "PRJ-100"
    assert created["status"] == "Planned"
    assert created["is_active"] == 1
    assert created["assignment_count"] == 0

    listed = client.get("/api/projects")
    assert listed.status_code == 200, listed.get_json()
    assert [project["id"] for project in listed.get_json()["projects"]] == [
        created["id"]
    ]

    detail = client.get(f"/api/projects/{created['id']}")
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["project"]["name"] == "Portal Refresh"
    assert detail.get_json()["assignments"] == []

    updated = client.put(
        f"/api/projects/{created['id']}",
        json={
            "name": "Portal Refresh Phase 2",
            "status": "In Progress",
            "end_date": "2027-01-15",
        },
    )
    assert updated.status_code == 200, updated.get_json()
    body = updated.get_json()["project"]
    assert body["name"] == "Portal Refresh Phase 2"
    assert body["status"] == "In Progress"
    assert body["end_date"] == "2027-01-15"
    assert body["project_code"] == "PRJ-100"

    duplicate = _create_project(client)
    assert duplicate.status_code == 409
    assert duplicate.get_json()["message"] == "Project code already exists"

    missing = client.get("/api/projects/99999")
    assert missing.status_code == 404
    assert client.put("/api/projects/99999", json={"name": "No"}).status_code == 404


def test_project_payload_validation(client):
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client))

    bad_requests = [
        (client.post("/api/projects", json=[]), "JSON object"),
        (
            client.post("/api/projects", json={"name": "No code"}),
            "Missing required field(s): project_code",
        ),
        (
            client.post("/api/projects", json={"project_code": "  "}),
            "Missing required field(s): project_code, name",
        ),
        (_create_project(client, status="Done"), "status must be one of"),
        (
            _create_project(client, start_date="2026-1-15"),
            "YYYY-MM-DD",
        ),
        (
            _create_project(client, start_date="2026-10-01", end_date="2026-09-01"),
            "end_date cannot be earlier than start_date",
        ),
    ]
    for response, expected_message in bad_requests:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]

    unsupported = _create_project(client, is_active=0)
    assert unsupported.status_code == 400
    assert "Unsupported field" in unsupported.get_json()["message"]

    empty_update = client.put(f"/api/projects/{project['id']}", json={})
    assert empty_update.status_code == 400
    assert "At least one field" in empty_update.get_json()["message"]


def test_project_manager_can_manage_projects_and_assignments(client):
    _link("demo_project_manager", 5)
    _login_as(client, "demo_project_manager")

    project = _created_project(_create_project(client))
    updated = client.put(
        f"/api/projects/{project['id']}", json={"status": "On Hold"}
    )
    assert updated.status_code == 200, updated.get_json()

    assignment = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=7, allocation_percentage=75),
    )
    assert assignment.status_code == 201, assignment.get_json()
    body = assignment.get_json()["assignment"]
    assert body["project_id"] == project["id"]
    assert body["employee_id"] == 7
    assert body["allocation_percentage"] == 75
    _assert_public_employee(body["employee"])

    detail = client.get(f"/api/projects/{project['id']}")
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["project"]["assignment_count"] == 1
    assert len(detail.get_json()["assignments"]) == 1

    removed = client.delete(
        f"/api/projects/{project['id']}/assignments/{body['id']}"
    )
    assert removed.status_code == 200, removed.get_json()
    assert client.get(f"/api/projects/{project['id']}").get_json()[
        "assignments"
    ] == []


def test_assignments_list_visible_employees_and_reject_duplicates(client):
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client))

    assigned = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=5),
    )
    assert assigned.status_code == 201, assigned.get_json()
    assignment_id = assigned.get_json()["assignment"]["id"]

    employees = client.get(f"/api/projects/{project['id']}/employees")
    assert employees.status_code == 200, employees.get_json()
    assert [employee["id"] for employee in employees.get_json()["employees"]] == [5]
    _assert_public_employee(employees.get_json()["employees"][0])
    assert employees.get_json()["assignments"][0]["id"] == assignment_id

    duplicate = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=5),
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["message"] == (
        "Employee is already assigned to this project"
    )

    removed = client.delete(
        f"/api/projects/{project['id']}/assignments/{assignment_id}"
    )
    assert removed.status_code == 200, removed.get_json()
    assert client.delete(
        f"/api/projects/{project['id']}/assignments/{assignment_id}"
    ).status_code == 404

    after_removal = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=5),
    )
    assert after_removal.status_code == 201, after_removal.get_json()


def test_assignment_validation(client):
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client))
    url = f"/api/projects/{project['id']}/assignments"

    bad_requests = [
        (client.post(url, json=[]), "JSON object"),
        (client.post(url, json={"start_date": "2026-09-01"}), "employee_id"),
        (client.post(url, json={"employee_id": 5}), "start_date"),
        (client.post(url, json=_assignment_payload(employee_id=0)), "employee_id"),
        (
            client.post(url, json=_assignment_payload(employee_id="5")),
            "employee_id",
        ),
        (
            client.post(url, json=_assignment_payload(employee_id=99999)),
            "active employee",
        ),
        (
            client.post(url, json=_assignment_payload(employee_id=6)),
            "active employee",
        ),
        (
            client.post(url, json=_assignment_payload(start_date="2026-9-01")),
            "YYYY-MM-DD",
        ),
        (
            client.post(url, json=_assignment_payload(
                start_date="2026-10-01", end_date="2026-09-01"
            )),
            "end_date cannot be earlier than start_date",
        ),
        (
            client.post(url, json=_assignment_payload(allocation_percentage=0)),
            "allocation_percentage",
        ),
        (
            client.post(url, json=_assignment_payload(allocation_percentage=101)),
            "allocation_percentage",
        ),
        (
            client.post(url, json=_assignment_payload(allocation_percentage=True)),
            "allocation_percentage",
        ),
        (
            client.post(url, json=_assignment_payload(employee_code="DEMO005")),
            "Unsupported field",
        ),
    ]
    for response, expected_message in bad_requests:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]

    missing_project = client.post(
        "/api/projects/99999/assignments", json=_assignment_payload()
    )
    assert missing_project.status_code == 404

    defaulted = client.post(
        url,
        json={"employee_id": 5, "start_date": "2026-09-01"},
    )
    assert defaulted.status_code == 201, defaulted.get_json()
    assert defaulted.get_json()["assignment"]["allocation_percentage"] == 100.0


def test_archived_employee_is_rejected_for_new_assignments(client):
    _login_as(client, "demo_hr_admin")
    assert client.delete("/api/employees/7").status_code == 200
    project = _created_project(_create_project(client))
    _link("demo_project_manager", 5)
    _set_project_manager(project["id"], 5)

    _login_as(client, "demo_project_manager")
    response = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=7),
    )

    assert response.status_code == 400, response.get_json()
    assert "active employee" in response.get_json()["message"]


def test_department_manager_assignment_scope_filtering(client):
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client))
    for employee_id in (3, 5):
        response = client.post(
            f"/api/projects/{project['id']}/assignments",
            json=_assignment_payload(employee_id=employee_id),
        )
        assert response.status_code == 201, response.get_json()

    _login_role(client, perms.ROLE_DEPARTMENT_MANAGER, employee_id=4)

    listed = client.get("/api/projects")
    assert listed.status_code == 200, listed.get_json()
    assert listed.get_json()["projects"][0]["assignment_count"] == 1

    detail = client.get(f"/api/projects/{project['id']}")
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["project"]["assignment_count"] == 1
    scoped_assignments = detail.get_json()["assignments"]
    assert [item["employee_id"] for item in scoped_assignments] == [5]
    _assert_public_employee(scoped_assignments[0]["employee"])

    employees = client.get(f"/api/projects/{project['id']}/employees")
    assert employees.status_code == 200, employees.get_json()
    assert [employee["id"] for employee in employees.get_json()["employees"]] == [5]

    assert client.get("/api/projects/assignable-employees").status_code == 403
    out_of_scope = next(
        item for item in scoped_assignments if item["employee_id"] == 5
    )
    assert client.delete(
        f"/api/projects/{project['id']}/assignments/{out_of_scope['id']}"
    ).status_code == 403


def test_project_responses_never_expose_restricted_employee_fields(client):
    _set_secret_employee_fields()
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client))
    assignment = client.post(
        f"/api/projects/{project['id']}/assignments",
        json=_assignment_payload(employee_id=7),
    )
    assert assignment.status_code == 201, assignment.get_json()

    responses = [
        client.get("/api/projects"),
        client.get(f"/api/projects/{project['id']}"),
        client.get(f"/api/projects/{project['id']}/employees"),
        client.get("/api/projects/assignable-employees"),
        assignment,
    ]
    for response in responses:
        assert response.status_code in (200, 201), response.get_json()
        body = response.get_json()
        _assert_no_forbidden_fields(body)
        assert "Secret contact" not in json.dumps(body)
        assert "Secret exit reason" not in json.dumps(body)


def _login_project_manager(client, employee_id):
    _link("demo_project_manager", employee_id)
    _login_as(client, "demo_project_manager")


def test_project_manager_cannot_access_another_managers_project(client):
    """A PM is confined to projects whose manager_id is their linked employee."""

    _login_as(client, "demo_hr_admin")
    owned = _created_project(_create_project(client, project_code="PRJ-MINE"))
    other = _created_project(_create_project(client, project_code="PRJ-THEIRS"))
    _set_project_manager(owned["id"], 5)
    _set_project_manager(other["id"], 4)

    assignment = client.post(
        f"/api/projects/{other['id']}/assignments",
        json=_assignment_payload(employee_id=7),
    )
    assert assignment.status_code == 201, assignment.get_json()
    assignment_id = assignment.get_json()["assignment"]["id"]

    _login_project_manager(client, 5)

    assert [item["id"] for item in client.get("/api/projects").get_json()["projects"]] == [
        owned["id"]
    ]
    for method, path in (
        ("GET", f"/api/projects/{other['id']}"),
        ("GET", f"/api/projects/{other['id']}/employees"),
    ):
        assert client.open(path, method=method).status_code == 404, path

    assert client.put(
        f"/api/projects/{other['id']}", json={"status": "On Hold"}
    ).status_code == 404
    assert client.post(
        f"/api/projects/{other['id']}/assignments",
        json=_assignment_payload(employee_id=7),
    ).status_code == 404
    assert client.delete(
        f"/api/projects/{other['id']}/assignments/{assignment_id}"
    ).status_code == 404

    # The owned project remains fully manageable.
    assert client.get(f"/api/projects/{owned['id']}").status_code == 200
    assert client.put(
        f"/api/projects/{owned['id']}", json={"status": "In Progress"}
    ).status_code == 200


def test_project_manager_without_employee_link_cannot_manage_projects(client):
    _login_as(client, "demo_project_manager")

    assert client.get("/api/projects").get_json()["projects"] == []
    created = _create_project(client)
    assert created.status_code == 400
    assert "linked to an employee" in created.get_json()["message"]


def test_hr_admin_can_assign_project_manager_and_retains_org_wide_access(client):
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client, manager_id=5))

    assert project["manager_id"] == 5
    assert client.get(f"/api/projects/{project['id']}").status_code == 200
    assert client.put(
        f"/api/projects/{project['id']}", json={"manager_id": 4}
    ).status_code == 200
    assert client.get(f"/api/projects/{project['id']}").get_json()["project"][
        "manager_id"
    ] == 4


def test_ceo_and_department_manager_retain_project_read_access(client):
    _login_as(client, "demo_hr_admin")
    project = _created_project(_create_project(client, manager_id=5))

    for role, employee_id in (
        (perms.ROLE_CEO, None),
        (perms.ROLE_DEPARTMENT_MANAGER, 4),
    ):
        _login_role(client, role, employee_id)
        response = client.get("/api/projects")
        assert response.status_code == 200, response.get_json()
        assert [item["id"] for item in response.get_json()["projects"]] == [
            project["id"]
        ]
        assert client.get(f"/api/projects/{project['id']}").status_code == 200
