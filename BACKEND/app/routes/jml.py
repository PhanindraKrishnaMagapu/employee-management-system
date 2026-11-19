"""JML event API endpoints with RBAC and employee-scope enforcement."""

import sqlite3

from flask import Blueprint, abort, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import require_any_permission, require_permission
from app.auth.permissions import PERMISSION_JML_MANAGE, PERMISSION_JML_READ
from app.db import get_connection
from app.services import employees as employee_service
from app.services import jml as jml_service
from app.services.authorization import employee_scope, require_employee_access


jml_bp = Blueprint("jml", __name__)


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _can_manage(user):
    return user is not None and PERMISSION_JML_MANAGE in user.permissions


def _serialize_event(connection, row, include_reason, counts=None):
    employee = jml_service.get_employee_public(connection, row["employee_id"])
    if counts is None:
        counts = jml_service.checklist_counts(connection)
    total, done = counts.get(row["id"], (0, 0))
    return jml_service.serialize_event(row, employee, total, done, include_reason)


@jml_bp.route("/events", methods=["GET"])
@require_any_permission(PERMISSION_JML_READ, PERMISSION_JML_MANAGE)
def list_events():
    """List JML events for employees visible to the caller."""

    user = get_current_user()
    connection = get_connection()
    try:
        scope = employee_scope(user, connection)
        rows = jml_service.list_events(connection)
        if scope is not None:
            rows = [row for row in rows if row["employee_id"] in scope]

        counts = jml_service.checklist_counts(connection)
        events = [
            _serialize_event(connection, row, include_reason=False, counts=counts)
            for row in rows
        ]
        return jsonify({"success": True, "events": events}), 200
    finally:
        connection.close()


@jml_bp.route("/events/<int:event_id>", methods=["GET"])
@require_any_permission(PERMISSION_JML_READ, PERMISSION_JML_MANAGE)
def get_event(event_id):
    """Return one event, its checklist, and Mover history when in scope."""

    user = get_current_user()
    connection = get_connection()
    try:
        row = jml_service.get_event(connection, event_id)
        if row is None:
            abort(404)
        require_employee_access(user, row["employee_id"], connection)

        checklist = [
            jml_service.serialize_checklist(item)
            for item in jml_service.list_checklist_items(connection, event_id)
        ]
        history = []
        if row["event_type"] == "Mover":
            history = [
                jml_service.serialize_history(item)
                for item in jml_service.list_history(connection, row["employee_id"])
            ]

        return jsonify({
            "success": True,
            "event": _serialize_event(
                connection, row, include_reason=_can_manage(user)
            ),
            "checklist_items": checklist,
            "history": history,
        }), 200
    finally:
        connection.close()


@jml_bp.route("/events", methods=["POST"])
@require_permission(PERMISSION_JML_MANAGE)
def create_event():
    """Create a JML event with default checklist items."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = jml_service.validate_event_payload(data)
    except jml_service.JMLValidationError as error:
        return _error(str(error), 400)

    user = get_current_user()
    connection = get_connection()
    try:
        employee = employee_service.get_employee(connection, values["employee_id"])
        if employee is None:
            abort(404)
        require_employee_access(user, values["employee_id"], connection)

        connection.execute("BEGIN IMMEDIATE")
        row = jml_service.create_event(connection, values, user.id, employee)
        counts = jml_service.checklist_counts(connection)
        connection.commit()

        return jsonify({
            "success": True,
            "message": "JML event created",
            "event": _serialize_event(connection, row, True, counts),
        }), 201
    except (jml_service.JMLValidationError, employee_service.EmployeeValidationError) as error:
        connection.rollback()
        return _error(str(error), 400)
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error(
            "Invalid employee, manager, department or designation reference", 400
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@jml_bp.route("/events/<int:event_id>", methods=["PATCH"])
@require_permission(PERMISSION_JML_MANAGE)
def update_event(event_id):
    """Update an event status and apply completion effects."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        status = jml_service.validate_status_payload(
            data, jml_service.EVENT_STATUSES
        )
    except jml_service.JMLValidationError as error:
        return _error(str(error), 400)

    user = get_current_user()
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        # Re-read under the write lock so a racing request cannot change the
        # status between validation and the update and slip past the table.
        row = jml_service.get_event(connection, event_id)
        if row is None:
            abort(404)
        require_employee_access(user, row["employee_id"], connection)

        jml_service.validate_transition(row["status"], status)
        if status == jml_service.COMPLETED:
            if not jml_service.checklist_is_complete(connection, event_id):
                raise jml_service.JMLValidationError(
                    "All checklist items must be completed before completing an event"
                )
            if (
                row["event_type"] == "Leaver"
                and not jml_service.access_removal_is_complete(connection, event_id)
            ):
                raise jml_service.JMLValidationError(
                    "Access removal must be confirmed before completing a Leaver event"
                )

        jml_service.set_event_status(connection, event_id, status)
        if status == jml_service.COMPLETED:
            jml_service.apply_completion_status(connection, row, user.id)
        updated = jml_service.get_event(connection, event_id)
        counts = jml_service.checklist_counts(connection)
        connection.commit()

        return jsonify({
            "success": True,
            "message": "JML event updated",
            "event": _serialize_event(connection, updated, True, counts),
        }), 200
    except (jml_service.JMLValidationError, employee_service.EmployeeValidationError) as error:
        connection.rollback()
        return _error(str(error), 400)
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("The employee could not be updated for this event", 400)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@jml_bp.route(
    "/events/<int:event_id>/checklist/<int:item_id>", methods=["PATCH"]
)
@require_permission(PERMISSION_JML_MANAGE)
def update_checklist_item(event_id, item_id):
    """Update one checklist item belonging to the specified event."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        status = jml_service.validate_status_payload(
            data, jml_service.CHECKLIST_STATUSES
        )
    except jml_service.JMLValidationError as error:
        return _error(str(error), 400)

    user = get_current_user()
    connection = get_connection()
    try:
        item = jml_service.get_checklist_item(connection, event_id, item_id)
        if item is None:
            abort(404)
        event = jml_service.get_event(connection, event_id)
        if event is None:
            abort(404)
        require_employee_access(user, event["employee_id"], connection)

        connection.execute("BEGIN IMMEDIATE")
        jml_service.set_checklist_status(connection, item_id, status)
        updated_item = jml_service.get_checklist_item(connection, event_id, item_id)
        updated_event = jml_service.get_event(connection, event_id)
        counts = jml_service.checklist_counts(connection)
        connection.commit()

        return jsonify({
            "success": True,
            "message": "Checklist item updated",
            "checklist_item": jml_service.serialize_checklist(updated_item),
            "event": _serialize_event(connection, updated_event, True, counts),
        }), 200
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
