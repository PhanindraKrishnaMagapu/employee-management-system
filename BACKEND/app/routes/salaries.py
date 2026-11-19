"""Salary record API endpoints with RBAC and salary-specific scoping.

Salary data intentionally lives under /api/salaries rather than the general
employee namespace. Payroll Admin therefore never needs employee read access,
and the Project Manager employee carve-out cannot interfere with combined
roles.
"""

import sqlite3

from flask import Blueprint, abort, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import require_any_permission, require_permission
from app.auth.permissions import (
    PERMISSION_SALARY_MANAGE,
    PERMISSION_SALARY_READ,
)
from app.db import get_connection
from app.services import salaries as salary_service


salaries_bp = Blueprint("salaries", __name__)


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _require_salary_employee(connection, employee_id):
    """Return the minimal employee row, or abort 404 when out of scope."""

    employee = salary_service.get_salary_employee(connection, employee_id)
    if employee is None:
        abort(404)
    salary_service.require_salary_employee_access(
        get_current_user(), employee_id, connection
    )
    return employee


@salaries_bp.route("", methods=["GET"])
@require_any_permission(PERMISSION_SALARY_READ, PERMISSION_SALARY_MANAGE)
def list_salaries():
    """List salary records with search, filters, and pagination."""

    try:
        filters = salary_service.parse_list_query(request.args)
    except salary_service.SalaryValidationError as error:
        return _error(str(error), 400)

    user = get_current_user()
    connection = get_connection()
    try:
        scope = salary_service.salary_employee_scope(user, connection)
        salaries, total = salary_service.list_salaries(
            connection, scope, filters
        )
        return jsonify({
            "success": True,
            "salaries": salaries,
            "total": total,
            "limit": filters["limit"],
            "offset": filters["offset"],
        }), 200
    finally:
        connection.close()


@salaries_bp.route("/employees", methods=["GET"])
@require_any_permission(PERMISSION_SALARY_READ, PERMISSION_SALARY_MANAGE)
def list_salary_employees():
    """Return a minimal, non-archived employee picker for salary forms."""

    search = request.args.get("search", "").strip()
    if len(search) > salary_service.MAX_SEARCH_LENGTH:
        return _error("search is too long", 400)

    user = get_current_user()
    connection = get_connection()
    try:
        scope = salary_service.salary_employee_scope(user, connection)
        employees = salary_service.list_salary_employees(
            connection, scope, search or None
        )
        return jsonify({"success": True, "employees": employees}), 200
    finally:
        connection.close()


@salaries_bp.route("/<int:salary_id>", methods=["GET"])
@require_any_permission(PERMISSION_SALARY_READ, PERMISSION_SALARY_MANAGE)
def get_salary(salary_id):
    """Return one salary record when its employee is in salary scope."""

    connection = get_connection()
    try:
        salary = salary_service.get_salary(connection, salary_id)
        if salary is None:
            abort(404)
        salary_service.require_salary_employee_access(
            get_current_user(), salary["employee_id"], connection
        )
        return jsonify({"success": True, "salary": salary}), 200
    finally:
        connection.close()


@salaries_bp.route("", methods=["POST"])
@require_permission(PERMISSION_SALARY_MANAGE)
def create_salary():
    """Create a salary period, closing any earlier open-ended period."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = salary_service.validate_create_payload(data)
    except salary_service.SalaryValidationError as error:
        return _error(str(error), 400)

    connection = get_connection()
    try:
        employee = _require_salary_employee(connection, values["employee_id"])
        if salary_service.is_archived(employee):
            return _error(
                "Archived employees cannot receive new salary records", 400
            )

        connection.execute("BEGIN IMMEDIATE")
        closed_ids = salary_service.close_open_salary_records(
            connection, values["employee_id"], values["effective_from"]
        )
        if salary_service.find_overlapping_salary(
            connection,
            values["employee_id"],
            values["effective_from"],
            values["effective_to"],
        ) is not None:
            connection.rollback()
            return _error("Salary period overlaps an existing record", 409)

        salary = salary_service.create_salary(connection, values)
        actor_user_id = get_current_user().id
        for closed_id in closed_ids:
            salary_service.log_salary_auto_close(
                connection,
                actor_user_id,
                values["employee_id"],
                closed_id,
            )
        salary_service.log_salary_create(
            connection, actor_user_id, salary
        )
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Salary record created",
            "salary": salary,
        }), 201
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Salary record violates a database constraint", 400)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@salaries_bp.route("/<int:salary_id>", methods=["PUT"])
@require_permission(PERMISSION_SALARY_MANAGE)
def update_salary(salary_id):
    """Correct or close a salary record without changing its employee.

    Updates remain available for archived employees so historical records can
    be corrected or closed. Only the existing update allowlist is accepted;
    ``employee_id`` is always immutable.
    """

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    connection = get_connection()
    try:
        current = salary_service.get_salary(connection, salary_id)
        if current is None:
            abort(404)
        _require_salary_employee(connection, current["employee_id"])

        try:
            values = salary_service.validate_update_payload(data, current)
        except salary_service.SalaryValidationError as error:
            return _error(str(error), 400)

        connection.execute("BEGIN IMMEDIATE")
        if salary_service.find_overlapping_salary(
            connection,
            current["employee_id"],
            values.get("effective_from", current["effective_from"]),
            values.get("effective_to", current["effective_to"]),
            exclude_id=salary_id,
        ) is not None:
            connection.rollback()
            return _error("Salary period overlaps an existing record", 409)

        salary = salary_service.update_salary(connection, salary_id, values)
        salary_service.log_salary_update(
            connection, get_current_user().id, salary
        )
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Salary record updated",
            "salary": salary,
        }), 200
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Salary record violates a database constraint", 400)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
