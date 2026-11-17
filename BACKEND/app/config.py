"""Read application settings from environment variables.

Copy BACKEND/.env.example to BACKEND/.env for local values.
Do not commit .env. This module does not load .env by itself.
Set the variables in your shell before starting Flask, or use a tool
you trust to load them. See DOCS/setup-guide.md.
"""

import os
from pathlib import Path

# BACKEND/ directory (parent of the app package).
BASE_DIR = Path(__file__).resolve().parent.parent


def _database_path():
    """Return an absolute path to the SQLite file.

    A relative DATABASE_PATH is resolved from the BACKEND folder so the
    file is not created in whatever directory the command happened to
    start in. Phase 1 does not create the file.
    """
    raw = os.environ.get("DATABASE_PATH", "database/ems.sqlite")
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


class Config:
    """Settings for the local Employee Management System."""

    # Development fallback only. Set FLASK_SECRET_KEY before real use.
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
    DATABASE_PATH = _database_path()
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
