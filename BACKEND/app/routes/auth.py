
"""Authentication API endpoints."""

from flask import Blueprint, jsonify, request, session

from app.db import get_connection
from app.services.auth import authenticate_user


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Authenticate a user and create a session."""

    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({
            "success": False,
            "message": "Username and password are required"
        }), 400

    username = username.strip()

    if not username or not password:
        return jsonify({
            "success": False,
            "message": "Username and password are required"
        }), 400

    user = authenticate_user(username, password)

    if not user:
        return jsonify({
            "success": False,
            "message": "Invalid username or password"
        }), 401

    session.clear()
    session["user_id"] = user["id"]

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "roles": user["roles"]
        }
    }), 200


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    """Destroy the current login session."""

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logout successful"
    }), 200


@auth_bp.route("/auth/me", methods=["GET"])
def current_user():
    """Return the currently authenticated user."""

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Authentication required"
        }), 401

    connection = get_connection()

    try:
        user = connection.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE id = ? AND is_active = 1
            """,
            (user_id,)
        ).fetchone()

        if not user:
            session.clear()
            return jsonify({
                "success": False,
                "message": "Authentication required"
            }), 401

        roles = connection.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = ?
            ORDER BY r.name
            """,
            (user_id,)
        ).fetchall()

        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "roles": [role["name"] for role in roles]
            }
        }), 200

    finally:
        connection.close()
