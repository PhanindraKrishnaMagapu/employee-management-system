"""JML event validation, serialization, and database helpers."""

import json
from datetime import datetime

from app.services import employees as employee_service
from app.services.authorization import EMPLOYEE_PUBLIC_FIELDS


EVENT_TYPES = frozenset({"Joiner", "Mover", "Leaver"})
EVENT_STATUSES = frozenset({
    "Pending",
    "In Progress",
    "Completed",
    "Cancelled",
})
CHECKLIST_STATUSES = frozenset({"Pending", "Completed"})
COMPLETED = "Completed"

# Terminal states cannot be reopened. Pending may go straight to Completed for
# simple workflows, but no transition out of Completed/Cancelled is legal.
EVENT_TRANSITIONS = {
    "Pending": frozenset({"In Progress", "Completed", "Cancelled"}),
    "In Progress": frozenset({"Completed", "Cancelled"}),
    "Completed": frozenset(),
    "Cancelled": frozenset(),
}
ACCESS_REMOVAL_ITEM_TITLE = "Access removal confirmed"

MOVER_FIELDS = ("department_id", "designation_id", "manager_id", "location")
COMPLETION_STATUSES = {"Joiner": "Active", "Leaver": "Exited"}

EVENT_FIELDS = (
    "id",
    "employee_id",
    "event_type",
    "effective_date",
    "status",
    "created_at",
    "updated_at",
)
EVENT_SELECT_FIELDS = EVENT_FIELDS + ("reason", "pending_changes")
CHECKLIST_FIELDS = (
    "id",
    "jml_event_id",
    "title",
    "description",
    "assigned_to",
    "status",
    "due_date",
    "completed_at",
    "created_at",
    "updated_at",
)
HISTORY_FIELDS = (
    "id",
    "employee_id",
    "old_department_id",
    "new_department_id",
    "old_designation_id",
    "new_designation_id",
    "old_manager_id",
    "new_manager_id",
    "old_location",
    "new_location",
    "effective_date",
    "change_reason",
    "created_at",
)

# Default templates stay in code: no database seed or migration is needed.
CHECKLIST_TEMPLATES = {
    "Joiner": (
        ("Employee record created", "Confirm the employee record exists with the correct details."),
        ("Role and reporting line assigned", "Confirm department, designation, location and manager."),
        ("System access confirmed", "Confirm required accounts and access are ready."),
    ),
    "Mover": (
        ("Approval recorded", "Confirm the move was approved."),
        ("Employee record updated", "Confirm the department, designation, manager and location changes."),
        ("History recorded", "Confirm the old and new values were retained."),
        ("Employee notified", "Confirm the employee was informed."),
    ),
    "Leaver": (
        ("Exit reason recorded", "Confirm the restricted exit reason was recorded."),
        ("Asset return confirmed", "Confirm company assets were returned."),
        ("Access removal confirmed", "Confirm system access was removed."),
        ("Final status confirmed", "Confirm the employee status was updated to Exited."),
    ),
}

EVENT_PAYLOAD_FIELDS = frozenset({
    "employee_id",
    "event_type",
    "effective_date",
    "reason",
    "changes",
})


class JMLValidationError(ValueError):
    """Raised when a JML payload contains invalid data."""


def _columns(fields):
    return ", ".join(fields)


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise JMLValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(value, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise JMLValidationError(f"{field} must be a string")
    return value.strip() or None


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise JMLValidationError(f"{field} must be a positive integer")
    return value


def _date(value, field):
    if not isinstance(value, str):
        raise JMLValidationError(f"{field} must be a YYYY-MM-DD date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise JMLValidationError(f"{field} must be a valid YYYY-MM-DD date") from error
    if parsed.isoformat() != value:
        raise JMLValidationError(f"{field} must be a valid YYYY-MM-DD date")
    return value


def _unknown_fields(payload, allowed_fields):
    unknown = set(payload) - set(allowed_fields)
    if unknown:
        raise JMLValidationError(
            "Unsupported field(s): " + ", ".join(sorted(unknown))
        )


def validate_event_payload(payload):
    """Validate and normalize a JML event create payload."""

    if not isinstance(payload, dict):
        raise JMLValidationError("Request body must be a JSON object")
    _unknown_fields(payload, EVENT_PAYLOAD_FIELDS)

    missing = [
        field
        for field in ("employee_id", "event_type", "effective_date")
        if field not in payload
        or payload[field] is None
        or (isinstance(payload[field], str) and not payload[field].strip())
    ]
    if missing:
        raise JMLValidationError(
            "Missing required field(s): " + ", ".join(missing)
        )

    event_type = _required_string(payload["event_type"], "event_type")
    if event_type not in EVENT_TYPES:
        raise JMLValidationError(
            "event_type must be one of: " + ", ".join(sorted(EVENT_TYPES))
        )

    values = {
        "employee_id": _positive_int(payload["employee_id"], "employee_id"),
        "event_type": event_type,
        "effective_date": _date(payload["effective_date"], "effective_date"),
        "reason": _optional_string(payload.get("reason"), "reason"),
    }

    if event_type == "Leaver" and not values["reason"]:
        raise JMLValidationError("reason is required for a Leaver event")

    has_changes = "changes" in payload
    if has_changes and event_type != "Mover":
        raise JMLValidationError("changes is only supported for Mover events")
    if event_type == "Mover" and not has_changes:
        raise JMLValidationError("changes is required for a Mover event")

    if has_changes:
        changes = payload["changes"]
        if not isinstance(changes, dict) or not changes:
            raise JMLValidationError("changes must be a non-empty object")
        try:
            values["changes"] = employee_service.validate_update_payload(
                changes, frozenset(MOVER_FIELDS)
            )
        except employee_service.EmployeeValidationError as error:
            raise JMLValidationError(str(error)) from error

    return values


def validate_status_payload(payload, allowed_statuses):
    """Validate a status-only PATCH payload."""

    if not isinstance(payload, dict):
        raise JMLValidationError("Request body must be a JSON object")
    _unknown_fields(payload, {"status"})
    if "status" not in payload:
        raise JMLValidationError("status is required")

    status = _required_string(payload["status"], "status")
    if status not in allowed_statuses:
        raise JMLValidationError(
            "status must be one of: " + ", ".join(sorted(allowed_statuses))
        )
    return status


def validate_transition(current_status, new_status):
    """Reject transitions that are not present in the legal transition table."""

    allowed = EVENT_TRANSITIONS.get(current_status, frozenset())
    if new_status not in allowed:
        raise JMLValidationError(
            f"Cannot change status from {current_status} to {new_status}"
        )
    return new_status


def get_event(connection, event_id):
    """Return one JML event, or None."""

    return connection.execute(
        f"SELECT {_columns(EVENT_SELECT_FIELDS)} FROM jml_events WHERE id = ?",
        (event_id,),
    ).fetchone()


def list_events(connection):
    """Return JML events, newest first."""

    return connection.execute(
        f"SELECT {_columns(EVENT_SELECT_FIELDS)} FROM jml_events ORDER BY id DESC"
    ).fetchall()


def get_employee_public(connection, employee_id):
    """Return an employee using the shared public-field allowlist."""

    row = connection.execute(
        f"SELECT {_columns(EMPLOYEE_PUBLIC_FIELDS)} FROM employees WHERE id = ?",
        (employee_id,),
    ).fetchone()
    return employee_service.serialize(row) if row is not None else None


def get_checklist_item(connection, event_id, item_id):
    """Return a checklist item only when it belongs to this event."""

    return connection.execute(
        f"SELECT {_columns(CHECKLIST_FIELDS)} FROM checklist_items "
        "WHERE id = ? AND jml_event_id = ?",
        (item_id, event_id),
    ).fetchone()


def list_checklist_items(connection, event_id):
    """Return all checklist items for one event."""

    return connection.execute(
        f"SELECT {_columns(CHECKLIST_FIELDS)} FROM checklist_items "
        "WHERE jml_event_id = ? ORDER BY id",
        (event_id,),
    ).fetchall()


def list_history(connection, employee_id):
    """Return employee history rows for one employee."""

    return connection.execute(
        f"SELECT {_columns(HISTORY_FIELDS)} FROM employee_history "
        "WHERE employee_id = ? ORDER BY effective_date DESC, id DESC",
        (employee_id,),
    ).fetchall()


def checklist_counts(connection):
    """Return {event_id: (total, completed)} for all checklist items."""

    rows = connection.execute(
        "SELECT jml_event_id, COUNT(*) AS total, "
        "SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS done "
        "FROM checklist_items GROUP BY jml_event_id",
        (COMPLETED,),
    ).fetchall()
    return {
        row["jml_event_id"]: (row["total"], row["done"] or 0)
        for row in rows
    }


def checklist_is_complete(connection, event_id):
    """Return True when every checklist item for the event is completed."""

    row = connection.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS done "
        "FROM checklist_items WHERE jml_event_id = ?",
        (COMPLETED, event_id),
    ).fetchone()
    return row is not None and row["total"] > 0 and (row["done"] or 0) == row["total"]


def access_removal_is_complete(connection, event_id):
    """Return True when the Leaver access-removal item is completed."""

    row = connection.execute(
        "SELECT status FROM checklist_items "
        "WHERE jml_event_id = ? AND title = ?",
        (event_id, ACCESS_REMOVAL_ITEM_TITLE),
    ).fetchone()
    return row is not None and row["status"] == COMPLETED


def deactivate_linked_users(connection, employee_id):
    """Deactivate only user accounts linked to this employee."""

    return connection.execute(
        "UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP "
        "WHERE employee_id = ?",
        (employee_id,),
    ).rowcount


def serialize_event(row, employee, checklist_total=0, checklist_done=0, include_reason=False):
    """Build the JSON representation of one JML event."""

    result = {field: row[field] for field in EVENT_FIELDS}
    if include_reason:
        result["reason"] = row["reason"]
    result["employee"] = employee
    result["checklist_total"] = checklist_total
    result["checklist_done"] = checklist_done
    return result


def serialize_checklist(row):
    """Build the JSON representation of one checklist item."""

    return {field: row[field] for field in CHECKLIST_FIELDS}


def serialize_history(row):
    """Build the JSON representation of one employee history row."""

    return {field: row[field] for field in HISTORY_FIELDS}


def _record_mover_history(connection, event_id, employee_row, values):
    history_values = {}
    for field in MOVER_FIELDS:
        old_value = employee_row[field]
        history_values[f"old_{field}"] = old_value
        history_values[f"new_{field}"] = values["changes"].get(field, old_value)

    columns = list(history_values) + ["employee_id", "effective_date", "change_reason"]
    parameters = tuple(history_values.values()) + (
        employee_row["id"],
        values["effective_date"],
        values.get("reason") or f"Mover event #{event_id}",
    )
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO employee_history ({_columns(columns)}) "
        f"VALUES ({placeholders})",
        parameters,
    )


def create_event(connection, values, user_id, employee_row):
    """Insert an event and its checklist in the caller's transaction."""

    if values["event_type"] == "Mover":
        # Validate references and reporting cycles now, but apply later.
        employee_service.validate_references(
            connection, values["changes"], values["employee_id"]
        )

    pending_changes = (
        json.dumps(values["changes"], sort_keys=True)
        if values["event_type"] == "Mover" else None
    )
    cursor = connection.execute(
        "INSERT INTO jml_events "
        "(employee_id, event_type, effective_date, reason, pending_changes, status) "
        "VALUES (?, ?, ?, ?, ?, 'Pending')",
        (
            values["employee_id"],
            values["event_type"],
            values["effective_date"],
            values["reason"],
            pending_changes,
        ),
    )
    event_id = cursor.lastrowid

    for title, description in CHECKLIST_TEMPLATES[values["event_type"]]:
        connection.execute(
            "INSERT INTO checklist_items "
            "(jml_event_id, title, description, due_date, status) "
            "VALUES (?, ?, ?, ?, 'Pending')",
            (event_id, title, description, values["effective_date"]),
        )

    # Mover changes are stored, not applied. They take effect only when the
    # event reaches Completed, so a Cancelled event leaves the record intact.
    return get_event(connection, event_id)


def set_event_status(connection, event_id, status):
    """Update an event status and its timestamp."""

    return connection.execute(
        "UPDATE jml_events SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, event_id),
    ).rowcount


def apply_completion_status(connection, event_row, user_id):
    """Apply deferred effects when an event moves to Completed."""

    employee_id = event_row["employee_id"]

    if event_row["event_type"] == "Mover" and event_row["pending_changes"]:
        changes = json.loads(event_row["pending_changes"])
        employee_before = get_employee_public(connection, employee_id)
        employee_service.validate_references(connection, changes, employee_id)
        employee_service.update_employee(connection, employee_id, changes, user_id)
        _record_mover_history(
            connection,
            event_row["id"],
            employee_before,
            {
                "changes": changes,
                "effective_date": event_row["effective_date"],
                "reason": event_row["reason"],
            },
        )

    target_status = COMPLETION_STATUSES.get(event_row["event_type"])
    if target_status is not None:
        employee_service.update_employee(
            connection, employee_id, {"employment_status": target_status}, user_id
        )

    if event_row["event_type"] == "Leaver":
        deactivate_linked_users(connection, employee_id)


def set_checklist_status(connection, item_id, status):
    """Update a checklist item and maintain completed_at."""

    completed_at = "CURRENT_TIMESTAMP" if status == COMPLETED else "NULL"
    return connection.execute(
        f"UPDATE checklist_items SET status = ?, completed_at = {completed_at}, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, item_id),
    ).rowcount
