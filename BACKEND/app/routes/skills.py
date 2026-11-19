"""Skill catalog API endpoints with RBAC enforcement."""

import sqlite3

from flask import Blueprint, abort, jsonify, request

from app.auth.decorators import require_any_permission, require_permission
from app.auth.permissions import (
    PERMISSION_SKILLS_MANAGE,
    PERMISSION_SKILLS_READ,
)
from app.db import get_connection
from app.services import skills as skill_service


skills_bp = Blueprint("skills", __name__)


def _error(message, status):
    return jsonify({"success": False, "message": message}), status


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@skills_bp.route("", methods=["GET"])
@require_any_permission(PERMISSION_SKILLS_READ, PERMISSION_SKILLS_MANAGE)
def list_skills():
    """List the skill catalog, optionally filtered by search text."""

    search = request.args.get("search", "").strip()
    connection = get_connection()
    try:
        rows = skill_service.list_skills(connection, search)
        return jsonify({
            "success": True,
            "skills": [skill_service.serialize_skill(row) for row in rows],
        }), 200
    finally:
        connection.close()


@skills_bp.route("", methods=["POST"])
@require_permission(PERMISSION_SKILLS_MANAGE)
def create_skill():
    """Create a skill. Requires the explicit manage permission."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    try:
        values = skill_service.validate_skill_payload(data)
    except skill_service.SkillValidationError as error:
        return _error(str(error), 400)

    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = skill_service.create_skill(connection, values)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Skill created",
            "skill": skill_service.serialize_skill(row),
        }), 201
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Skill name already exists", 409)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@skills_bp.route("/<int:skill_id>", methods=["PUT"])
@require_permission(PERMISSION_SKILLS_MANAGE)
def update_skill(skill_id):
    """Partially update an existing skill."""

    data = _json_object()
    if data is None:
        return _error("Request body must be a JSON object", 400)

    connection = get_connection()
    try:
        current = skill_service.get_skill(connection, skill_id)
        if current is None:
            abort(404)
        try:
            values = skill_service.validate_skill_payload(data, current)
        except skill_service.SkillValidationError as error:
            return _error(str(error), 400)

        connection.execute("BEGIN IMMEDIATE")
        row = skill_service.update_skill(connection, skill_id, values)
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Skill updated",
            "skill": skill_service.serialize_skill(row),
        }), 200
    except sqlite3.IntegrityError:
        connection.rollback()
        return _error("Skill name already exists", 409)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
