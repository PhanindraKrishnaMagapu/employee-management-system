
"""SQLite database connection and initialization utilities."""

import argparse
import sqlite3
import sys
from pathlib import Path

from app.config import Config


BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = BACKEND_DIR / "database" / "schema.sql"
SEED_FILE = BACKEND_DIR / "database" / "seed.sql"


def get_database_path():
    """Return the configured SQLite database path."""
    return Path(Config.DATABASE_PATH).resolve()


def get_connection():
    """Open a SQLite connection with foreign keys enabled."""
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database(seed=True):
    """Create database tables and optionally insert development data."""
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    if seed and not SEED_FILE.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_FILE}")

    connection = get_connection()

    try:
        schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        connection.executescript(schema_sql)

        if seed:
            seed_sql = SEED_FILE.read_text(encoding="utf-8")
            connection.executescript(seed_sql)

        connection.commit()
        print(f"Database initialized successfully: {get_database_path()}")

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def main():
    """Run database commands from the terminal."""
    parser = argparse.ArgumentParser(description="Employee Management System database")
    parser.add_argument(
        "command",
        choices=["init"],
        help="Initialize database tables and development seed data",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Create tables without inserting sample data",
    )

    args = parser.parse_args()

    try:
        if args.command == "init":
            initialize_database(seed=not args.no_seed)
    except (sqlite3.Error, OSError, ValueError) as error:
        print(f"Database initialization failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
