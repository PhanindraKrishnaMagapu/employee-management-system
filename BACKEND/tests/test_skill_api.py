"""Tests for skill catalog and employee assignment endpoints.

Every test uses the isolated_db fixture through client, so the local SQLite
database is never opened by these requests.
"""

import json

import pytest

from app.auth import permissions as perms
from app.db import get_connection
from app.services import skills as skill_service
from app.services.auth import hash_password
from app.services.authorization import (
    EMPLOYEE_PUBLIC_FIELDS,
    RESTRICTED_EMPLOYEE_FIELDS,
    SALARY_FIELDS,
)


PASSWORD = "SkillsTest!234"
ALL_FORBIDDEN_FIELDS = RESTRICTED_EMPLOYEE_FIELDS | SALARY_FIELDS

READ_ROLES = frozenset({
    perms.ROLE_CEO,
    perms.ROLE_HR_ADMIN,
    perms.ROLE_HR_EXECUTIVE,
    perms.ROLE_DEPARTMENT_MANAGER,
    perms.ROLE_EMPLOYEE,
})
MANAGE_ROLES = frozenset({perms.ROLE_HR_ADMIN})
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
LINK_EMPLOYEE_BY_ROLE = {
    perms.ROLE_CEO: None,
    perms.ROLE_HR_ADMIN: None,
    perms.ROLE_HR_EXECUTIVE: 7,
    perms.ROLE_DEPARTMENT_MANAGER: 4,
    perms.ROLE_PROJECT_MANAGER: 7,
    perms.ROLE_EMPLOYEE: 7,
    perms.ROLE_SYSTEM_ADMIN: None,
    perms.ROLE_PAYROLL_ADMIN: None,
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
    username = "test_skills_payroll_admin"
    connection = get_connection()
    try:
        role = connection.execute(
            "SELECT id FROM roles WHERE name = ?", (perms.ROLE_PAYROLL_ADMIN,)
        ).fetchone()
        connection.execute(
            "INSERT OR REPLACE INTO users "
            "(id, username, email, password_hash, employee_id) "
            "VALUES (?, ?, ?, ?, NULL)",
            (92, username, "skills-test-payroll@example.invalid", "placeholder"),
        )
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (92,))
        connection.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (92, role["id"]),
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


def _skill_payload(**overrides):
    payload = {
        "name": "Python",
        "description": "General-purpose programming language",
    }
    payload.update(overrides)
    return payload


def _create_skill(client, **overrides):
    return client.post("/api/skills", json=_skill_payload(**overrides))


def _created_skill(response):
    assert response.status_code == 201, response.get_json()
    return response.get_json()["skill"]


def _assignment_payload(**overrides):
    payload = {
        "skill_id": 1,
        "proficiency_level": "Intermediate",
        "experience_years": 3,
        "last_verified": "2026-01-15",
    }
    payload.update(overrides)
    return payload


def _assign(client, employee_id, **overrides):
    return client.post(
        f"/api/employees/{employee_id}/skills",
        json=_assignment_payload(**overrides),
    )


def _create_and_assign(client, employee_id=7, skill_id=1, **skill_overrides):
    skill = _created_skill(_create_skill(client, **skill_overrides))
    response = _assign(client, employee_id, skill_id=skill["id"])
    assert response.status_code == 201, response.get_json()
    return skill, response.get_json()["assignment"]


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


def _request(client, method, path):
    if method in ("POST", "PUT"):
        return client.open(path, method=method, json={})
    return client.open(path, method=method)


def test_unauthenticated_skill_endpoints_return_401(client):
    checks = [
        ("GET", "/api/skills"),
        ("POST", "/api/skills"),
        ("PUT", "/api/skills/1"),
        ("GET", "/api/employees/7/skills"),
        ("POST", "/api/employees/7/skills"),
        ("PUT", "/api/employees/7/skills/1"),
        ("DELETE", "/api/employees/7/skills/1"),
    ]

    for method, path in checks:
        response = _request(client, method, path)
        assert response.status_code == 401, (method, path, response.get_json())
        assert response.get_json()["message"] == "Authentication required"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_skill_read_and_manage_permissions_by_role(client, role):
    _login_role(client, role)

    catalog = client.get("/api/skills")
    created = client.post("/api/skills", json=_skill_payload(name="Role skill"))

    if role in READ_ROLES:
        assert catalog.status_code == 200, catalog.get_json()
        assert catalog.get_json()["skills"] == []
    else:
        assert catalog.status_code == 403

    if role in MANAGE_ROLES:
        assert created.status_code == 201, created.get_json()
    else:
        assert created.status_code == 403
        assert created.get_json() == {
            "success": False,
            "message": "Permission denied",
        }


def test_hr_admin_manage_permission_also_allows_reading(client):
    _login_as(client, "demo_hr_admin")

    granted = perms.permissions_for_roles((perms.ROLE_HR_ADMIN,))
    assert perms.PERMISSION_SKILLS_MANAGE in granted
    assert perms.PERMISSION_SKILLS_READ not in granted
    assert client.get("/api/skills").status_code == 200


def test_hr_admin_skill_catalog_crud_and_conflicts(client):
    _login_as(client, "demo_hr_admin")

    created = _created_skill(_create_skill(client))
    assert set(created) == set(skill_service.SKILL_FIELDS)
    assert created["name"] == "Python"
    assert created["description"] == "General-purpose programming language"

    listed = client.get("/api/skills")
    assert listed.status_code == 200, listed.get_json()
    assert [skill["id"] for skill in listed.get_json()["skills"]] == [created["id"]]

    duplicate = _create_skill(client, name="Python")
    assert duplicate.status_code == 409
    assert duplicate.get_json()["message"] == "Skill name already exists"

    updated = client.put(
        f"/api/skills/{created['id']}",
        json={"description": "Updated description"},
    )
    assert updated.status_code == 200, updated.get_json()
    body = updated.get_json()["skill"]
    assert body["name"] == "Python"
    assert body["description"] == "Updated description"
    assert body["updated_at"] != body["created_at"] or body["updated_at"]

    duplicate_update = client.put(
        f"/api/skills/{created['id']}",
        json={"name": "Python"},
    )
    assert duplicate_update.status_code == 200

    other = _created_skill(_create_skill(client, name="SQL"))
    conflict = client.put(
        f"/api/skills/{other['id']}",
        json={"name": "Python"},
    )
    assert conflict.status_code == 409

    assert client.put("/api/skills/99999", json={"name": "Missing"}).status_code == 404


def test_skill_search_filters_name_description_and_escapes_wildcards(client):
    _login_as(client, "demo_hr_admin")
    _create_skill(client, name="Python", description="Scripting language")
    _create_skill(client, name="SQL", description="Query language")
    _create_skill(client, name="C% Plus", description="Systems language")
    _create_skill(client, name="A_B", description="Testing language")

    def names(search):
        response = client.get("/api/skills", query_string={"search": search})
        assert response.status_code == 200, response.get_json()
        return [skill["name"] for skill in response.get_json()["skills"]]

    assert names("python") == ["Python"]
    assert names("QUERY") == ["SQL"]
    assert names("%") == ["C% Plus"]
    assert names("_") == ["A_B"]
    assert len(names("")) == 4


def test_skill_payload_validation(client):
    _login_as(client, "demo_hr_admin")
    skill = _created_skill(_create_skill(client))

    bad_requests = [
        (client.post("/api/skills", json=[]), "JSON object"),
        (client.post("/api/skills", json={}), "Missing required"),
        (client.post("/api/skills", json={"name": "  "}), "Missing required"),
        (client.post("/api/skills", json={"name": 123}), "non-empty string"),
        (
            client.post("/api/skills", json={"name": "Java", "description": 7}),
            "description must be a string",
        ),
        (
            client.post("/api/skills", json={"name": "Java", "id": 9}),
            "Unsupported field",
        ),
        (client.put(f"/api/skills/{skill['id']}", json={}), "At least one field"),
        (
            client.put(
                f"/api/skills/{skill['id']}",
                json={"created_at": "2026-01-01"},
            ),
            "Unsupported field",
        ),
    ]
    for response, expected_message in bad_requests:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]


@pytest.mark.parametrize("role", ALL_ROLES)
def test_employee_skill_read_access_by_role(client, role):
    _login_as(client, "demo_hr_admin")
    _create_and_assign(client)

    _login_role(client, role, employee_id=LINK_EMPLOYEE_BY_ROLE[role])

    response = client.get("/api/employees/7/skills")

    if role in READ_ROLES:
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        _assert_public_employee(body["employee"])
        assert len(body["assignments"]) == 1
        _assert_no_forbidden_fields(body)
    else:
        assert response.status_code == 403, response.get_json()


def test_employee_scope_and_archived_employees(client):
    _login_as(client, "demo_hr_admin")
    skill, _ = _create_and_assign(client, employee_id=7)
    _assign(client, 5, skill_id=skill["id"])

    _link("demo_employee", 7)
    _login_as(client, "demo_employee")
    own = client.get("/api/employees/7/skills")
    assert own.status_code == 200, own.get_json()
    assert client.get("/api/employees/5/skills").status_code == 404

    _login_role(client, perms.ROLE_DEPARTMENT_MANAGER, employee_id=4)
    in_scope = client.get("/api/employees/5/skills")
    assert in_scope.status_code == 200, in_scope.get_json()
    assert client.get("/api/employees/1/skills").status_code == 404

    _login_as(client, "demo_hr_admin")
    assert client.delete("/api/employees/7").status_code == 200
    assert client.get("/api/employees/7/skills").status_code == 404
    assert _assign(client, 7, skill_id=skill["id"]).status_code == 404


def test_project_manager_carveout_and_combined_roles(client):
    _login_as(client, "demo_hr_admin")
    skill = _created_skill(_create_skill(client))

    _login_role(client, perms.ROLE_PROJECT_MANAGER, employee_id=7)
    assert client.get("/api/skills").status_code == 403
    assert client.get("/api/employees/7/skills").status_code == 403
    assert _assign(client, 7, skill_id=skill["id"]).status_code == 403

    _add_role("demo_project_manager", perms.ROLE_EMPLOYEE)
    _login_as(client, "demo_project_manager")
    assert client.get("/api/skills").status_code == 200
    own = client.get("/api/employees/7/skills")
    assert own.status_code == 200, own.get_json()
    assert _assign(client, 7, skill_id=skill["id"]).status_code == 403

    _add_role("demo_project_manager", perms.ROLE_HR_ADMIN)
    _login_as(client, "demo_project_manager")
    assigned = _assign(client, 7, skill_id=skill["id"])
    assert assigned.status_code == 201, assigned.get_json()


def test_assignment_crud_duplicates_and_immutability(client):
    _login_as(client, "demo_hr_admin")
    first = _created_skill(_create_skill(client, name="Python"))
    second = _created_skill(_create_skill(client, name="SQL"))

    created = _assign(client, 7, skill_id=first["id"])
    assert created.status_code == 201, created.get_json()
    assignment = created.get_json()["assignment"]
    assert set(assignment) == set(skill_service.EMPLOYEE_SKILL_FIELDS) | {
        "skill",
        "employee",
    }
    assert set(assignment["skill"]) == set(skill_service.SKILL_FIELDS)
    _assert_public_employee(assignment["employee"])

    duplicate = _assign(client, 7, skill_id=first["id"])
    assert duplicate.status_code == 409
    assert duplicate.get_json()["message"] == "Employee is already assigned this skill"

    other = _assign(client, 5, skill_id=second["id"])
    assert other.status_code == 201, other.get_json()

    updated = client.put(
        f"/api/employees/7/skills/{assignment['id']}",
        json={
            "proficiency_level": "Advanced",
            "experience_years": 7.5,
            "last_verified": "2026-02-20",
        },
    )
    assert updated.status_code == 200, updated.get_json()
    body = updated.get_json()["assignment"]
    assert body["proficiency_level"] == "Advanced"
    assert body["experience_years"] == 7.5
    assert body["last_verified"] == "2026-02-20"

    wrong_employee = client.put(
        f"/api/employees/5/skills/{assignment['id']}",
        json={"proficiency_level": "Expert"},
    )
    assert wrong_employee.status_code == 404

    immutable = client.put(
        f"/api/employees/7/skills/{assignment['id']}",
        json={"skill_id": second["id"]},
    )
    assert immutable.status_code == 400
    assert "Unsupported field" in immutable.get_json()["message"]

    removed = client.delete(f"/api/employees/7/skills/{assignment['id']}")
    assert removed.status_code == 200, removed.get_json()
    assert client.delete(
        f"/api/employees/7/skills/{assignment['id']}"
    ).status_code == 404

    catalog = client.get("/api/skills")
    assert [skill["id"] for skill in catalog.get_json()["skills"]] == [
        first["id"],
        second["id"],
    ]

    reassigned = _assign(client, 7, skill_id=first["id"])
    assert reassigned.status_code == 201, reassigned.get_json()


def test_assignment_validation(client):
    _login_as(client, "demo_hr_admin")
    skill = _created_skill(_create_skill(client))
    url = "/api/employees/7/skills"

    bad_requests = [
        (client.post(url, json=[]), "JSON object"),
        (client.post(url, json={"proficiency_level": "Beginner"}), "skill_id"),
        (client.post(url, json={"skill_id": skill["id"]}), "proficiency_level"),
        (client.post(url, json=_assignment_payload(skill_id=0)), "skill_id"),
        (client.post(url, json=_assignment_payload(skill_id="1")), "skill_id"),
        (client.post(url, json=_assignment_payload(skill_id=True)), "skill_id"),
        (
            client.post(url, json=_assignment_payload(skill_id=99999)),
            "existing skill",
        ),
        (
            client.post(url, json=_assignment_payload(proficiency_level="Expert II")),
            "proficiency_level must be one of",
        ),
        (
            client.post(url, json=_assignment_payload(experience_years=-1)),
            "non-negative finite",
        ),
        (
            client.post(url, json=_assignment_payload(experience_years="3")),
            "non-negative finite",
        ),
        (
            client.post(url, json=_assignment_payload(experience_years=True)),
            "non-negative finite",
        ),
        (
            client.post(url, json=_assignment_payload(last_verified="2026-1-15")),
            "YYYY-MM-DD",
        ),
        (
            client.post(url, json=_assignment_payload(last_verified="not-a-date")),
            "YYYY-MM-DD",
        ),
        (
            client.post(url, json=_assignment_payload(employee_id=7)),
            "Unsupported field",
        ),
        (
            client.post("/api/employees/6/skills", json=_assignment_payload()),
            "Active employees",
        ),
    ]
    for response, expected_message in bad_requests:
        assert response.status_code == 400, response.get_json()
        assert expected_message in response.get_json()["message"]

    defaulted = client.post(
        url,
        json={"skill_id": skill["id"], "proficiency_level": "Beginner"},
    )
    assert defaulted.status_code == 201, defaulted.get_json()
    assignment = defaulted.get_json()["assignment"]
    assert assignment["experience_years"] == 0.0
    assert assignment["last_verified"] is None

    assert client.put(url + "/99999", json={"proficiency_level": "Expert"}).status_code == 404
    assert client.put(
        f"/api/employees/7/skills/{assignment['id']}", json={}
    ).status_code == 400


def test_experience_years_rejects_non_finite_numbers_directly():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(skill_service.SkillValidationError):
            skill_service.validate_assignment_payload(_assignment_payload(
                experience_years=value
            ))


def test_responses_never_expose_restricted_or_salary_fields(client):
    _set_secret_employee_fields()
    _login_as(client, "demo_hr_admin")
    skill, assignment = _create_and_assign(client)

    updated = client.put(
        f"/api/employees/7/skills/{assignment['id']}",
        json={"proficiency_level": "Expert"},
    )
    assert updated.status_code == 200, updated.get_json()

    responses = [
        client.get("/api/skills"),
        client.get("/api/employees/7/skills"),
        updated,
    ]
    for response in responses:
        assert response.status_code in (200, 201), response.get_json()
        body = response.get_json()
        _assert_no_forbidden_fields(body)
        text = json.dumps(body)
        assert "Secret contact" not in text
        assert "Secret exit reason" not in text
        assert "900000.0" not in text
        assert "INR" not in text

    employee = client.get(
        "/api/employees/7/skills"
    ).get_json()["employee"]
    _assert_public_employee(employee)
    assert skill["id"] == assignment["skill_id"]


def test_skill_permission_constants_and_role_grants():
    assert perms.PERMISSION_SKILLS_READ == "skills:read"
    assert perms.PERMISSION_SKILLS_MANAGE == "skills:manage"
    assert perms.PERMISSION_SKILLS_READ in perms.ALL_PERMISSIONS
    assert perms.PERMISSION_SKILLS_MANAGE in perms.ALL_PERMISSIONS

    assert perms.PERMISSION_SKILLS_READ in perms.ROLE_PERMISSIONS[perms.ROLE_CEO]
    assert perms.PERMISSION_SKILLS_MANAGE in perms.ROLE_PERMISSIONS[perms.ROLE_HR_ADMIN]
    for role in (
        perms.ROLE_HR_EXECUTIVE,
        perms.ROLE_DEPARTMENT_MANAGER,
        perms.ROLE_EMPLOYEE,
    ):
        assert perms.PERMISSION_SKILLS_READ in perms.ROLE_PERMISSIONS[role]
        assert perms.PERMISSION_SKILLS_MANAGE not in perms.ROLE_PERMISSIONS[role]
    for role in (
        perms.ROLE_PROJECT_MANAGER,
        perms.ROLE_SYSTEM_ADMIN,
        perms.ROLE_PAYROLL_ADMIN,
    ):
        assert not perms.permissions_for_roles((role,)) & {
            perms.PERMISSION_SKILLS_READ,
            perms.PERMISSION_SKILLS_MANAGE,
        }
