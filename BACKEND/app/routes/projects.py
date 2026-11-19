"""Project and assignment API endpoints with RBAC and employee scoping."""

import sqlite3

from flask import Blueprint, abort, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import (
    require_all_permissions,
    require_any_permission,
    require_permission,
)
from app.auth.permissions import (
    PERMISSION_EMPLOYEE_READ_ALL,
    PERMISSION_PROJECT_MANAGE,
    PERMISSION_PROJECT_READ,
    ROLE_HR_ADMIN,
    ROLE_PROJECT_MANAGER,
)
from app.db import get_connection
from app.services import projects as project_service


projects_bp = Blueprint("projects", __name__)


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _project_for_user(connection, project_id, user):
    """Return a project only when it is inside the caller's project scope."""

    project = project_service.get_project(connection, project_id)
    if project is None or not project_service.can_access_project(user, project):
        abort(404)
    return project


def _is_project_manager_only(user):
    return (
        user is not None
        and ROLE_PROJECT_MANAGER in user.roles
        and ROLE_HR_ADMIN not in user.roles
    )


def _manager_id_from_payload(data):
    """Validate an optional HR-admin-supplied project manager id."""

    if "manager_id" not in data or data["manager_id"] is None:
        return None
    value = data["manager_id"]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise project_service.ProjectValidationError(
            "manager_id must be a positive integer"
        )
    return value


def _assignment_payload(connection, project_id, scope):
    project = project_service.get_project(connection, project_id)
    if project is None:
        abort(404)

    assignments = project_service.list_assignments(connection, project_id, scope)
    return project, [
        project_service.serialize_assignment(
            row, project_service.get_employee_public(connection, row["employee_id"])
        )
        for row in assignments
    ]


@projects_bp.route("", methods=["GET"])
@require_any_permission(PERMISSION_PROJECT_READ, PERMISSION_PROJECT_MANAGE)
def list_projects():
    """List active projects with assignment counts visible to the caller."""

    user = get_current_user()
    connection = get_connection()
    try:
        scope = project_service.visible_employee_ids(user, connection)
        rows = project_service.visible_projects(connection, user)
        counts = project_service.assignment_counts(
            connection, [row["id"] for row in rows], scope
        )
        projects = [
            project_service.serialize_project(
                row, counts.get(row["id"], 0)
            )
            for row in rows
        ]
        return jsonify({"success": True, "projects": projects}), 200
    finally:
        connection.close()


@projects_bp.route("/assignable-employees", methods=["GET"])
@require_all_permissions(PERMISSION_PROJECT_MANAGE, PERMISSION_EMPLOYEE_READ_ALL)
def list_assignable_employees():
    """Return active employees for the project-only employee picker."""

    connection = get_connection()
    try:
        user = get_current_user()
        scope = project_service.visible_employee_ids(user, connection)
        employees = project_service.list_assignable_employees(connection, scope)
        return jsonify({"success": True, "employees": employees}), 200
    finally:
        connection.close()


@projects_bp.route("/<int:project_id>", methods=["GET"])
@require_any_permission(PERMISSION_PROJECT_READ, PERMISSION_PROJECT_MANAGE)
def get_project(project_id):
    """Return project details and visible assignments."""

    user = get_current_user()
    connection = get_connection()
    try:
        _project_for_user(connection, project_id, user)
        scope = project_service.visible_employee_ids(user, connection)
        project, assignments = _assignment_payload(connection, project_id, scope)
        return jsonify({
            "success": True,
            "project": project_service.serialize_project(
                project, len(assignments)
            ),
            "assignments": assignments,
        }), 200
    finally:
        connection.close()


@projects_bp.route("/<int:project_id>/employees", methods=["GET"])
@require_any_permission(PERMISSION_PROJECT_READ, PERMISSION_PROJECT_MANAGE)
def list_project_employees(project_id):
    """Return employees assigned to a project within the caller's scope."""

    user = get_current_user()
    connection = get_connection()
    try:
        _project_for_user(connection, project_id, user)
        scope = project_service.visible_employee_ids(user, connection)
        _, assignments = _assignment_payload(connection, project_id, scope)
        employees = [assignment["employee"] for assignment in assignments]
        return jsonify({
            "success": True,
            "employees": employees,
            "assignments": assignments,
        }), 200
    finally:
        connection.close()


@projects_bp.route("", methods=["POST"])
@require_permission(PERMISSION_PROJECT_MANAGE)
def create_project():
    """Create a project."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    user = get_current_user()
    if _is_project_manager_only(user):
        if "manager_id" in data:
            return _error("Only HR Admin can assign a project manager", 400)
        if user.employee_id is None:
            return _error(
                "Project Manager account must be linked to an employee", 400
            )
        manager_id = user.employee_id
    else:
        manager_id = None

    try:
        values = project_service.validate_project_payload(data)
        if not _is_project_manager_only(user):
            manager_id = _manager_id_from_payload(data)
    except project_service.ProjectValidationError as error:
        return _error(str(error), 400)
    values["manager_id"] = manager_id

    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = project_service.create_project(connection, values)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Project created",
            "project": project_service.serialize_project(row),
        }), 201
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Project code already exists", 409)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@require_permission(PERMISSION_PROJECT_MANAGE)
def update_project(project_id):
    """Partially update an existing project."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    user = get_current_user()
    if _is_project_manager_only(user) and "manager_id" in data:
        return _error("Only HR Admin can assign a project manager", 400)

    connection = get_connection()
    try:
        project = _project_for_user(connection, project_id, user)
        try:
            values = project_service.validate_project_payload(data, project)
        except project_service.ProjectValidationError as error:
            return _error(str(error), 400)

        connection.execute("BEGIN IMMEDIATE")
        row = project_service.update_project(connection, project_id, values)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Project updated",
            "project": project_service.serialize_project(row),
        }), 200
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Project code already exists", 409)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@projects_bp.route("/<int:project_id>/assignments", methods=["POST"])
@require_permission(PERMISSION_PROJECT_MANAGE)
def create_assignment(project_id):
    """Assign an active employee to a project."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = project_service.validate_assignment_payload(data)
    except project_service.ProjectValidationError as error:
        return _error(str(error), 400)

    user = get_current_user()
    connection = get_connection()
    try:
        project = _project_for_user(connection, project_id, user)

        employee_id = values["employee_id"]
        scope = project_service.visible_employee_ids(user, connection)
        if scope is not None and employee_id not in scope:
            abort(404)
        if not project_service.active_employee_exists(connection, employee_id):
            return _error(
                "employee_id must reference an active employee", 400
            )
        if project_service.assignment_exists(connection, project_id, employee_id):
            return _error(
                "Employee is already assigned to this project", 409
            )

        connection.execute("BEGIN IMMEDIATE")
        row = project_service.create_assignment(connection, project_id, values)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Employee assigned to project",
            "assignment": project_service.serialize_assignment(
                row,
                project_service.get_employee_public(connection, employee_id),
            ),
        }), 201
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Invalid project or employee reference", 400)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@projects_bp.route(
    "/<int:project_id>/assignments/<int:assignment_id>", methods=["DELETE"]
)
@require_permission(PERMISSION_PROJECT_MANAGE)
def delete_assignment(project_id, assignment_id):
    """Remove an employee assignment from a project."""

    user = get_current_user()
    connection = get_connection()
    try:
        _project_for_user(connection, project_id, user)
        scope = project_service.visible_employee_ids(user, connection)
        assignment = project_service.get_assignment(
            connection, project_id, assignment_id, scope
        )
        if assignment is None:
            abort(404)

        connection.execute("BEGIN IMMEDIATE")
        project_service.delete_assignment(connection, assignment_id)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Employee assignment removed",
        }), 200
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
