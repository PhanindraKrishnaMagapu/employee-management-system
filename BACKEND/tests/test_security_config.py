"""Regression tests for startup secret rules and API default-deny coverage.

All app instances are created against the isolated temporary database fixture;
the local SQLite file is never opened.
"""

import pytest

from app import create_app
from app.config import DEFAULT_SECRET_KEY, Config


def test_unknown_environment_still_requires_a_real_secret(monkeypatch, isolated_db):
    """Any environment outside the dev allowlist is treated as deployed."""

    monkeypatch.setenv("FLASK_ENV", "staging")
    monkeypatch.setattr(Config, "SECRET_KEY", DEFAULT_SECRET_KEY)

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app()


def test_unknown_environment_with_real_secret_enables_secure_cookies(
    monkeypatch, isolated_db
):
    monkeypatch.setenv("FLASK_ENV", "staging")
    monkeypatch.setattr(Config, "SECRET_KEY", "staging-test-secret-key")

    application = create_app()

    assert application.config["SESSION_COOKIE_SECURE"] is True


def test_development_environment_allows_the_default_secret(monkeypatch, isolated_db):
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setattr(Config, "SECRET_KEY", DEFAULT_SECRET_KEY)

    application = create_app()

    assert application.config["SESSION_COOKIE_SECURE"] is False


def test_exact_api_path_requires_authentication(client):
    """The /api path itself must not slip past the default-deny hook."""

    response = client.get("/api")

    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "message": "Authentication required",
    }
