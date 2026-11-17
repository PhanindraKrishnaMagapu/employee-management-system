"""SQLite access point.

Phase 2 will:
- open the file at Config.DATABASE_PATH
- enable foreign keys on every connection
- apply BACKEND/database/schema.sql

Phase 1 does not open SQLite and does not create tables.
"""


def get_connection():
    """Open the database. Not available until Phase 2."""
    raise NotImplementedError(
        "Database connections start in Phase 2. "
        "See DOCS/architecture.md and DOCS/database-design.md."
    )
