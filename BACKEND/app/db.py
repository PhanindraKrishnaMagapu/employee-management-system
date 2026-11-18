"""SQLite database connection and initialization utilities."""

import argparse
import getpass
import os
import re
import sqlite3
import sys
from pathlib import Path

from app.config import Config, is_production


BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = BACKEND_DIR / "database" / "schema.sql"
SEED_FILE = BACKEND_DIR / "database" / "seed.sql"
MIGRATIONS_DIR = BACKEND_DIR / "database" / "migrations"

# Exact fictional demo accounts managed by the development-only password tool.
DEMO_USERNAMES = (
    "demo_ceo",
    "demo_hr_admin",
    "demo_hr_exec",
    "demo_dept_manager",
    "demo_project_manager",
    "demo_employee",
    "demo_sysadmin",
)

# Sentinel written by seed.sql. It is not a password and cannot authenticate.
PLACEHOLDER_PASSWORD_HASH = "NOT_A_REAL_PASSWORD_HASH"


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


_ADD_COLUMN_PATTERN = re.compile(
    r"^\s*ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+ADD\s+(?:COLUMN\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _sql_statements(script):
    """Split a migration script into statements, ignoring comment lines."""

    statements = []
    buffer = []

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if sqlite3.complete_statement(candidate):
            statements.append(candidate)
            buffer = []

    remainder = "\n".join(buffer).strip()
    if remainder:
        statements.append(remainder)

    return statements


def _column_exists(connection, table, column):
    rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(row["name"] == column for row in rows)


def apply_migrations():
    """Apply pending additive migrations safely and idempotently.

    A ``schema_migrations`` table records completed scripts. In addition,
    ALTER TABLE ... ADD COLUMN statements are skipped when the column already
    exists, so re-running after a partial application cannot fail. The local
    development database is only changed when this function is called with
    that database configured; tests always point it at a temporary file.
    """

    connection = get_connection()
    applied = []
    skipped = []

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        recorded = {
            row["name"]
            for row in connection.execute("SELECT name FROM schema_migrations")
        }

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in migration_files:
            name = path.stem
            if name in recorded:
                skipped.append(name)
                continue

            for statement in _sql_statements(path.read_text(encoding="utf-8")):
                match = _ADD_COLUMN_PATTERN.match(statement)
                if match and _column_exists(connection, match.group(1), match.group(2)):
                    continue
                connection.execute(statement)

            connection.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)", (name,)
            )
            applied.append(name)
            recorded.add(name)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {"applied": applied, "skipped": skipped}


def is_valid_password_hash(value):
    """Return True when a stored value looks like an existing password hash.

    Conservative on purpose: anything that is not the seed placeholder and
    contains the separators used by Werkzeug hashes is treated as an existing
    hash, so real hashes are never overwritten by accident.
    """
    if not isinstance(value, str) or not value or value == PLACEHOLDER_PASSWORD_HASH:
        return False
    return value.count("$") >= 2


def provision_demo_passwords(password, *, force=False):
    """Provision demo passwords for the seven fictional demo accounts.

    Development-only. Existing valid hashes are preserved unless force is
    True. Returns a summary of updated, skipped and missing usernames.
    """
    if is_production():
        raise RuntimeError("Refusing to provision demo passwords in production")
    if not isinstance(password, str) or not password:
        raise ValueError("A non-empty demo password is required")

    # Imported lazily: app.services.auth imports get_connection from this module.
    from app.services.auth import authenticate_user, hash_password

    connection = get_connection()
    updated = []
    skipped = []
    missing = []

    try:
        connection.execute("BEGIN IMMEDIATE")

        placeholders = ", ".join("?" for _ in DEMO_USERNAMES)
        rows = connection.execute(
            f"SELECT id, username, password_hash FROM users "
            f"WHERE username IN ({placeholders}) ORDER BY id",
            DEMO_USERNAMES,
        ).fetchall()
        by_username = {row["username"]: row for row in rows}

        for username in DEMO_USERNAMES:
            row = by_username.get(username)
            if row is None:
                missing.append(username)
                continue
            if is_valid_password_hash(row["password_hash"]) and not force:
                skipped.append(username)
                continue

            cursor = connection.execute(
                "UPDATE users SET password_hash = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND username = ?",
                (hash_password(password), row["id"], username),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Unexpected update result for demo account: {username}"
                )
            updated.append(username)

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    # End-to-end verification with a fresh connection after the commit.
    for username in updated:
        if not authenticate_user(username, password):
            raise RuntimeError(
                "Post-provisioning authentication verification failed for: "
                f"{username}"
            )

    return {"updated": updated, "skipped": skipped, "missing": missing}


def _read_demo_password(args):
    """Read the demo password without storing it in any project file."""
    if args.password_env:
        if not args.yes:
            raise ValueError("Non-interactive password input requires --yes")
        value = os.environ.get(args.password_env)
        if not value:
            raise ValueError(f"Environment variable is not set: {args.password_env}")
        return value

    first = getpass.getpass("Demo password for fictional accounts: ")
    second = getpass.getpass("Confirm demo password: ")
    if first != second:
        raise ValueError("Entered passwords do not match")
    return first


def main():
    """Run database commands from the terminal."""
    parser = argparse.ArgumentParser(description="Employee Management System database")
    parser.add_argument(
        "command",
        choices=["init", "migrate", "demo-passwords"],
        help="Initialize the database, apply migrations, or provision demo passwords",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Create tables without inserting sample data",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing demo password hashes (default: preserve them)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm non-interactive password input from --password-env",
    )
    parser.add_argument(
        "--password-env",
        metavar="NAME",
        help="Read the demo password from this environment variable (requires --yes)",
    )

    args = parser.parse_args()

    if args.command == "init":
        try:
            initialize_database(seed=not args.no_seed)
        except (sqlite3.Error, OSError, ValueError) as error:
            print(f"Database initialization failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error
        return

    if args.command == "migrate":
        try:
            result = apply_migrations()
        except (sqlite3.Error, OSError, ValueError) as error:
            print(f"Database migration failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        print(f"Applied migration(s): {', '.join(result['applied']) or 'none'}")
        if result["skipped"]:
            print(f"Already applied: {', '.join(result['skipped'])}")
        return

    try:
        password = _read_demo_password(args)
        summary = provision_demo_passwords(password, force=args.force)
    except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
        print(f"Demo password provisioning failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Provisioned demo passwords for {len(summary['updated'])} account(s).")
    if summary["skipped"]:
        print(
            f"Skipped {len(summary['skipped'])} account(s) with existing hashes; "
            "use --force to replace them."
        )
    if summary["missing"]:
        print(f"Warning: {len(summary['missing'])} demo account(s) were not found.")
    if summary["updated"]:
        print("Authentication verification passed for all updated accounts.")


if __name__ == "__main__":
    main()
