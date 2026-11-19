"""Authenticated current-user profile API."""

from datetime import date

from flask import Blueprint, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import require_any_permission, require_authentication
from app.auth.permissions import (
    PERMISSION_EMPLOYEE_SELF_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE_LIMITED,
    PERMISSION_SALARY_MANAGE,
    PERMISSION_SALARY_READ,
)
from app.db import get_connection
from app.services import employees as employee_service


profile_bp = Blueprint("profile", __name__)

PROFILE_UPDATE_FIELDS = frozenset({"phone"})


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _profile_employee(connection, employee_id):
    """Load the authenticated user's linked employee without accepting an ID."""

    if employee_id is None:
        return None

    return connection.execute(
        """
        SELECT
            e.employee_code,
            e.first_name,
            e.last_name,
            e.official_email,
            e.phone,
            e.date_of_birth,
            e.joining_date,
            e.employment_type,
            e.employment_status,
            e.location,
            e.profile_photo_path,
            d.name AS department,
            dg.title AS designation,
            CASE
                WHEN manager.id IS NULL THEN NULL
                ELSE manager.first_name || ' ' || manager.last_name
            END AS manager_name
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
        LEFT JOIN designations dg ON dg.id = e.designation_id
        LEFT JOIN employees manager ON manager.id = e.manager_id
        WHERE e.id = ? AND e.archived_at IS NULL
        """,
        (employee_id,),
    ).fetchone()


def _serialize_employee(row):
    if row is None:
        return None
    return {key: row[key] for key in (
        "employee_code",
        "first_name",
        "last_name",
        "official_email",
        "phone",
        "date_of_birth",
        "joining_date",
        "employment_type",
        "employment_status",
        "location",
        "profile_photo_path",
        "department",
        "designation",
        "manager_name",
    )}


def _profile_response(user, connection):
    employee_row = _profile_employee(connection, user.employee_id)
    employee = _serialize_employee(employee_row)
    result = {
        "success": True,
        "user": {
            "username": user.username,
            "email": user.email,
            "roles": list(user.roles),
            # The request has an authenticated CurrentUser, which is loaded
            # only for active accounts.
            "account_status": "Active",
        },
        "employee": employee,
        "editable_fields": sorted(
            PROFILE_UPDATE_FIELDS.intersection(
                employee_service.update_fields_for(user.permissions)
            )
        ),
    }

    can_read_salary = bool(user.permissions.intersection({
        PERMISSION_SALARY_READ,
        PERMISSION_SALARY_MANAGE,
    }))
    if can_read_salary:
        salary = None
        if user.employee_id is not None and employee_row is not None:
            today = date.today().isoformat()
            row = connection.execute(
                """
                SELECT annual_salary, currency, effective_from, effective_to
                FROM salary_records
                WHERE employee_id = ?
                  AND effective_from <= ?
                  AND (effective_to IS NULL OR effective_to >= ?)
                ORDER BY effective_from DESC, id DESC
                LIMIT 1
                """,
                (user.employee_id, today, today),
            ).fetchone()
            if row is not None:
                salary = {key: row[key] for key in (
                    "annual_salary", "currency", "effective_from", "effective_to"
                )}
        result["salary"] = salary

    return result


@profile_bp.route("/profile", methods=["GET"])
@require_authentication
def get_profile():
    """Return only the signed-in user's account and linked employee profile."""

    user = get_current_user()
    connection = get_connection()
    try:
        return jsonify(_profile_response(user, connection)), 200
    finally:
        connection.close()


@profile_bp.route("/profile", methods=["PUT"])
@require_any_permission(
    PERMISSION_EMPLOYEE_UPDATE,
    PERMISSION_EMPLOYEE_UPDATE_LIMITED,
    PERMISSION_EMPLOYEE_SELF_UPDATE,
)
def update_profile():
    """Update the caller's phone using their existing employee permissions."""

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("Request body must be a JSON object", 400)

    user = get_current_user()
    allowed_fields = PROFILE_UPDATE_FIELDS.intersection(
        employee_service.update_fields_for(user.permissions)
    )
    try:
        values = employee_service.validate_update_payload(data, allowed_fields)
    except employee_service.EmployeeValidationError as error:
        return _error(str(error), 400)

    if user.employee_id is None:
        return _error("No employee profile is linked to this account", 404)

    connection = get_connection()
    try:
        current = employee_service.get_employee(connection, user.employee_id)
        if current is None:
            return _error("No employee profile is linked to this account", 404)
        employee_service.update_employee(
            connection, user.employee_id, values, user.id
        )
        connection.commit()
        response = _profile_response(user, connection)
        response["employee"] = _serialize_employee(
            _profile_employee(connection, user.employee_id)
        )
        return jsonify(response), 200
    finally:
        connection.close()
