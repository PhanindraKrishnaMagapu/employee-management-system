"""Shared pytest fixtures using isolated temporary databases."""

from flask import Blueprint, abort, jsonify
import pytest

from app import create_app
from app.auth.context import get_current_user
from app.auth.decorators import (
    require_all_permissions,
    require_any_permission,
    require_authentication,
    require_permission,
)
from app.auth import permissions as perms
from app.config import Config
from app.db import get_connection, initialize_database
from app.services.authorization import require_employee_access


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Create a freshly seeded database in a temporary directory.

    The real development database is never opened by tests that use this
    fixture, because every connection reads Config.DATABASE_PATH at call time.
    """
    database_path = tmp_path / "test_ems.sqlite"
    monkeypatch.setattr(Config, "DATABASE_PATH", str(database_path))
    monkeypatch.delenv("FLASK_ENV", raising=False)
    initialize_database()
    return database_path


@pytest.fixture
def app(isolated_db, monkeypatch):
    """Create a Flask app whose requests use the isolated temp database."""
    monkeypatch.setattr(Config, "SECRET_KEY", "auth-test-secret-key")
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    """Flask test client for API requests."""
    return app.test_client()


def create_rbac_test_blueprint():
    """Build endpoints that use the real decorators, for tests only.

    This factory lives in the test package and is never imported by the
    production application. No employee or salary business API is created.
    """

    blueprint = Blueprint("rbac_test", __name__)

    def _ok(message):
        return jsonify({"success": True, "message": message}), 200

    @blueprint.route("/api/rbac-test/open", methods=["GET"])
    def open_endpoint():
        # Intentionally undecorated: default-deny must block this endpoint.
        return _ok("This endpoint must not be reachable")

    @blueprint.route("/api/rbac-test/authenticated", methods=["GET"])
    @require_authentication
    def authenticated_endpoint():
        return _ok("Authenticated")

    @blueprint.route("/api/rbac-test/employee/<int:employee_id>", methods=["GET"])
    @require_any_permission(
        perms.PERMISSION_EMPLOYEE_READ_ALL,
        perms.PERMISSION_EMPLOYEE_READ_SCOPE,
    )
    def employee_endpoint(employee_id):
        connection = get_connection()
        try:
            exists = connection.execute(
                "SELECT 1 FROM employees WHERE id = ?", (employee_id,)
            ).fetchone()
            if exists is None:
                abort(404)
            require_employee_access(get_current_user(), employee_id, connection)
        finally:
            connection.close()
        return jsonify({"success": True, "employee_id": employee_id}), 200

    @blueprint.route("/api/rbac-test/salary", methods=["GET"])
    @require_permission(perms.PERMISSION_SALARY_READ)
    def salary_endpoint():
        return _ok("Salary permission granted")

    @blueprint.route("/api/rbac-test/users", methods=["GET"])
    @require_permission(perms.PERMISSION_USER_MANAGE)
    def users_endpoint():
        return _ok("User administration permission granted")

    @blueprint.route("/api/rbac-test/hr-create", methods=["POST"])
    @require_permission(perms.PERMISSION_EMPLOYEE_CREATE)
    def hr_create_endpoint():
        return _ok("HR create permission granted")

    @blueprint.route("/api/rbac-test/either", methods=["GET"])
    @require_any_permission(
        perms.PERMISSION_USER_MANAGE,
        perms.PERMISSION_SALARY_READ,
    )
    def either_endpoint():
        return _ok("At least one permission granted")

    @blueprint.route("/api/rbac-test/both", methods=["GET"])
    @require_all_permissions(
        perms.PERMISSION_USER_MANAGE,
        perms.PERMISSION_ROLE_MANAGE,
    )
    def both_endpoint():
        return _ok("All permissions granted")

    @blueprint.route("/api/rbac-test/report", methods=["GET"])
    @require_permission(perms.PERMISSION_REPORT_READ)
    def report_endpoint():
        return _ok("Report permission granted")

    return blueprint


@pytest.fixture
def rbac_client(app):
    """Test client with the RBAC test blueprint registered on this app only."""

    app.register_blueprint(create_rbac_test_blueprint())
    return app.test_client()
