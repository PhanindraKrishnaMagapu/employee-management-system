
"""Authentication and password utilities."""

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_connection


def hash_password(password):
    """Generate a secure password hash."""
    return generate_password_hash(password)


def verify_password(password, password_hash):
    """Verify a password against its stored hash."""
    if not password_hash or password_hash == "NOT_A_REAL_PASSWORD_HASH":
        return False

    return check_password_hash(password_hash, password)


def authenticate_user(username, password):
    """Authenticate an active user and return their details."""
    connection = get_connection()

    try:
        user = connection.execute(
            """
            SELECT id, username, email, password_hash, is_active
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if not user or not user["is_active"]:
            return None

        if not verify_password(password, user["password_hash"]):
            return None

        roles = connection.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = ?
            ORDER BY r.name
            """,
            (user["id"],)
        ).fetchall()

        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "roles": [role["name"] for role in roles]
        }

    finally:
        connection.close()
