"""Employee skill assignment API endpoints with RBAC and employee scoping."""

import sqlite3

from flask import Blueprint, abort, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import require_any_permission, require_permission
from app.auth.permissions import (
    PERMISSION_SKILLS_MANAGE,
    PERMISSION_SKILLS_READ,
)
from app.db import get_connection
from app.services import skills as skill_service
from app.services.authorization import require_employee_access


employee_skills_bp = Blueprint("employee_skills", __name__)


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _require_scoped_employee(connection, employee_id):
    user = get_current_user()
    employee = skill_service.get_public_employee(connection, employee_id)
    if employee is None:
        abort(404)
    require_employee_access(user, employee_id, connection)
    return employee


@employee_skills_bp.route("/<int:employee_id>/skills", methods=["GET"])
@require_any_permission(PERMISSION_SKILLS_READ, PERMISSION_SKILLS_MANAGE)
def list_employee_skills(employee_id):
    """List skills assigned to an employee within the caller's scope."""

    connection = get_connection()
    try:
        employee = _require_scoped_employee(connection, employee_id)
        rows = skill_service.list_assignments(connection, employee_id)
        assignments = []
        for row in rows:
            skill = skill_service.get_skill(connection, row["skill_id"])
            assignments.append(
                skill_service.serialize_assignment(row, skill, employee)
            )
        return jsonify({
            "success": True,
            "employee": employee,
            "assignments": assignments,
        }), 200
    finally:
        connection.close()


@employee_skills_bp.route("/<int:employee_id>/skills", methods=["POST"])
@require_permission(PERMISSION_SKILLS_MANAGE)
def create_employee_skill(employee_id):
    """Assign a skill to an active employee within the caller's scope."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = skill_service.validate_assignment_payload(data)
    except skill_service.SkillValidationError as error:
        return _error(str(error), 400)

    connection = get_connection()
    try:
        employee = _require_scoped_employee(connection, employee_id)
        if not skill_service.active_employee_exists(connection, employee_id):
            return _error("Only Active employees can receive skill assignments", 400)
        if not skill_service.skill_exists(connection, values["skill_id"]):
            return _error("skill_id must reference an existing skill", 400)
        if skill_service.assignment_exists(
            connection, employee_id, values["skill_id"]
        ):
            return _error("Employee is already assigned this skill", 409)

        connection.execute("BEGIN IMMEDIATE")
        row = skill_service.create_assignment(connection, employee_id, values)
        connection.commit()
        skill = skill_service.get_skill(connection, row["skill_id"])
        return jsonify({
            "success": True,
            "message": "Skill assigned to employee",
            "assignment": skill_service.serialize_assignment(row, skill, employee),
        }), 201
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Employee is already assigned this skill", 409)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@employee_skills_bp.route(
    "/<int:employee_id>/skills/<int:assignment_id>", methods=["PUT"]
)
@require_permission(PERMISSION_SKILLS_MANAGE)
def update_employee_skill(employee_id, assignment_id):
    """Update an employee skill assignment within the caller's scope."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = skill_service.validate_assignment_update_payload(data)
    except skill_service.SkillValidationError as error:
        return _error(str(error), 400)

    connection = get_connection()
    try:
        employee = _require_scoped_employee(connection, employee_id)
        assignment = skill_service.get_assignment(
            connection, employee_id, assignment_id
        )
        if assignment is None:
            abort(404)

        connection.execute("BEGIN IMMEDIATE")
        row = skill_service.update_assignment(connection, assignment_id, values)
        connection.commit()
        skill = skill_service.get_skill(connection, row["skill_id"])
        return jsonify({
            "success": True,
            "message": "Employee skill updated",
            "assignment": skill_service.serialize_assignment(row, skill, employee),
        }), 200
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@employee_skills_bp.route(
    "/<int:employee_id>/skills/<int:assignment_id>", methods=["DELETE"]
)
@require_permission(PERMISSION_SKILLS_MANAGE)
def delete_employee_skill(employee_id, assignment_id):
    """Remove a skill assignment from an employee within the caller's scope."""

    connection = get_connection()
    try:
        _require_scoped_employee(connection, employee_id)
        assignment = skill_service.get_assignment(
            connection, employee_id, assignment_id
        )
        if assignment is None:
            abort(404)

        connection.execute("BEGIN IMMEDIATE")
        skill_service.delete_assignment(connection, assignment_id)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Employee skill removed",
        }), 200
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
