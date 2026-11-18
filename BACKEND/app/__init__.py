"""Flask application factory for Employee Management System."""

from flask import Flask, current_app, jsonify, request

from app.auth.context import get_current_user
from app.auth.decorators import AUTHENTICATION_REQUIRED, PERMISSION_DENIED
from app.config import DEFAULT_SECRET_KEY, Config, is_production
from app.routes.health import health_bp
from app.routes.auth import auth_bp


# Deliberately small: every other /api/* route is authenticated by default and
# must also be marked by a real authorization decorator to be reachable.
PUBLIC_API_ENDPOINTS = frozenset({
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
})


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

    secret_key = app.config.get("SECRET_KEY")
    normalized_key = secret_key.strip() if isinstance(secret_key, str) else ""
    if is_production() and (
        not normalized_key or normalized_key == DEFAULT_SECRET_KEY
    ):
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set to a non-default value in production"
        )

    # Evaluate at startup so environment changes after import are respected.
    app.config["SESSION_COOKIE_SECURE"] = is_production()

    # Register API blueprints
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")

    @app.before_request
    def default_deny_api():
        """Require authentication and an explicit decorator on /api/*."""

        if not request.path.startswith("/api/"):
            return None
        if (request.method, request.path) in PUBLIC_API_ENDPOINTS:
            return None

        if get_current_user() is None:
            return jsonify({
                "success": False,
                "message": AUTHENTICATION_REQUIRED,
            }), 401

        endpoint = request.endpoint
        view = current_app.view_functions.get(endpoint) if endpoint else None
        if view is None or not getattr(view, "_rbac_protected", False):
            return jsonify({
                "success": False,
                "message": PERMISSION_DENIED,
            }), 403

        return None

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
