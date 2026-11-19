"""Skill catalog and employee assignment validation and database helpers."""

import math
from datetime import datetime

from app.services.authorization import EMPLOYEE_PUBLIC_FIELDS


PROFICIENCY_LEVELS = ("Beginner", "Intermediate", "Advanced", "Expert")

SKILL_FIELDS = (
    "id",
    "name",
    "description",
    "created_at",
    "updated_at",
)
EMPLOYEE_SKILL_FIELDS = (
    "id",
    "employee_id",
    "skill_id",
    "proficiency_level",
    "experience_years",
    "last_verified",
    "created_at",
    "updated_at",
)

SKILL_PAYLOAD_FIELDS = frozenset({"name", "description"})
ASSIGNMENT_PAYLOAD_FIELDS = frozenset({
    "skill_id",
    "proficiency_level",
    "experience_years",
    "last_verified",
})
ASSIGNMENT_UPDATE_FIELDS = frozenset({
    "proficiency_level",
    "experience_years",
    "last_verified",
})


class SkillValidationError(ValueError):
    """Raised when a skill payload contains invalid data."""


def _columns(fields):
    return ", ".join(fields)


def _placeholders(values):
    return ", ".join("?" for _ in values)


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise SkillValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise SkillValidationError(f"{field} must be a string")
    return value.strip() or None


def _unknown_fields(payload, allowed_fields):
    unknown = set(payload) - set(allowed_fields)
    if unknown:
        raise SkillValidationError(
            "Unsupported field(s): " + ", ".join(sorted(unknown))
        )


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SkillValidationError(f"{field} must be a positive integer")
    return value


def _proficiency(value):
    level = _required_string(value, "proficiency_level")
    if level not in PROFICIENCY_LEVELS:
        raise SkillValidationError(
            "proficiency_level must be one of: " + ", ".join(PROFICIENCY_LEVELS)
        )
    return level


def _experience_years(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SkillValidationError(
            "experience_years must be a non-negative finite number"
        )
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise SkillValidationError(
            "experience_years must be a non-negative finite number"
        )
    return number


def _date(value, field):
    if not isinstance(value, str):
        raise SkillValidationError(f"{field} must be a YYYY-MM-DD date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise SkillValidationError(
            f"{field} must be a valid YYYY-MM-DD date"
        ) from error
    if parsed.isoformat() != value:
        raise SkillValidationError(f"{field} must be a valid YYYY-MM-DD date")
    return value


def validate_skill_payload(payload, current=None):
    """Validate and normalize a skill create or partial update payload."""

    if not isinstance(payload, dict):
        raise SkillValidationError("Request body must be a JSON object")
    _unknown_fields(payload, SKILL_PAYLOAD_FIELDS)

    is_update = current is not None
    if is_update and not payload:
        raise SkillValidationError("At least one field is required")

    if not is_update and _blank(payload.get("name")):
        raise SkillValidationError("Missing required field(s): name")

    values = {}
    if "name" in payload:
        values["name"] = _required_string(payload["name"], "name")
    if "description" in payload:
        values["description"] = _optional_string(
            payload["description"], "description"
        )
    return values


def validate_assignment_payload(payload):
    """Validate and normalize an employee skill assignment create payload."""

    if not isinstance(payload, dict):
        raise SkillValidationError("Request body must be a JSON object")
    _unknown_fields(payload, ASSIGNMENT_PAYLOAD_FIELDS)

    missing = [
        field for field in ("skill_id", "proficiency_level")
        if _blank(payload.get(field))
    ]
    if missing:
        raise SkillValidationError(
            "Missing required field(s): " + ", ".join(missing)
        )

    values = {
        "skill_id": _positive_int(payload["skill_id"], "skill_id"),
        "proficiency_level": _proficiency(payload["proficiency_level"]),
        "experience_years": (
            0.0 if "experience_years" not in payload
            else _experience_years(payload["experience_years"])
        ),
        "last_verified": (
            None if _blank(payload.get("last_verified"))
            else _date(payload["last_verified"], "last_verified")
        ),
    }
    return values


def validate_assignment_update_payload(payload):
    """Validate and normalize an employee skill assignment update payload."""

    if not isinstance(payload, dict):
        raise SkillValidationError("Request body must be a JSON object")
    _unknown_fields(payload, ASSIGNMENT_UPDATE_FIELDS)
    if not payload:
        raise SkillValidationError("At least one field is required")

    values = {}
    if "proficiency_level" in payload:
        values["proficiency_level"] = _proficiency(payload["proficiency_level"])
    if "experience_years" in payload:
        values["experience_years"] = _experience_years(
            payload["experience_years"]
        )
    if "last_verified" in payload:
        value = payload["last_verified"]
        values["last_verified"] = None if _blank(value) else _date(
            value, "last_verified"
        )
    return values


def _escape_like(value):
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def list_skills(connection, search=None):
    """Return skills ordered by name, optionally filtered by search text."""

    parameters = []
    sql = f"SELECT {_columns(SKILL_FIELDS)} FROM skills"
    if search:
        pattern = "%" + _escape_like(search.strip()) + "%"
        sql += (
            " WHERE name LIKE ? ESCAPE '\\' "
            "OR description LIKE ? ESCAPE '\\'"
        )
        parameters.extend([pattern, pattern])
    sql += " ORDER BY name COLLATE NOCASE, id"
    return connection.execute(sql, tuple(parameters)).fetchall()


def get_skill(connection, skill_id):
    """Return one skill row, or None."""

    return connection.execute(
        f"SELECT {_columns(SKILL_FIELDS)} FROM skills WHERE id = ?",
        (skill_id,),
    ).fetchone()


def skill_exists(connection, skill_id):
    """Return True when the id references a skill."""

    return get_skill(connection, skill_id) is not None


def get_public_employee(connection, employee_id):
    """Return a non-archived employee using the shared public allowlist."""

    row = connection.execute(
        f"SELECT {_columns(EMPLOYEE_PUBLIC_FIELDS)} FROM employees "
        "WHERE id = ? AND archived_at IS NULL",
        (employee_id,),
    ).fetchone()
    if row is None:
        return None
    return {field: row[field] for field in EMPLOYEE_PUBLIC_FIELDS}


def active_employee_exists(connection, employee_id):
    """Return True when the id references a current Active employee."""

    row = connection.execute(
        "SELECT id FROM employees "
        "WHERE id = ? AND archived_at IS NULL AND employment_status = 'Active'",
        (employee_id,),
    ).fetchone()
    return row is not None


def list_assignments(connection, employee_id):
    """Return an employee's assignments ordered by skill id."""

    return connection.execute(
        f"SELECT {_columns(EMPLOYEE_SKILL_FIELDS)} FROM employee_skills "
        "WHERE employee_id = ? ORDER BY skill_id, id",
        (employee_id,),
    ).fetchall()


def get_assignment(connection, employee_id, assignment_id):
    """Return one assignment only when it belongs to this employee."""

    return connection.execute(
        f"SELECT {_columns(EMPLOYEE_SKILL_FIELDS)} FROM employee_skills "
        "WHERE id = ? AND employee_id = ?",
        (assignment_id, employee_id),
    ).fetchone()


def assignment_exists(connection, employee_id, skill_id):
    """Return True when this employee already has this skill."""

    row = connection.execute(
        "SELECT id FROM employee_skills "
        "WHERE employee_id = ? AND skill_id = ?",
        (employee_id, skill_id),
    ).fetchone()
    return row is not None


def serialize_skill(row):
    """Build the JSON representation of one skill."""

    return {field: row[field] for field in SKILL_FIELDS}


def serialize_assignment(row, skill, employee):
    """Build the JSON representation of one employee skill assignment."""

    result = {field: row[field] for field in EMPLOYEE_SKILL_FIELDS}
    result["skill"] = serialize_skill(skill) if skill is not None else None
    result["employee"] = employee
    return result


def create_skill(connection, values):
    """Insert a skill in the caller's transaction."""

    columns = ("name", "description")
    parameters = tuple(values.get(field) for field in columns)
    cursor = connection.execute(
        f"INSERT INTO skills ({_columns(columns)}) "
        f"VALUES ({_placeholders(parameters)})",
        parameters,
    )
    return get_skill(connection, cursor.lastrowid)


def update_skill(connection, skill_id, values):
    """Update allowed skill fields in the caller's transaction."""

    assignments = [f"{field} = ?" for field in values]
    parameters = list(values.values()) + [skill_id]
    connection.execute(
        "UPDATE skills SET " + ", ".join(assignments) +
        ", updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(parameters),
    )
    return get_skill(connection, skill_id)


def create_assignment(connection, employee_id, values):
    """Insert an employee skill assignment in the caller's transaction."""

    columns = (
        "employee_id",
        "skill_id",
        "proficiency_level",
        "experience_years",
        "last_verified",
    )
    parameters = (employee_id,) + tuple(values.get(field) for field in columns[1:])
    cursor = connection.execute(
        f"INSERT INTO employee_skills ({_columns(columns)}) "
        f"VALUES ({_placeholders(parameters)})",
        parameters,
    )
    return get_assignment(connection, employee_id, cursor.lastrowid)


def update_assignment(connection, assignment_id, values):
    """Update allowed assignment fields in the caller's transaction."""

    assignments = [f"{field} = ?" for field in values]
    parameters = list(values.values()) + [assignment_id]
    connection.execute(
        "UPDATE employee_skills SET " + ", ".join(assignments) +
        ", updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(parameters),
    )
    return connection.execute(
        f"SELECT {_columns(EMPLOYEE_SKILL_FIELDS)} FROM employee_skills "
        "WHERE id = ?",
        (assignment_id,),
    ).fetchone()


def delete_assignment(connection, assignment_id):
    """Hard-delete one assignment; the schema has no soft-delete column."""

    return connection.execute(
        "DELETE FROM employee_skills WHERE id = ?",
        (assignment_id,),
    ).rowcount
