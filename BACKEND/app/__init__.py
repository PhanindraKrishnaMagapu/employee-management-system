
"""Flask application factory for Employee Management System."""

from flask import Flask, jsonify

from app.config import Config
from app.routes.health import health_bp
from app.routes.auth import auth_bp


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

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
