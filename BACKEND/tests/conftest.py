"""Shared pytest fixtures using isolated temporary databases."""

import pytest

from app.config import Config
from app.db import initialize_database


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
