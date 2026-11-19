"""Flask application factory for Employee Management System."""

from flask import Flask, current_app, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import AUTHENTICATION_REQUIRED, PERMISSION_DENIED
from app.auth.permissions import (
    PERMISSION_EMPLOYEE_READ_ALL,
    PERMISSION_EMPLOYEE_READ_SCOPE,
    ROLE_PROJECT_MANAGER,
    permissions_for_roles,
)
from app.config import DEFAULT_SECRET_KEY, Config, is_development
from app.routes.health import health_bp
from app.routes.auth import auth_bp
from app.routes.employees import employees_bp
from app.routes.employee_skills import employee_skills_bp
from app.routes.jml import jml_bp
from app.routes.projects import projects_bp
from app.routes.salaries import salaries_bp
from app.routes.skills import skills_bp
from app.routes.ui import ui_bp


# Deliberately small: every other /api/* route is authenticated by default and
# must also be marked by a real authorization decorator to be reachable.
PUBLIC_API_ENDPOINTS = frozenset({
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
})


def _project_only_employee_grant(user):
    """Block the project picker grant from becoming general employee access.

    Project Managers need employees:read:all for project assignment only. If
    that is their only employee-read source, the general Employees API (also
    used by Hierarchy) stays closed. Combined roles keep their own access.
    """

    if user is None or ROLE_PROJECT_MANAGER not in user.roles:
        return False
    path = request.path
    if not (path.startswith("/api/employees") or path.startswith("/api/hierarchy")):
        return False

    other_roles = tuple(role for role in user.roles if role != ROLE_PROJECT_MANAGER)
    other_permissions = permissions_for_roles(other_roles)
    return not other_permissions.intersection({
        PERMISSION_EMPLOYEE_READ_ALL,
        PERMISSION_EMPLOYEE_READ_SCOPE,
    })


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

    secret_key = app.config.get("SECRET_KEY")
    normalized_key = secret_key.strip() if isinstance(secret_key, str) else ""
    if (not normalized_key or normalized_key == DEFAULT_SECRET_KEY) and not is_development():
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set to a non-default value outside "
            "an explicitly recognized development environment"
        )

    # Secure cookies are required outside development; evaluate at startup so
    # environment changes after import are respected.
    app.config["SESSION_COOKIE_SECURE"] = not is_development()

    # Register API blueprints
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(employees_bp, url_prefix="/api/employees")
    app.register_blueprint(employee_skills_bp, url_prefix="/api/employees")
    app.register_blueprint(jml_bp, url_prefix="/api/jml")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(salaries_bp, url_prefix="/api/salaries")
    app.register_blueprint(skills_bp, url_prefix="/api/skills")
    app.register_blueprint(ui_bp)

    @app.before_request
    def default_deny_api():
        """Require authentication and an explicit decorator on /api/*."""

        if request.path != "/api" and not request.path.startswith("/api/"):
            return None
        if (request.method, request.path) in PUBLIC_API_ENDPOINTS:
            return None

        user = get_current_user()
        if user is None:
            return jsonify({
                "success": False,
                "message": AUTHENTICATION_REQUIRED,
            }), 401

        if _project_only_employee_grant(user):
            return jsonify({
                "success": False,
                "message": PERMISSION_DENIED,
            }), 403

        endpoint = request.endpoint
        view = current_app.view_functions.get(endpoint) if endpoint else None
        if view is None or not getattr(view, "_rbac_protected", False):
            return jsonify({
                "success": False,
                "message": PERMISSION_DENIED,
            }), 403

        return None

    @app.after_request
    def prevent_salary_caching(response):
        """Keep confidential salary responses out of browser caches."""

        if request.path.startswith("/api/salaries"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Handle unknown API routes and record-scope abort(404) calls.
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            "success": False,
            "message": PERMISSION_DENIED
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "message": "Resource not found"
        }), 404

    # Handle unexpected server errors
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500

    return app
