"""Employee CRUD API endpoints."""

import sqlite3

from flask import Blueprint, abort, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import require_any_permission, require_permission
from app.auth.permissions import (
    PERMISSION_EMPLOYEE_ARCHIVE,
    PERMISSION_EMPLOYEE_CREATE,
    PERMISSION_EMPLOYEE_READ_ALL,
    PERMISSION_EMPLOYEE_READ_SCOPE,
    PERMISSION_EMPLOYEE_SELF_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE_LIMITED,
)
from app.db import get_connection
from app.services import employees as employee_service
from app.services.authorization import employee_scope, require_employee_access


employees_bp = Blueprint("employees", __name__)


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@employees_bp.route("", methods=["GET"])
@require_any_permission(
    PERMISSION_EMPLOYEE_READ_ALL,
    PERMISSION_EMPLOYEE_READ_SCOPE,
)
def list_employees():
    """List employees visible to the caller."""

    user = get_current_user()
    connection = get_connection()
    try:
        scope = employee_scope(user, connection)
        rows = employee_service.list_employees(connection)
        if scope is not None:
            rows = [row for row in rows if row["id"] in scope]
        return jsonify({
            "success": True,
            "employees": [employee_service.serialize(row) for row in rows],
        }), 200
    finally:
        connection.close()


@employees_bp.route("", methods=["POST"])
@require_permission(PERMISSION_EMPLOYEE_CREATE)
def create_employee():
    """Create an employee. Requires the explicit create permission."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = employee_service.validate_create_payload(data)
    except employee_service.EmployeeValidationError as error:
        return _error(str(error), 400)

    user = get_current_user()
    connection = get_connection()
    try:
        employee = employee_service.create_employee(connection, values, user.id)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Employee created",
            "employee": employee_service.serialize(employee),
        }), 201
    except employee_service.EmployeeValidationError as error:
        connection.rollback()
        return _error(str(error), 400)
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Employee code or official email already exists", 409)
    finally:
        connection.close()


@employees_bp.route("/<int:employee_id>", methods=["GET"])
@require_any_permission(
    PERMISSION_EMPLOYEE_READ_ALL,
    PERMISSION_EMPLOYEE_READ_SCOPE,
)
def get_employee(employee_id):
    """Return one employee record when it is in the caller's scope."""

    user = get_current_user()
    connection = get_connection()
    try:
        row = employee_service.get_employee(connection, employee_id)
        if row is None:
            abort(404)
        require_employee_access(user, employee_id, connection)
        return jsonify({
            "success": True,
            "employee": employee_service.serialize(row),
        }), 200
    finally:
        connection.close()


@employees_bp.route("/<int:employee_id>", methods=["PUT"])
@require_any_permission(
    PERMISSION_EMPLOYEE_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE_LIMITED,
    PERMISSION_EMPLOYEE_SELF_UPDATE,
)
def update_employee(employee_id):
    """Partially update an employee using the caller's field allowlist."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    user = get_current_user()
    allowed_fields = employee_service.update_fields_for(user.permissions)
    try:
        values = employee_service.validate_update_payload(data, allowed_fields)
    except employee_service.EmployeeValidationError as error:
        return _error(str(error), 400)

    connection = get_connection()
    try:
        row = employee_service.get_employee(connection, employee_id)
        if row is None:
            abort(404)
        require_employee_access(user, employee_id, connection)
        updated = employee_service.update_employee(
            connection, employee_id, values, user.id
        )
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Employee updated",
            "employee": employee_service.serialize(updated),
        }), 200
    except employee_service.EmployeeValidationError as error:
        connection.rollback()
        return _error(str(error), 400)
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Employee code or official email already exists", 409)
    finally:
        connection.close()


@employees_bp.route("/<int:employee_id>", methods=["DELETE"])
@require_permission(PERMISSION_EMPLOYEE_ARCHIVE)
def delete_employee(employee_id):
    """Archive an employee instead of deleting related data."""

    user = get_current_user()
    connection = get_connection()
    try:
        row = employee_service.get_employee(connection, employee_id)
        if row is None:
            abort(404)
        require_employee_access(user, employee_id, connection)
        if employee_service.archive_employee(connection, employee_id, user.id) == 0:
            abort(404)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Employee archived",
        }), 200
    finally:
        connection.close()
