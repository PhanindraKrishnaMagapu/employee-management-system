"""Production entry point for the isolated Render demo deployment."""

import os
import tempfile
from pathlib import Path


DEMO_DATABASE_DIRECTORY = "employee-management-system-demo"


def create_demo_app():
    """Initialize an isolated fictional demo database and return the app."""

    # Render's filesystem is ephemeral. Always keep this deployment's database
    # in the temporary directory and never honor the local DATABASE_PATH.
    os.environ["FLASK_ENV"] = "production"
    database_path = (
        Path(tempfile.gettempdir()) / DEMO_DATABASE_DIRECTORY / "ems.sqlite"
    )

    from app import create_app
    from app.config import Config
    from app.db import apply_migrations, initialize_database, provision_hosted_demo_user

    # The database module intentionally uses this shared local setting; this
    # production-only entry point redirects it before any DB helper is called.
    Config.DATABASE_PATH = str(database_path)

    class RenderDemoConfig(Config):
        SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
        DATABASE_PATH = str(database_path)
        FLASK_ENV = "production"

    application = create_app(RenderDemoConfig)
    initialize_database(seed=True)
    apply_migrations()
    provision_hosted_demo_user()
    return application


def main():
    """Start the production WSGI server using Render's assigned port."""

    from waitress import serve

    application = create_demo_app()
    port = int(os.environ.get("PORT", "10000"))
    serve(application, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
