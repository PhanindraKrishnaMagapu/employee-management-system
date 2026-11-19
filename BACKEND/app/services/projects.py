"""Project validation, serialization, and database helpers."""

import math
from datetime import datetime

from app.auth.permissions import (
    PERMISSION_EMPLOYEE_READ_ALL,
    ROLE_HR_ADMIN,
    ROLE_PROJECT_MANAGER,
)
from app.services.authorization import (
    EMPLOYEE_PUBLIC_FIELDS,
    employee_scope,
)


PROJECT_STATUSES = frozenset({
    "Planned",
    "In Progress",
    "Completed",
    "On Hold",
})

PROJECT_FIELDS = (
    "id",
    "project_code",
    "name",
    "description",
    "status",
    "start_date",
    "end_date",
    "manager_id",
    "is_active",
    "created_at",
    "updated_at",
)
ASSIGNMENT_FIELDS = (
    "id",
    "project_id",
    "employee_id",
    "start_date",
    "end_date",
    "allocation_percentage",
    "created_at",
    "updated_at",
)

PROJECT_PAYLOAD_FIELDS = frozenset({
    "project_code",
    "name",
    "description",
    "status",
    "start_date",
    "end_date",
    "manager_id",
})
REQUIRED_PROJECT_FIELDS = ("project_code", "name")
ASSIGNMENT_PAYLOAD_FIELDS = frozenset({
    "employee_id",
    "start_date",
    "end_date",
    "allocation_percentage",
})


class ProjectValidationError(ValueError):
    """Raised when a project payload contains invalid data."""


def _columns(fields):
    return ", ".join(fields)


def _placeholders(values):
    return ", ".join("?" for _ in values)


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProjectValidationError(f"{field} must be a string")
    return value.strip() or None


def _date(value, field):
    if not isinstance(value, str):
        raise ProjectValidationError(f"{field} must be a YYYY-MM-DD date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise ProjectValidationError(
            f"{field} must be a valid YYYY-MM-DD date"
        ) from error
    if parsed.isoformat() != value:
        raise ProjectValidationError(f"{field} must be a valid YYYY-MM-DD date")
    return value


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProjectValidationError(f"{field} must be a positive integer")
    return value


def _allocation(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectValidationError(
            "allocation_percentage must be greater than 0 and at most 100"
        )
    number = float(value)
    if not math.isfinite(number) or number <= 0 or number > 100:
        raise ProjectValidationError(
            "allocation_percentage must be greater than 0 and at most 100"
        )
    return number


def _unknown_fields(payload, allowed_fields):
    unknown = set(payload) - set(allowed_fields)
    if unknown:
        raise ProjectValidationError(
            "Unsupported field(s): " + ", ".join(sorted(unknown))
        )


def _current_value(current, field):
    return current[field] if current is not None else None


def _validate_date_range(values, current):
    start_date = values.get(
        "start_date", _current_value(current, "start_date")
    )
    end_date = values.get("end_date", _current_value(current, "end_date"))
    if start_date and end_date and end_date < start_date:
        raise ProjectValidationError("end_date cannot be earlier than start_date")


def project_scope(user):
    """Return manager employee ids a caller may access, or None for all.

    HR Admin keeps organization-wide project management. Project Managers are
    confined to projects whose manager_id is their linked employee id. Other
    roles (CEO, Department Manager) keep their existing read-only visibility.
    """

    if user is None:
        return frozenset()
    if ROLE_HR_ADMIN in user.roles:
        return None
    if ROLE_PROJECT_MANAGER in user.roles:
        if user.employee_id is None:
            return frozenset()
        return frozenset({user.employee_id})
    return None


def can_access_project(user, project_row):
    """Return True when the caller may view or manage this project."""

    scope = project_scope(user)
    return scope is None or project_row["manager_id"] in scope


def visible_projects(connection, user):
    """Return active projects filtered to the caller's project scope."""

    return [
        row for row in list_projects(connection)
        if can_access_project(user, row)
    ]


def validate_project_payload(payload, current=None):
    """Validate and normalize a project create or partial update payload."""

    if not isinstance(payload, dict):
        raise ProjectValidationError("Request body must be a JSON object")
    _unknown_fields(payload, PROJECT_PAYLOAD_FIELDS)

    is_update = current is not None
    if is_update and not payload:
        raise ProjectValidationError("At least one field is required")

    if not is_update:
        missing = [
            field for field in REQUIRED_PROJECT_FIELDS if _blank(payload.get(field))
        ]
        if missing:
            raise ProjectValidationError(
                "Missing required field(s): " + ", ".join(missing)
            )

    values = {}
    if "project_code" in payload:
        values["project_code"] = _required_string(
            payload["project_code"], "project_code"
        )
    if "name" in payload:
        values["name"] = _required_string(payload["name"], "name")
    if "description" in payload:
        values["description"] = _optional_string(
            payload["description"], "description"
        )
    if "status" in payload:
        status = _required_string(payload["status"], "status")
        if status not in PROJECT_STATUSES:
            raise ProjectValidationError(
                "status must be one of: " + ", ".join(sorted(PROJECT_STATUSES))
            )
        values["status"] = status
    elif not is_update:
        values["status"] = "Planned"

    for field in ("start_date", "end_date"):
        if field in payload:
            values[field] = (
                None if payload[field] is None else _date(payload[field], field)
            )

    if "manager_id" in payload:
        values["manager_id"] = (
            None if payload["manager_id"] is None
            else _positive_int(payload["manager_id"], "manager_id")
        )

    _validate_date_range(values, current)
    return values


def validate_assignment_payload(payload):
    """Validate and normalize an assignment create payload."""

    if not isinstance(payload, dict):
        raise ProjectValidationError("Request body must be a JSON object")
    _unknown_fields(payload, ASSIGNMENT_PAYLOAD_FIELDS)

    missing = [
        field for field in ("employee_id", "start_date")
        if _blank(payload.get(field))
    ]
    if missing:
        raise ProjectValidationError(
            "Missing required field(s): " + ", ".join(missing)
        )

    values = {
        "employee_id": _positive_int(payload["employee_id"], "employee_id"),
        "start_date": _date(payload["start_date"], "start_date"),
        "end_date": (
            None if _blank(payload.get("end_date"))
            else _date(payload["end_date"], "end_date")
        ),
        "allocation_percentage": (
            100.0 if "allocation_percentage" not in payload
            else _allocation(payload["allocation_percentage"])
        ),
    }
    _validate_date_range(values, None)
    return values


def visible_employee_ids(user, connection):
    """Return employee ids visible for project work, or None for all.

    Project Managers receive employees:read:all for the project employee
    picker only. This helper honors that permission without changing the
    shared role-based employee_scope() used by Employees, Hierarchy and JML.
    """

    if user is None:
        return frozenset()
    if PERMISSION_EMPLOYEE_READ_ALL in user.permissions:
        return None
    return employee_scope(user, connection)


def list_projects(connection):
    """Return active projects, newest first."""

    return connection.execute(
        f"SELECT {_columns(PROJECT_FIELDS)} FROM projects "
        "WHERE is_active = 1 ORDER BY id DESC"
    ).fetchall()


def get_project(connection, project_id):
    """Return one active project, or None."""

    return connection.execute(
        f"SELECT {_columns(PROJECT_FIELDS)} FROM projects "
        "WHERE id = ? AND is_active = 1",
        (project_id,),
    ).fetchone()


def serialize_project(row, assignment_count=0):
    """Build the JSON representation of one project."""

    result = {field: row[field] for field in PROJECT_FIELDS}
    result["assignment_count"] = int(assignment_count or 0)
    return result


def assignment_counts(connection, project_ids, visible_ids=None):
    """Return {project_id: count} for the caller's visible assignments."""

    project_ids = tuple(project_ids)
    if not project_ids:
        return {}
    if visible_ids is not None:
        visible_ids = tuple(visible_ids)
        if not visible_ids:
            return {}

    parameters = list(project_ids)
    sql = (
        "SELECT project_id, COUNT(*) AS total FROM project_assignments "
        f"WHERE project_id IN ({_placeholders(project_ids)})"
    )
    if visible_ids is not None:
        sql += f" AND employee_id IN ({_placeholders(visible_ids)})"
        parameters.extend(visible_ids)
    sql += " GROUP BY project_id"

    rows = connection.execute(sql, tuple(parameters)).fetchall()
    return {row["project_id"]: row["total"] for row in rows}


def get_employee_public(connection, employee_id):
    """Return an employee using the shared public-field allowlist."""

    row = connection.execute(
        f"SELECT {_columns(EMPLOYEE_PUBLIC_FIELDS)} FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()
    return {field: row[field] for field in EMPLOYEE_PUBLIC_FIELDS} if row else None


def list_assignments(connection, project_id, visible_ids=None):
    """Return a project's assignments that are visible to the caller."""

    parameters = [project_id]
    sql = (
        f"SELECT {_columns(ASSIGNMENT_FIELDS)} FROM project_assignments "
        "WHERE project_id = ?"
    )
    if visible_ids is not None:
        visible_ids = tuple(visible_ids)
        if not visible_ids:
            return []
        sql += f" AND employee_id IN ({_placeholders(visible_ids)})"
        parameters.extend(visible_ids)
    sql += " ORDER BY id"

    return connection.execute(sql, tuple(parameters)).fetchall()


def get_assignment(connection, project_id, assignment_id, visible_ids=None):
    """Return one assignment only when it belongs to this project and scope."""

    parameters = [assignment_id, project_id]
    sql = (
        f"SELECT {_columns(ASSIGNMENT_FIELDS)} FROM project_assignments "
        "WHERE id = ? AND project_id = ?"
    )
    if visible_ids is not None:
        visible_ids = tuple(visible_ids)
        if not visible_ids:
            return None
        sql += f" AND employee_id IN ({_placeholders(visible_ids)})"
        parameters.extend(visible_ids)

    return connection.execute(sql, tuple(parameters)).fetchone()


def serialize_assignment(row, employee):
    """Build the JSON representation of one assignment."""

    result = {field: row[field] for field in ASSIGNMENT_FIELDS}
    result["employee"] = employee
    return result


def list_assignable_employees(connection, visible_ids=None):
    """Return active employees who may be assigned to a project."""

    parameters = []
    sql = (
        f"SELECT {_columns(EMPLOYEE_PUBLIC_FIELDS)} FROM employees "
        "WHERE archived_at IS NULL AND employment_status = 'Active'"
    )
    if visible_ids is not None:
        visible_ids = tuple(visible_ids)
        if not visible_ids:
            return []
        sql += f" AND id IN ({_placeholders(visible_ids)})"
        parameters.extend(visible_ids)
    sql += " ORDER BY id"

    rows = connection.execute(sql, tuple(parameters)).fetchall()
    return [
        {field: row[field] for field in EMPLOYEE_PUBLIC_FIELDS}
        for row in rows
    ]


def active_employee_exists(connection, employee_id):
    """Return True when the id references a current active employee."""

    row = connection.execute(
        "SELECT id FROM employees "
        "WHERE id = ? AND archived_at IS NULL AND employment_status = 'Active'",
        (employee_id,),
    ).fetchone()
    return row is not None


def assignment_exists(connection, project_id, employee_id):
    """Return True when this employee already has an assignment here."""

    row = connection.execute(
        "SELECT id FROM project_assignments "
        "WHERE project_id = ? AND employee_id = ?",
        (project_id, employee_id),
    ).fetchone()
    return row is not None


def create_project(connection, values):
    """Insert a project in the caller's transaction."""

    columns = (
        "project_code",
        "name",
        "description",
        "status",
        "start_date",
        "end_date",
        "manager_id",
    )
    parameters = tuple(values.get(field) for field in columns)
    cursor = connection.execute(
        f"INSERT INTO projects ({_columns(columns)}) "
        f"VALUES ({_placeholders(parameters)})",
        parameters,
    )
    return get_project(connection, cursor.lastrowid)


def update_project(connection, project_id, values):
    """Update allowed project fields in the caller's transaction."""

    assignments = [f"{field} = ?" for field in values]
    parameters = list(values.values()) + [project_id]
    connection.execute(
        "UPDATE projects SET " + ", ".join(assignments) +
        ", updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(parameters),
    )
    return get_project(connection, project_id)


def create_assignment(connection, project_id, values):
    """Insert an assignment in the caller's transaction."""

    columns = (
        "project_id",
        "employee_id",
        "start_date",
        "end_date",
        "allocation_percentage",
    )
    parameters = (project_id,) + tuple(values.get(field) for field in columns[1:])
    cursor = connection.execute(
        f"INSERT INTO project_assignments ({_columns(columns)}) "
        f"VALUES ({_placeholders(parameters)})",
        parameters,
    )
    return get_assignment(connection, project_id, cursor.lastrowid)


def delete_assignment(connection, assignment_id):
    """Hard-delete an assignment; the schema has no soft-delete column."""

    return connection.execute(
        "DELETE FROM project_assignments WHERE id = ?",
        (assignment_id,),
    ).rowcount
