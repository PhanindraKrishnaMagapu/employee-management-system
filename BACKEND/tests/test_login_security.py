"""Regression tests for login throttling and username-enumeration defenses.

Every test uses the client fixture, whose isolated_db keeps the local SQLite
file untouched. The autouse throttle fixture also prevents state leakage.
"""

from app.db import get_connection
from app.services import auth as auth_service
from app.services.auth import hash_password


PASSWORD = "LoginSecurity!234"


def _set_password(username):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(PASSWORD), username),
        )
        connection.commit()
    finally:
        connection.close()


def _set_active(username, is_active):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET is_active = ? WHERE username = ?",
            (is_active, username),
        )
        connection.commit()
    finally:
        connection.close()


def _login(client, username, password):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def _spying_verifier(monkeypatch):
    """Wrap verify_password and record the hashes it is asked to check."""

    calls = []
    original = auth_service.verify_password

    def spy(password, password_hash):
        calls.append(password_hash)
        return original(password, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", spy)
    return calls


def test_unknown_username_still_verifies_a_dummy_hash(client, monkeypatch):
    calls = _spying_verifier(monkeypatch)

    response = _login(client, "ghost_user", "any-password")

    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "message": "Invalid username or password",
    }
    assert auth_service._DUMMY_PASSWORD_HASH in calls


def test_inactive_username_also_verifies_a_dummy_hash(client, monkeypatch):
    _set_password("demo_ceo")
    _set_active("demo_ceo", 0)
    calls = _spying_verifier(monkeypatch)

    response = _login(client, "demo_ceo", PASSWORD)

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid username or password"
    assert auth_service._DUMMY_PASSWORD_HASH in calls


def test_repeated_failures_are_throttled(client):
    attempts = {"username": "demo_ceo", "password": "wrong-password"}

    for _ in range(auth_service.MAX_FAILED_ATTEMPTS):
        response = _login(client, **attempts)
        assert response.status_code == 401, response.get_json()

    blocked = _login(client, **attempts)
    assert blocked.status_code == 429, blocked.get_json()
    assert "Too many login attempts" in blocked.get_json()["message"]

    # Even correct credentials cannot bypass an active throttle window.
    _set_password("demo_ceo")
    assert _login(client, "demo_ceo", PASSWORD).status_code == 429


def test_throttle_is_scoped_per_username(client):
    attempts = {"username": "demo_ceo", "password": "wrong-password"}
    for _ in range(auth_service.MAX_FAILED_ATTEMPTS):
        assert _login(client, **attempts).status_code == 401
    assert _login(client, **attempts).status_code == 429

    # A different username from the same client is unaffected.
    _set_password("demo_employee")
    assert _login(client, "demo_employee", PASSWORD).status_code == 200


def test_successful_login_clears_prior_failures(client):
    _set_password("demo_ceo")
    for _ in range(auth_service.MAX_FAILED_ATTEMPTS - 1):
        assert _login(client, "demo_ceo", "wrong-password").status_code == 401

    assert _login(client, "demo_ceo", PASSWORD).status_code == 200

    for _ in range(auth_service.MAX_FAILED_ATTEMPTS):
        assert _login(client, "demo_ceo", "wrong-password").status_code == 401
    assert _login(client, "demo_ceo", "wrong-password").status_code == 429
