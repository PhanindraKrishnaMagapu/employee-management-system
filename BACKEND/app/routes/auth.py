
"""Authentication API endpoints."""

from flask import Blueprint, jsonify, request, session

from app.auth.context import get_current_user
from app.auth.decorators import require_authentication
from app.services.auth import authenticate_user


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Authenticate a user and create a session."""

    data = request.get_json(silent=True)

    # A valid JSON scalar or array has no .get(); treat every non-object body
    # as a bad request instead of letting it become a 500 error.
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Username and password are required"
        }), 400

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
    # Apply the configured PERMANENT_SESSION_LIFETIME to the login cookie.
    session.permanent = True
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
@require_authentication
def logout():
    """Destroy the current login session."""

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logout successful"
    }), 200


@auth_bp.route("/auth/me", methods=["GET"])
@require_authentication
def current_user():
    """Return the currently authenticated user."""

    user = get_current_user()

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": list(user.roles)
        }
    }), 200
