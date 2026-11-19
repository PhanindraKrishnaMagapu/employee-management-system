"""Employee validation, serialization, and database helpers."""

import re
from datetime import datetime

from app.auth.permissions import (
    PERMISSION_EMPLOYEE_SELF_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE_LIMITED,
)
from app.services.authorization import EMPLOYEE_PUBLIC_FIELDS


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMPLOYMENT_STATUSES = frozenset({"Pre-joining", "Active", "Exited"})

# The same allowlist is used for create and full HR update. Restricted fields
# from authorization.py are deliberately absent.
CREATE_FIELDS = (
    "employee_code",
    "first_name",
    "last_name",
    "official_email",
    "phone",
    "joining_date",
    "employment_type",
    "employment_status",
    "location",
    "department_id",
    "designation_id",
    "manager_id",
    "profile_photo_path",
)
REQUIRED_CREATE_FIELDS = (
    "employee_code",
    "first_name",
    "last_name",
    "official_email",
    "joining_date",
    "employment_type",
    "department_id",
    "designation_id",
)

FULL_UPDATE_FIELDS = frozenset(CREATE_FIELDS)
LIMITED_UPDATE_FIELDS = frozenset({"phone", "location"})
SELF_UPDATE_FIELDS = frozenset({"phone"})

OPTIONAL_TEXT_FIELDS = frozenset({
    "phone",
    "location",
    "profile_photo_path",
})
INTEGER_FIELDS = frozenset({"department_id", "designation_id", "manager_id"})


class EmployeeValidationError(ValueError):
    """Raised when an employee payload contains invalid data."""


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise EmployeeValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise EmployeeValidationError(f"{field} must be a string")
    return value.strip() or None


def _email(value):
    email = _required_string(value, "official_email")
    if not EMAIL_PATTERN.fullmatch(email):
        raise EmployeeValidationError("official_email must be a valid email address")
    return email


def _joining_date(value):
    if not isinstance(value, str):
        raise EmployeeValidationError("joining_date must be a YYYY-MM-DD date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise EmployeeValidationError(
            "joining_date must be a valid YYYY-MM-DD date"
        ) from error
    if parsed.isoformat() != value:
        raise EmployeeValidationError("joining_date must be a valid YYYY-MM-DD date")
    return value


def _status(value):
    status = _required_string(value, "employment_status")
    if status not in EMPLOYMENT_STATUSES:
        raise EmployeeValidationError(
            "employment_status must be one of: "
            + ", ".join(sorted(EMPLOYMENT_STATUSES))
        )
    return status


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EmployeeValidationError(f"{field} must be a positive integer")
    return value


def _unknown_fields(payload, allowed_fields):
    unknown = set(payload) - set(allowed_fields)
    if unknown:
        raise EmployeeValidationError(
            "Unsupported field(s): " + ", ".join(sorted(unknown))
        )


def validate_create_payload(payload):
    """Validate and normalize a create payload."""

    _unknown_fields(payload, CREATE_FIELDS)
    missing = [
        field
        for field in REQUIRED_CREATE_FIELDS
        if field not in payload
        or payload[field] is None
        or (isinstance(payload[field], str) and not payload[field].strip())
    ]
    if missing:
        raise EmployeeValidationError(
            "Missing required field(s): " + ", ".join(missing)
        )

    values = {
        "employee_code": _required_string(payload["employee_code"], "employee_code"),
        "first_name": _required_string(payload["first_name"], "first_name"),
        "last_name": _required_string(payload["last_name"], "last_name"),
        "official_email": _email(payload["official_email"]),
        "joining_date": _joining_date(payload["joining_date"]),
        "employment_type": _required_string(
            payload["employment_type"], "employment_type"
        ),
        "department_id": _positive_int(payload["department_id"], "department_id"),
        "designation_id": _positive_int(payload["designation_id"], "designation_id"),
    }

    if "employment_status" in payload:
        values["employment_status"] = _status(payload["employment_status"])
    for field in OPTIONAL_TEXT_FIELDS:
        if field in payload:
            values[field] = _optional_string(payload[field], field)
    if "manager_id" in payload:
        values["manager_id"] = (
            None
            if payload["manager_id"] is None
            else _positive_int(payload["manager_id"], "manager_id")
        )

    return values


def validate_update_payload(payload, allowed_fields):
    """Validate and normalize a partial update payload."""

    if not payload:
        raise EmployeeValidationError("At least one field is required")
    _unknown_fields(payload, allowed_fields)

    values = {}
    for field, value in payload.items():
        if field == "official_email":
            values[field] = _email(value)
        elif field == "joining_date":
            values[field] = _joining_date(value)
        elif field == "employment_status":
            values[field] = _status(value)
        elif field in OPTIONAL_TEXT_FIELDS:
            values[field] = _optional_string(value, field)
        elif field in INTEGER_FIELDS:
            values[field] = (
                None if field == "manager_id" and value is None
                else _positive_int(value, field)
            )
        else:
            values[field] = _required_string(value, field)

    return values


def update_fields_for(permissions):
    """Return the writable field set for the caller's strongest update grant."""

    if PERMISSION_EMPLOYEE_UPDATE in permissions:
        return FULL_UPDATE_FIELDS
    if PERMISSION_EMPLOYEE_UPDATE_LIMITED in permissions:
        return LIMITED_UPDATE_FIELDS
    if PERMISSION_EMPLOYEE_SELF_UPDATE in permissions:
        return SELF_UPDATE_FIELDS
    return frozenset()


def _reference_exists(connection, table, record_id, field, require_active=False):
    clause = " AND is_active = 1" if require_active else ""
    row = connection.execute(
        f"SELECT id FROM {table} WHERE id = ?{clause}", (record_id,)
    ).fetchone()
    if row is None:
        raise EmployeeValidationError(f"{field} does not reference an active record")


MAX_MANAGER_CHAIN_DEPTH = 100


def _creates_manager_cycle(connection, employee_id, manager_id):
    """Return True when assigning manager_id would create a reporting cycle.

    Walks upward from the proposed manager. Reaching the employee itself means
    a direct or indirect cycle; encountering a repeated id means the stored
    chain is already corrupt. The depth cap guarantees termination.
    """

    if manager_id is None:
        return False
    if employee_id is not None and manager_id == employee_id:
        return True

    seen = set()
    current = manager_id
    for _ in range(MAX_MANAGER_CHAIN_DEPTH):
        if current is None:
            return False
        if employee_id is not None and current == employee_id:
            return True
        if current in seen:
            return True
        seen.add(current)
        row = connection.execute(
            "SELECT manager_id FROM employees WHERE id = ?", (current,)
        ).fetchone()
        current = row["manager_id"] if row is not None else None
    return True


def _validate_references(connection, values, employee_id=None):
    if "department_id" in values:
        _reference_exists(
            connection, "departments", values["department_id"], "department_id", True
        )
    if "designation_id" in values:
        _reference_exists(
            connection, "designations", values["designation_id"], "designation_id"
        )
    if values.get("manager_id") is not None:
        manager_id = values["manager_id"]
        if employee_id is not None and manager_id == employee_id:
            raise EmployeeValidationError("manager_id cannot be the employee itself")
        _reference_exists(connection, "employees", manager_id, "manager_id")
        if _creates_manager_cycle(connection, employee_id, manager_id):
            raise EmployeeValidationError(
                "manager_id would create a circular reporting relationship"
            )


def validate_references(connection, values, employee_id=None):
    """Public reference/cycle validation for callers such as JML."""

    return _validate_references(connection, values, employee_id)


def _select_columns():
    return ", ".join(EMPLOYEE_PUBLIC_FIELDS)


def get_employee(connection, employee_id):
    """Return one active employee row, or None."""

    return connection.execute(
        f"SELECT {_select_columns()} FROM employees "
        "WHERE id = ? AND archived_at IS NULL",
        (employee_id,),
    ).fetchone()


def list_employees(connection):
    """Return all active employees ordered by id."""

    return connection.execute(
        f"SELECT {_select_columns()} FROM employees "
        "WHERE archived_at IS NULL ORDER BY id"
    ).fetchall()


def serialize(row):
    """Build the public JSON representation of an employee."""

    return {field: row[field] for field in EMPLOYEE_PUBLIC_FIELDS}


def create_employee(connection, values, user_id):
    """Insert a new employee and return its public row."""

    _validate_references(connection, values)
    columns = list(values) + ["created_by", "updated_by"]
    placeholders = ", ".join("?" for _ in columns)
    cursor = connection.execute(
        f"INSERT INTO employees ({', '.join(columns)}) VALUES ({placeholders})",
        tuple(values.values()) + (user_id, user_id),
    )
    return get_employee(connection, cursor.lastrowid)


def update_employee(connection, employee_id, values, user_id):
    """Apply a partial update and return the public row."""

    _validate_references(connection, values, employee_id)
    assignments = [f"{field} = ?" for field in values]
    assignments.extend(["updated_at = CURRENT_TIMESTAMP", "updated_by = ?"])
    connection.execute(
        f"UPDATE employees SET {', '.join(assignments)} "
        "WHERE id = ? AND archived_at IS NULL",
        tuple(values.values()) + (user_id, employee_id),
    )
    return get_employee(connection, employee_id)


def archive_employee(connection, employee_id, user_id):
    """Soft-delete an employee. Return the number of changed rows."""

    cursor = connection.execute(
        "UPDATE employees SET archived_at = CURRENT_TIMESTAMP, "
        "updated_at = CURRENT_TIMESTAMP, updated_by = ? "
        "WHERE id = ? AND archived_at IS NULL",
        (user_id, employee_id),
    )
    return cursor.rowcount
