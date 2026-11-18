
"""Flask application factory for Employee Management System."""

from flask import Flask, jsonify

from app.config import DEFAULT_SECRET_KEY, Config, is_production
from app.routes.health import health_bp
from app.routes.auth import auth_bp


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

    # Handle unknown API routes
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
