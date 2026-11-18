"""Tests for the authentication API and session security configuration.

Every test uses the isolated_db fixture through app/client, so no request in
this module can reach BACKEND/database/ems.sqlite.
"""

from datetime import timedelta

import pytest

from app import create_app
from app.config import DEFAULT_SECRET_KEY, Config
from app.db import get_connection
from app.services.auth import authenticate_user, hash_password, verify_password


PASSWORD = "AuthTest!234"
DEMO_USER = "demo_ceo"


def _set_password(username, password):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(password), username),
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


def _user_id(username):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row["id"]
    finally:
        connection.close()


def _roles_for(username):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            JOIN users u ON u.id = ur.user_id
            WHERE u.username = ?
            ORDER BY r.name
            """,
            (username,),
        ).fetchall()
        return [row["name"] for row in rows]
    finally:
        connection.close()


def _login(client, username=DEMO_USER, password=PASSWORD):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


@pytest.fixture
def logged_in_client(client):
    _set_password(DEMO_USER, PASSWORD)
    assert _login(client).status_code == 200
    return client


# ---------------------------------------------------------------------------
# Login: success and credential failures
# ---------------------------------------------------------------------------

def test_login_success_returns_user_and_creates_session(client):
    _set_password(DEMO_USER, PASSWORD)

    response = _login(client)
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Login successful"
    assert set(body) == {"success", "message", "user"}

    user = body["user"]
    assert set(user) == {"id", "username", "email", "roles"}
    assert user["username"] == DEMO_USER
    assert user["email"] == "ceo@example.invalid"
    assert user["roles"] == _roles_for(DEMO_USER)
    assert user["roles"] == sorted(user["roles"])

    with client.session_transaction() as session:
        assert session["user_id"] == user["id"]


def test_login_failures_are_generic_and_identical(client):
    _set_password(DEMO_USER, PASSWORD)

    wrong_password = _login(client, username=DEMO_USER, password="wrong")
    unknown_user = _login(client, username="ghost_user", password=PASSWORD)

    expected = {"success": False, "message": "Invalid username or password"}
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.get_json() == expected
    assert unknown_user.get_json() == expected

    with client.session_transaction() as session:
        assert "user_id" not in session


def test_login_rejects_inactive_user(client):
    _set_password(DEMO_USER, PASSWORD)
    _set_active(DEMO_USER, 0)

    response = _login(client)

    assert response.status_code == 401
    assert response.get_json()["message"] == "Invalid username or password"
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_login_rejects_placeholder_password_hash(client):
    # The seed script leaves placeholder hashes in the temporary test DB.
    response = _login(client, username="demo_employee", password=PASSWORD)

    assert response.status_code == 401
    assert response.get_json()["success"] is False


# ---------------------------------------------------------------------------
# Login: invalid request bodies
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": DEMO_USER},
        {"password": PASSWORD},
        {"username": "", "password": PASSWORD},
        {"username": "   ", "password": PASSWORD},
        {"username": DEMO_USER, "password": ""},
        {"username": 123, "password": PASSWORD},
        {"username": DEMO_USER, "password": 123},
        {"username": [DEMO_USER], "password": PASSWORD},
        {"username": DEMO_USER, "password": None},
    ],
)
def test_login_invalid_fields_return_400(client, payload):
    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Username and password are required",
    }


def test_login_malformed_json_returns_400(client):
    response = client.post(
        "/api/auth/login", data="{not-json", content_type="application/json"
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False


@pytest.mark.parametrize("body", ['["x"]', '"text"', "123", "true"])
def test_login_non_object_json_body_returns_400(client, body):
    response = client.post("/api/auth/login", data=body, content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Username and password are required",
    }


def test_login_without_json_body_returns_400(client):
    response = client.post("/api/auth/login")

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_login_strips_surrounding_username_whitespace(client):
    _set_password(DEMO_USER, PASSWORD)

    response = client.post(
        "/api/auth/login",
        json={"username": "  demo_ceo  ", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == DEMO_USER


# ---------------------------------------------------------------------------
# Login: session handling
# ---------------------------------------------------------------------------

def test_login_clears_preexisting_session(client):
    _set_password(DEMO_USER, PASSWORD)
    with client.session_transaction() as session:
        session["stale_key"] = "stale_value"

    _login(client)

    with client.session_transaction() as session:
        assert "stale_key" not in session
        assert session["user_id"] == _user_id(DEMO_USER)


def test_repeated_login_replaces_previous_session(client):
    _set_password(DEMO_USER, PASSWORD)
    _set_password("demo_employee", PASSWORD)

    assert _login(client, DEMO_USER).status_code == 200
    assert _login(client, "demo_employee").status_code == 200

    with client.session_transaction() as session:
        assert session["user_id"] == _user_id("demo_employee")

    me = client.get("/api/auth/me")
    assert me.get_json()["user"]["username"] == "demo_employee"


def test_login_sets_hardened_permanent_session_cookie(client):
    _set_password(DEMO_USER, PASSWORD)

    response = _login(client)
    cookie = response.headers["Set-Cookie"]

    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie
    assert "Expires=" in cookie
    with client.session_transaction() as session:
        assert session.permanent is True


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_clears_session_and_blocks_me(logged_in_client):
    response = logged_in_client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "message": "Logout successful"}
    with logged_in_client.session_transaction() as session:
        assert "user_id" not in session
    assert logged_in_client.get("/api/auth/me").status_code == 401


def test_logout_without_session_is_rejected(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "message": "Authentication required",
    }


# ---------------------------------------------------------------------------
# Current user (/me)
# ---------------------------------------------------------------------------

def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "message": "Authentication required",
    }


def test_me_returns_current_user(logged_in_client):
    response = logged_in_client.get("/api/auth/me")
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert set(body) == {"success", "user"}
    assert body["user"]["username"] == DEMO_USER
    assert body["user"]["roles"] == _roles_for(DEMO_USER)
    assert body["user"]["roles"] == sorted(body["user"]["roles"])


def test_me_matches_login_user_payload(client):
    _set_password(DEMO_USER, PASSWORD)
    login_user = _login(client).get_json()["user"]
    me_user = client.get("/api/auth/me").get_json()["user"]

    assert me_user == login_user


def test_me_rejects_deleted_user(logged_in_client):
    user_id = _user_id(DEMO_USER)
    connection = get_connection()
    try:
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()

    response = logged_in_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.get_json()["message"] == "Authentication required"
    with logged_in_client.session_transaction() as session:
        assert "user_id" not in session


def test_me_rejects_deactivated_user(logged_in_client):
    _set_active(DEMO_USER, 0)

    response = logged_in_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.get_json()["message"] == "Authentication required"
    with logged_in_client.session_transaction() as session:
        assert "user_id" not in session


# ---------------------------------------------------------------------------
# Response contract and configuration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/auth/login"),
        ("post", "/api/auth/logout"),
        ("get", "/api/auth/me"),
    ],
)
def test_auth_responses_are_json_with_success_flag(client, method, path):
    response = getattr(client, method)(path)

    assert response.is_json
    assert "success" in response.get_json()


def test_session_security_configuration(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=8)


def test_production_rejects_default_secret_key(monkeypatch, isolated_db):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", DEFAULT_SECRET_KEY)

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app()


@pytest.mark.parametrize("secret_key", [None, "", "   ", "\t\n "])
def test_production_rejects_missing_or_blank_secret_key(
    monkeypatch, isolated_db, secret_key
):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", secret_key)

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app()


def test_production_with_custom_secret_key_enables_secure_cookies(
    monkeypatch, isolated_db
):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", "production-test-secret")

    application = create_app()

    assert application.config["SESSION_COOKIE_SECURE"] is True


# ---------------------------------------------------------------------------
# Service-level checks exercised through the same isolated database
# ---------------------------------------------------------------------------

def test_password_hashing_and_verification(isolated_db):
    hashed = hash_password(PASSWORD)

    assert hashed != PASSWORD
    assert verify_password(PASSWORD, hashed) is True
    assert verify_password("other-password", hashed) is False
    assert verify_password(PASSWORD, "NOT_A_REAL_PASSWORD_HASH") is False
    assert verify_password(PASSWORD, None) is False


def test_authenticate_user_rejects_invalid_cases(isolated_db):
    _set_password(DEMO_USER, PASSWORD)

    assert authenticate_user(DEMO_USER, PASSWORD)["username"] == DEMO_USER
    assert authenticate_user(DEMO_USER, "wrong") is None
    assert authenticate_user("ghost_user", PASSWORD) is None
    assert authenticate_user("demo_employee", PASSWORD) is None

    _set_active(DEMO_USER, 0)
    assert authenticate_user(DEMO_USER, PASSWORD) is None
