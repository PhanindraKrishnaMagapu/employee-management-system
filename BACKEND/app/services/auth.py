"""Authentication, password and login-throttling utilities."""

import threading
import time

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_connection


# A real hash for a value no account can use. Unknown/inactive users are still
# verified against it so response timing does not reveal account existence.
_DUMMY_PASSWORD_HASH = generate_password_hash("login-throttling-dummy-value")

# Simple per-(client, username) throttle. Five failures in five minutes block
# further attempts for the remainder of the window; a successful login clears
# the counter. This is intentionally in-process for this single-app deployment.
MAX_FAILED_ATTEMPTS = 5
THROTTLE_WINDOW_SECONDS = 300
_lock = threading.Lock()
_failed_attempts = {}


def _throttle_key(client_ip, username):
    return (client_ip or "unknown", (username or "").strip().lower())


def is_login_throttled(client_ip, username):
    """Return True when this client has exhausted its failure allowance."""

    key = _throttle_key(client_ip, username)
    now = time.monotonic()
    with _lock:
        record = _failed_attempts.get(key)
        if record is None:
            return False
        count, started_at = record
        if now - started_at >= THROTTLE_WINDOW_SECONDS:
            _failed_attempts.pop(key, None)
            return False
        return count >= MAX_FAILED_ATTEMPTS


def record_login_failure(client_ip, username):
    """Record one failed login attempt."""

    key = _throttle_key(client_ip, username)
    now = time.monotonic()
    with _lock:
        count, started_at = _failed_attempts.get(key, (0, now))
        if now - started_at >= THROTTLE_WINDOW_SECONDS:
            count, started_at = 0, now
        _failed_attempts[key] = (count + 1, started_at)


def clear_login_failures(client_ip, username):
    """Clear failures for a successful login."""

    with _lock:
        _failed_attempts.pop(_throttle_key(client_ip, username), None)


def reset_login_throttling():
    """Clear all throttle state (used by the test suite)."""

    with _lock:
        _failed_attempts.clear()


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
            # Spend the same hashing effort as a real account so response time
            # cannot be used to enumerate usernames.
            verify_password(password, _DUMMY_PASSWORD_HASH)
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
