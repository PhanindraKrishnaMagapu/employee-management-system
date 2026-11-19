"""Read application settings from environment variables.

Copy BACKEND/.env.example to BACKEND/.env for local values.
Do not commit .env. This module does not load .env by itself.
Set the variables in your shell before starting Flask, or use a tool
you trust to load them. See DOCS/setup-guide.md.
"""

import os
from datetime import timedelta
from pathlib import Path

# BACKEND/ directory (parent of the app package).
BASE_DIR = Path(__file__).resolve().parent.parent

# Development-only fallback. Production startup refuses this value.
DEFAULT_SECRET_KEY = "dev-only-change-me"

# Only these explicit values are treated as local development environments.
# Anything else (including unset) requires a real configured secret.
DEVELOPMENT_ENVIRONMENTS = frozenset({
    "development",
    "dev",
    "local",
    "test",
    "testing",
})


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


def environment_name():
    """Return the normalized FLASK_ENV value (defaults to development)."""

    return os.environ.get("FLASK_ENV", "development").strip().lower()


def is_development():
    """Return True only for an explicitly recognized development environment."""

    return environment_name() in DEVELOPMENT_ENVIRONMENTS


def is_production():
    """Return True when the environment is explicitly marked as production.

    Read at call time so shell changes and test monkeypatching are respected.
    """
    return environment_name() == "production"


class Config:
    """Settings for the local Employee Management System."""

    # Development fallback only. Set FLASK_SECRET_KEY before real use.
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", DEFAULT_SECRET_KEY)
    DATABASE_PATH = _database_path()
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # The session cookie is an authentication credential, so harden it.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = is_production()

    # Login marks sessions as permanent so this lifetime applies to the
    # cookie. Non-permanent sessions still expire when the browser closes.
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
