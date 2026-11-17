"""Flask application factory.

Phase 1 creates the application and loads settings.
Later phases register REST blueprints here. No business routes are
registered yet, and this module does not open the database.
"""

from flask import Flask

from app.config import Config


def create_app(config_class=Config):
    """Build and return the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Employee, auth, organization, and other blueprints will be registered
    # in later phases. Phase 1 leaves the URL map empty on purpose.

    return app
